"""Multi-provider LLM router with fall-through and rate-limit cooldown.

A *role* ("triage", "converse", "reason") maps to an ordered list of
candidate endpoints in configuration. ``complete()`` tries each in turn,
skipping any still cooling down from a prior 429, and falls through on
failure rather than propagating it to the caller.

Two decisions are specific to Telemachus rather than inherited from the
general shape of this pattern:

**Roles express escalation, not preference.** Telemachus is an unattended
system; it is expected to look at many observations and reason about very
few. Cheap models triage, expensive models decide. Putting that in
configuration keeps the policy visible instead of scattering model names
through the Core.

**The router is optional.** ``try_complete()`` returns None instead of
raising when every candidate fails, so an unreachable Ollama or an expired
API key degrades Telemachus to deterministic behaviour rather than taking
it down (ADR-009, Graceful Degradation).

Transport is stdlib ``urllib``. An OpenAI-compatible chat completion is a
single JSON POST, and that is worth more than a dependency: Groq,
OpenRouter, Together, llama.cpp, vLLM, and LM Studio all speak it, and
Ollama's native API is one more POST.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telemachus.config import LLMCandidate, LLMConfig

logger = logging.getLogger("telemachus.llm.router")

DEFAULT_COOLDOWN_SEC = 90.0


class AllCandidatesFailedError(RuntimeError):
    """Every candidate for a role failed, or was skipped while cooling down."""


@dataclass(frozen=True)
class Message:
    """A single chat message."""

    role: str
    content: str

    def as_dict(self) -> dict[str, str]:
        """Return the wire representation."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class Completion:
    """A successful completion and the provenance needed to audit it."""

    text: str
    candidate: str
    model: str
    latency_ms: float


@dataclass
class _Cooldown:
    """Per-candidate rate-limit backoff, persisted across restarts."""

    until: float = 0.0


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    """POST JSON and parse the JSON response.

    Args:
        url: Fully-qualified endpoint URL.
        payload: Request body, serialized as JSON.
        headers: Additional request headers.
        timeout: Socket timeout in seconds.

    Returns:
        The decoded response body.

    Raises:
        urllib.error.HTTPError: On a non-2xx response.
        urllib.error.URLError: On a connection failure or timeout.
        ValueError: If the response body is not valid JSON.
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
    parsed: dict[str, Any] = json.loads(raw)
    return parsed


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    """Extract a Retry-After hint from a 429 response, if it carries one."""
    header = error.headers.get("retry-after") if error.headers else None
    if header is None:
        return None
    try:
        return float(header)
    except (TypeError, ValueError):
        return None


def _call_openai_compatible(
    candidate: LLMCandidate, messages: list[Message], max_tokens: int,
    temperature: float, timeout: float,
) -> str:
    """Call an OpenAI-compatible /chat/completions endpoint."""
    headers = {}
    if candidate.api_key_env:
        api_key = os.environ.get(candidate.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"{candidate.api_key_env} is not set")
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": candidate.model,
        "messages": [m.as_dict() for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    payload.update(candidate.extra_body)

    data = _post_json(
        f"{candidate.base_url.rstrip('/')}/chat/completions", payload, headers, timeout
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("response contained no choices")
    content = choices[0].get("message", {}).get("content")
    return str(content or "")


def _call_ollama(
    candidate: LLMCandidate, messages: list[Message], max_tokens: int,
    temperature: float, timeout: float,
) -> str:
    """Call Ollama's native /api/chat endpoint."""
    payload: dict[str, Any] = {
        "model": candidate.model,
        "messages": [m.as_dict() for m in messages],
        "stream": False,
        # Hybrid-reasoning models spend the token budget on chain-of-thought
        # before emitting any content, which leaves `content` empty at modest
        # max_tokens. Deliberate reasoning belongs to the "reason" role and
        # its own candidate, not to every call.
        "think": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    payload.update(candidate.extra_body)

    data = _post_json(
        f"{candidate.base_url.rstrip('/')}/api/chat", payload, {}, timeout
    )
    return str(data.get("message", {}).get("content") or "")


_PROVIDERS: dict[str, Callable[..., str]] = {
    "openai": _call_openai_compatible,
    "ollama": _call_ollama,
}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class LLMRouter:
    """Routes a role to the first working candidate configured for it.

    Attributes:
        config: The LLM configuration section.
        state_dir: Directory holding cooldown state and the call log.
    """

    def __init__(self, config: LLMConfig, state_dir: Path | None = None) -> None:
        """Initialize the router.

        Args:
            config: The LLM configuration section.
            state_dir: Where to persist cooldowns and the audit log. When
                None the router keeps cooldowns in memory only, which is
                what tests and one-shot invocations want.
        """
        self.config = config
        self.state_dir = state_dir
        self._cooldowns: dict[str, _Cooldown] = {}
        self._lock = threading.Lock()
        self._loaded = False

    # -- cooldown state ------------------------------------------------

    @property
    def _state_path(self) -> Path | None:
        return None if self.state_dir is None else self.state_dir / "llm_cooldowns.json"

    @property
    def _log_path(self) -> Path | None:
        return None if self.state_dir is None else self.state_dir / "llm_calls.jsonl"

    def _load(self) -> None:
        """Load persisted cooldowns once, tolerating a corrupt file."""
        if self._loaded:
            return
        self._loaded = True
        path = self._state_path
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for name, entry in raw.items():
                self._cooldowns[name] = _Cooldown(until=float(entry.get("until", 0.0)))
        except (OSError, ValueError) as exc:
            logger.warning("Discarding unreadable cooldown state: %s", exc)

    def _save(self) -> None:
        """Persist cooldowns, tolerating an unwritable directory."""
        path = self._state_path
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({k: {"until": v.until} for k, v in self._cooldowns.items()}),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not persist cooldown state: %s", exc)

    def _cooling_for(self, name: str) -> float:
        """Seconds remaining on a candidate's cooldown, 0 if it is available."""
        with self._lock:
            self._load()
            entry = self._cooldowns.get(name)
            return 0.0 if entry is None else max(0.0, entry.until - time.time())

    def _start_cooldown(self, name: str, retry_after: float | None) -> None:
        with self._lock:
            self._load()
            wait = retry_after if retry_after and retry_after > 0 else DEFAULT_COOLDOWN_SEC
            self._cooldowns[name] = _Cooldown(until=time.time() + wait)
            self._save()
        logger.warning("Candidate %s cooling down for %.0fs", name, wait)

    def _clear_cooldown(self, name: str) -> None:
        with self._lock:
            self._load()
            if self._cooldowns.pop(name, None) is not None:
                self._save()

    # -- audit ---------------------------------------------------------

    def _log_attempt(
        self, role: str, candidate: LLMCandidate, outcome: str,
        latency_ms: float, error: str = "",
    ) -> None:
        """Append one attempt to the call log.

        Every prompt that leaves the machine is recorded with the endpoint
        that saw it. Once traffic is spread across vendors this is the only
        way to answer "who received this".
        """
        path = self._log_path
        if path is None:
            return
        entry = {
            "ts": time.time(),
            "role": role,
            "candidate": candidate.name,
            "provider": candidate.provider,
            "model": candidate.model,
            "outcome": outcome,
            "latency_ms": round(latency_ms, 1),
        }
        if error:
            entry["error"] = error[:300]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.debug("Could not write call log: %s", exc)

    # -- public API ----------------------------------------------------

    def candidates_for(self, role: str) -> list[LLMCandidate]:
        """Return the configured candidates for a role, in preference order."""
        return self.config.candidates.get(role, [])

    def available(self, role: str) -> bool:
        """Whether this role could plausibly be served right now.

        True when the LLM layer is enabled and at least one candidate for
        the role is configured and not cooling down.
        """
        if not self.config.enabled:
            return False
        return any(
            self._cooling_for(c.name) == 0.0 for c in self.candidates_for(role)
        )

    def complete(
        self,
        role: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        validate: Callable[[str], bool] | None = None,
    ) -> Completion:
        """Complete a chat request using the first candidate that works.

        Args:
            role: The configured role to route through.
            messages: The conversation to complete.
            max_tokens: Override the candidate's token budget.
            temperature: Override the candidate's temperature.
            validate: Optional predicate applied to each reply. A reply that
                fails it is treated exactly like a failed call and the chain
                falls through — this is how a syntactically fine but
                semantically unusable answer gets a second chance on a
                different model instead of being returned.

        Returns:
            The first accepted Completion.

        Raises:
            AllCandidatesFailedError: If the layer is disabled, no candidates are
                configured for the role, or every candidate failed.
        """
        if not self.config.enabled:
            raise AllCandidatesFailedError("LLM layer is disabled in configuration")

        candidates = self.candidates_for(role)
        if not candidates:
            raise AllCandidatesFailedError(f"No candidates configured for role {role!r}")

        errors: list[str] = []

        for candidate in candidates:
            cooling = self._cooling_for(candidate.name)
            if cooling > 0:
                logger.info(
                    "Skipping %s for role=%s (cooling down %.0fs)",
                    candidate.name, role, cooling,
                )
                errors.append(f"{candidate.name}: cooling down ({int(cooling)}s)")
                continue

            call = _PROVIDERS.get(candidate.provider)
            if call is None:
                errors.append(f"{candidate.name}: unknown provider {candidate.provider!r}")
                continue

            started = time.monotonic()
            try:
                text = call(
                    candidate,
                    messages,
                    max_tokens if max_tokens is not None else candidate.max_tokens,
                    temperature if temperature is not None else candidate.temperature,
                    self.config.timeout_sec,
                )
                latency_ms = (time.monotonic() - started) * 1000

                if not text.strip():
                    raise RuntimeError("empty response")
                if validate is not None and not validate(text):
                    raise RuntimeError("reply rejected by validator")

                self._clear_cooldown(candidate.name)
                self._log_attempt(role, candidate, "ok", latency_ms)
                logger.info(
                    "role=%s served by %s (%.0fms)", role, candidate.name, latency_ms
                )
                return Completion(
                    text=text,
                    candidate=candidate.name,
                    model=candidate.model,
                    latency_ms=latency_ms,
                )

            except urllib.error.HTTPError as exc:
                latency_ms = (time.monotonic() - started) * 1000
                if exc.code == 429:
                    self._start_cooldown(candidate.name, _retry_after(exc))
                    outcome = "rate_limited"
                else:
                    outcome = "http_error"
                self._log_attempt(role, candidate, outcome, latency_ms, f"HTTP {exc.code}")
                errors.append(f"{candidate.name}: HTTP {exc.code}")

            except Exception as exc:  # noqa: BLE001 — any failure falls through
                latency_ms = (time.monotonic() - started) * 1000
                self._log_attempt(role, candidate, "error", latency_ms, str(exc))
                logger.warning("%s failed for role=%s: %s", candidate.name, role, exc)
                errors.append(f"{candidate.name}: {exc}")

        raise AllCandidatesFailedError(f"role={role}: " + " | ".join(errors))

    def try_complete(
        self,
        role: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        validate: Callable[[str], bool] | None = None,
    ) -> Completion | None:
        """Like ``complete()``, but returns None instead of raising.

        This is the entry point the Core should use. A missing API key or an
        unreachable model server is a degraded capability, not an error the
        cognitive pipeline should have to handle.
        """
        try:
            return self.complete(
                role,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                validate=validate,
            )
        except AllCandidatesFailedError as exc:
            logger.info("No completion available for role=%s: %s", role, exc)
            return None

    def status(self) -> dict[str, Any]:
        """Summarize configured roles and any active cooldowns."""
        now = time.time()
        with self._lock:
            self._load()
            cooling = {
                name: round(entry.until - now, 1)
                for name, entry in self._cooldowns.items()
                if entry.until > now
            }
        return {
            "enabled": self.config.enabled,
            "roles": {
                role: [c.name for c in cands]
                for role, cands in self.config.candidates.items()
            },
            "cooling_down": cooling,
        }

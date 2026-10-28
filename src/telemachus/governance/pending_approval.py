"""Pending approval request and request-bound challenge matching (GOV-ADR-001).

A ``PendingApprovalRequest`` records that one exact action is awaiting
potential human consideration. It binds to the action through the same
canonical representation and SHA-256 digest that ``AuthorizationGrant``
uses (``governance/authorization.py``), and carries a *commitment* to a
per-request challenge. The commitment covers the request ID, the
canonical action digest and the challenge, so a challenge issued for one
request and action does not match a record bound to another. The
plaintext challenge is returned once at creation and is never stored on
the request.

This is not an authorization mechanism, and it is not an
``ActionRequest``, ``ActionProposal``, ``AuthorizationGrant`` or
executable action. It has no approval, authorization or eligibility
state: that a request exists says nothing about whether the action could
ever be granted. Policy (P1, P2, P3, P4, P5, reversibility, expiry)
belongs to a later issuer, not here.

What ``challenge_matches()`` establishes, and nothing more: the supplied
text equals the challenge whose commitment this request holds. It does
not establish human identity, human presence, approval provenance or
authorization. The code that created the request also holds the
plaintext challenge, and nothing here shows where a response came from.
The challenge is only friction against reflexive, ambiguous or
cross-request replies; the 8-character challenge is also a small space,
so anyone who obtains a request object can recover it by brute force.
This module is not a security boundary against malicious in-process
code. Operator identity (``governance/operator.py``) is separate and is
not consulted.

The creation timestamp is caller-supplied metadata. There is no clock,
expiry or persistence here.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import (
    BINDING_FORMAT_VERSION,
    canonical_action_bytes,
)

# Crockford base32: digits plus letters without I, L, O and U. With I, L
# and O absent, 0 and 1 have no look-alike in the set. Exactly 32 symbols.
_CHALLENGE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CHALLENGE_LENGTH = 8

_COMMITMENT_DOMAIN = b"telemachus.pending_approval.challenge.v1"
_HEX_SHA256_CHARS = frozenset("0123456789abcdef")
_BINDING_KEYS = frozenset({"arguments", "binding_format", "impact", "tool"})
_CONSTRAINTS_BY_VALUE = {c.value: c for c in ProtectedConstraint}


# ---------------------------------------------------------------------------
# Challenge
# ---------------------------------------------------------------------------


def generate_challenge() -> str:
    """Return a fresh 8-character challenge from a cryptographic source.

    Drawn with ``secrets.choice`` from a 32-symbol alphabet that avoids
    visually ambiguous characters (no I, L, O or U). Not configurable.
    """
    return "".join(secrets.choice(_CHALLENGE_ALPHABET) for _ in range(_CHALLENGE_LENGTH))


def _is_valid_challenge(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == _CHALLENGE_LENGTH
        and all(ch in _CHALLENGE_ALPHABET for ch in value)
    )


def _length_prefixed(*parts: bytes) -> bytes:
    """Unambiguous encoding: each part is preceded by its 8-byte length."""
    return b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def _commitment(request_id: str, action_digest: str, challenge: str) -> str:
    """SHA-256 over a domain tag, the request id, the action digest and the challenge.

    Each component is length-prefixed, so no two distinct tuples encode
    to the same bytes. Binding the action digest means a challenge issued
    for one action cannot validate against a record bound to another.
    """
    return hashlib.sha256(
        _length_prefixed(
            _COMMITMENT_DOMAIN,
            request_id.encode("utf-8"),
            action_digest.encode("ascii"),
            challenge.encode("utf-8"),
        )
    ).hexdigest()


# ---------------------------------------------------------------------------
# Binding validation
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r} in canonical binding")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} in canonical binding")


def _parse_binding(binding: bytes) -> dict[str, Any]:
    """Strictly parse canonical binding bytes into its document."""
    try:
        document = json.loads(
            binding.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"canonical_binding is not valid canonical JSON: {exc}") from exc
    if type(document) is not dict or set(document) != _BINDING_KEYS:
        raise ValueError("canonical_binding does not have the expected structure")
    if document["binding_format"] != BINDING_FORMAT_VERSION or (
        type(document["binding_format"]) is not int
    ):
        raise ValueError("canonical_binding has an unsupported binding_format")
    tool = document["tool"]
    if (
        type(tool) is not dict
        or set(tool) != {"name", "version"}
        or type(tool["name"]) is not str
        or type(tool["version"]) is not str
    ):
        raise ValueError("canonical_binding has an invalid tool section")
    if type(document["arguments"]) is not dict:
        raise ValueError("canonical_binding arguments must be an object")
    impact_values = document["impact"]
    if type(impact_values) is not list or not all(
        type(v) is str and v in _CONSTRAINTS_BY_VALUE for v in impact_values
    ):
        raise ValueError("canonical_binding impact must list known Protected Constraints")
    if len(set(impact_values)) != len(impact_values):
        raise ValueError("canonical_binding impact contains duplicates")
    return document


def _impact_of(document: dict[str, Any]) -> frozenset[ProtectedConstraint]:
    return frozenset(_CONSTRAINTS_BY_VALUE[v] for v in document["impact"])


def _require_finite_time(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number (Unix time)")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


# ---------------------------------------------------------------------------
# Pending approval request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingApprovalRequest:
    """One exact action awaiting potential human consideration.

    Not an authorization, approval, eligibility decision or executable
    action; see the module docstring. ``canonical_binding`` is the source
    of truth for the action; ``action_digest`` and ``impact`` are checked
    against it on construction.

    Attributes:
        request_id: Unique identifier of this request.
        created_at: Caller-supplied Unix time. Metadata only.
        canonical_binding: The exact canonical bytes produced by
            ``canonical_action_bytes()`` for the action (immutable).
        action_digest: SHA-256 hex digest of ``canonical_binding``.
        impact: Effective Protected Constraint impact encoded in the
            binding. Creation applies no policy to it.
        challenge_commitment: SHA-256 commitment to this request's
            challenge, bound to ``request_id`` and ``action_digest``.
            Never the plaintext.

    Raises:
        ValueError: On construction, if the record is malformed or
            internally inconsistent.
    """

    request_id: str
    created_at: float
    canonical_binding: bytes
    action_digest: str
    impact: frozenset[ProtectedConstraint]
    challenge_commitment: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty str")
        _require_finite_time("created_at", self.created_at)
        if type(self.canonical_binding) is not bytes or not self.canonical_binding:
            raise ValueError("canonical_binding must be non-empty bytes")
        if not isinstance(self.impact, frozenset):
            raise ValueError("impact must be a frozenset of ProtectedConstraint")
        for constraint in self.impact:
            if not isinstance(constraint, ProtectedConstraint):
                raise ValueError(
                    f"impact must contain only ProtectedConstraint members, got {constraint!r}"
                )
        for name, value in (
            ("action_digest", self.action_digest),
            ("challenge_commitment", self.challenge_commitment),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or not set(value) <= _HEX_SHA256_CHARS
            ):
                raise ValueError(f"{name} must be 64 lowercase hex characters")

        document = _parse_binding(self.canonical_binding)
        if self.impact != _impact_of(document):
            raise ValueError("impact does not match the impact in canonical_binding")
        # Re-canonicalize through the shared implementation: the stored bytes
        # must be exactly what it produces, not merely parseable.
        expected = canonical_action_bytes(
            tool_name=document["tool"]["name"],
            tool_version=document["tool"]["version"],
            arguments=document["arguments"],
            impact=self.impact,
        )
        if expected != self.canonical_binding:
            raise ValueError("canonical_binding is not in canonical form")
        if hashlib.sha256(self.canonical_binding).hexdigest() != self.action_digest:
            raise ValueError("action_digest does not match canonical_binding")

    @property
    def tool_name(self) -> str:
        """Tool name, read from the canonical binding."""
        return str(_parse_binding(self.canonical_binding)["tool"]["name"])

    @property
    def tool_version(self) -> str:
        """Tool version, read from the canonical binding."""
        return str(_parse_binding(self.canonical_binding)["tool"]["version"])

    @property
    def arguments(self) -> dict[str, Any]:
        """A fresh copy of the arguments, read from the canonical binding."""
        arguments: dict[str, Any] = _parse_binding(self.canonical_binding)["arguments"]
        return arguments


@dataclass(frozen=True)
class CreatedPendingApproval:
    """Result of ``create_pending_approval()``.

    Attributes:
        request: The immutable request. Holds no plaintext challenge.
        challenge: The plaintext challenge, returned once for whatever
            will display it. Excluded from ``repr``.
    """

    request: PendingApprovalRequest
    challenge: str = field(repr=False)


def create_pending_approval(
    *,
    tool_name: str,
    tool_version: str,
    arguments: Mapping[str, Any],
    impact: frozenset[ProtectedConstraint],
    now: float,
    challenge_source: Callable[[], str] = generate_challenge,
) -> CreatedPendingApproval:
    """Create a pending approval request for one exact action.

    Creation applies no policy: any impact, including empty, is accepted,
    and a created request implies nothing about eligibility for a grant.

    Args:
        tool_name: Tool identity of the action.
        tool_version: Tool version of the action.
        arguments: Exact arguments of the action; copied into the binding.
        impact: The effective Protected Constraint impact.
        now: Caller-supplied creation time (metadata, not evidence).
        challenge_source: Supplies the challenge. Exists so tests can be
            deterministic; its output must still be exactly 8 characters
            from the documented alphabet, or creation fails.

    Raises:
        CanonicalizationError: If the action cannot be represented exactly.
        ValueError: If ``now`` is invalid or the challenge source returns
            a challenge outside the documented format.
    """
    _require_finite_time("now", now)
    binding = canonical_action_bytes(
        tool_name=tool_name, tool_version=tool_version, arguments=arguments, impact=impact
    )
    challenge = challenge_source()
    if not _is_valid_challenge(challenge):
        raise ValueError(
            f"challenge must be exactly {_CHALLENGE_LENGTH} characters "
            "from the documented alphabet"
        )
    request_id = str(uuid.uuid4())
    action_digest = hashlib.sha256(binding).hexdigest()
    request = PendingApprovalRequest(
        request_id=request_id,
        created_at=float(now),
        canonical_binding=binding,
        action_digest=action_digest,
        impact=frozenset(impact),
        challenge_commitment=_commitment(request_id, action_digest, challenge),
    )
    return CreatedPendingApproval(request=request, challenge=challenge)


def challenge_matches(request: PendingApprovalRequest, response: object) -> bool:
    """Whether ``response`` equals the challenge this request committed to.

    The commitment is recomputed from this request's ID and action digest
    together with the response, so the same text does not match a
    different request or a record bound to a different action. Exact
    comparison: no trimming, case folding or other rewriting. Any
    blank, partial, padded, malformed, incorrect or non-string response
    returns ``False``. A ``True`` result does not prove human identity,
    presence, approval provenance or authorization (see the module
    docstring).
    """
    if type(response) is not str:
        return False
    try:
        candidate = _commitment(request.request_id, request.action_digest, response)
    except UnicodeEncodeError:
        return False
    return secrets.compare_digest(
        candidate.encode("ascii"), request.challenge_commitment.encode("ascii")
    )

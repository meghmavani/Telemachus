"""Authorization grant value type and canonical action binding.

This module defines *binding semantics* for human authorization under
GOV-ADR-001 (Proposal → Authorization → Request, ``docs/DECISIONS.md``):

- what an ``AuthorizationGrant`` record contains,
- how the exact action being approved is canonically represented and
  digested,
- whether a grant's stated scope covers an action's Protected Constraint
  impact, and
- whether a point in time falls within a grant's validity window.

It does **not** establish authority. An ``AuthorizationGrant`` is a
record of a grant, not proof that one was legitimately issued: any code
can construct the object, so constructing one authorizes nothing. A
future verifier must consult a durable grant ledger, check consumption,
and rely on an authenticated principal recorded by a trusted human
approval surface — none of which exists yet. Nothing here is consulted
by the Constitution, Stage 6, or the tool registry.

The digest exists for exact-action binding, not secrecy: a grant issued
for one action must not match any other action (different tool, tool
version, arguments, or Protected Constraint impact).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from telemachus.core.codex import ProtectedConstraint

# Bumped if the canonical representation below ever changes, so a digest
# computed under one representation can never equal one computed under
# another.
BINDING_FORMAT_VERSION = 1

_CONSTRAINT_ORDER: dict[ProtectedConstraint, int] = {
    c: i for i, c in enumerate(ProtectedConstraint)
}
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class CanonicalizationError(ValueError):
    """Raised when an action cannot be represented in strict canonical JSON.

    Binding fails closed: a value that cannot be represented exactly is
    rejected rather than approximated, because an approximate
    representation could let two different actions share one digest.
    """


# ---------------------------------------------------------------------------
# Canonical action binding
# ---------------------------------------------------------------------------


def _check_strict_json(value: Any, path: str) -> None:
    """Reject anything that is not exactly representable as JSON.

    Accepted: ``None``, ``bool``, ``int``, finite ``float``, ``str``,
    ``list`` of accepted values, and ``dict`` with ``str`` keys and
    accepted values. Exact types only — subclasses (including ``Enum``
    members that subclass ``str``) and tuples are rejected, since JSON
    encoding would silently erase the distinction.
    """
    kind = type(value)
    if value is None or kind in (bool, int, str):
        return
    if kind is float:
        if not math.isfinite(value):
            raise CanonicalizationError(f"{path}: non-finite float {value!r}")
        return
    if kind is list:
        for i, item in enumerate(value):
            _check_strict_json(item, f"{path}[{i}]")
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise CanonicalizationError(
                    f"{path}: dict key {key!r} is not a str"
                )
            _check_strict_json(item, f"{path}.{key}")
        return
    raise CanonicalizationError(
        f"{path}: {kind.__name__} is not strictly JSON-representable"
    )


def canonical_action_bytes(
    *,
    tool_name: str,
    tool_version: str,
    arguments: Mapping[str, Any],
    impact: frozenset[ProtectedConstraint],
) -> bytes:
    """Return the canonical byte representation of an exact action.

    The representation is UTF-8 encoded JSON with sorted object keys and
    no insignificant whitespace, over:
    ``{"arguments", "binding_format", "impact", "tool": {"name", "version"}}``.
    ``impact`` is the list of ``ProtectedConstraint`` values in
    declaration order. Description, rationale, and any other
    presentation text are deliberately excluded: they describe what a
    human is shown, not what executes.

    Raises:
        CanonicalizationError: If any input cannot be represented exactly.
    """
    if type(tool_name) is not str or not tool_name:
        raise CanonicalizationError("tool_name must be a non-empty str")
    if type(tool_version) is not str or not tool_version:
        raise CanonicalizationError("tool_version must be a non-empty str")
    if not isinstance(arguments, Mapping):
        raise CanonicalizationError("arguments must be a mapping")
    args = dict(arguments)
    _check_strict_json(args, "arguments")
    for constraint in impact:
        if not isinstance(constraint, ProtectedConstraint):
            raise CanonicalizationError(
                f"impact contains a non-ProtectedConstraint value: {constraint!r}"
            )
    ordered_impact = [
        c.value for c in sorted(impact, key=lambda c: _CONSTRAINT_ORDER[c])
    ]
    document = {
        "arguments": args,
        "binding_format": BINDING_FORMAT_VERSION,
        "impact": ordered_impact,
        "tool": {"name": tool_name, "version": tool_version},
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_action_digest(
    *,
    tool_name: str,
    tool_version: str,
    arguments: Mapping[str, Any],
    impact: frozenset[ProtectedConstraint],
) -> str:
    """SHA-256 hex digest of ``canonical_action_bytes()`` for these inputs.

    ``impact`` must be the *effective* Protected Constraint impact of the
    action (caller-declared plus tool-declared), so a change to either
    produces a different digest.

    Raises:
        CanonicalizationError: If any input cannot be represented exactly.
    """
    return hashlib.sha256(
        canonical_action_bytes(
            tool_name=tool_name,
            tool_version=tool_version,
            arguments=arguments,
            impact=impact,
        )
    ).hexdigest()


# ---------------------------------------------------------------------------
# Grant record
# ---------------------------------------------------------------------------


def _require_non_empty_str(name: str, value: object) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty str")


def _require_finite_time(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number (Unix time)")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class AuthorizationGrant:
    """A record of a human authorization grant for one exact action.

    This is a value type, not an authority boundary. Constructing one
    does not authorize anything, and its fields are not verified here:
    ``principal`` and ``surface`` are recorded data, not authenticated
    identities. Whether a grant is genuine, unconsumed, and issued by an
    authorized human through a trusted surface is for a future verifier
    backed by a durable ledger to decide (GOV-ADR-001). Consumption
    state deliberately does not live on this immutable record.

    Attributes:
        grant_id: Unique identifier of the grant.
        principal: The human principal recorded as issuing the grant.
        surface: The approval surface recorded as issuing the grant.
        issued_at: Unix time the grant takes effect (inclusive).
        expires_at: Unix time the grant stops being valid (exclusive).
            Must be later than ``issued_at``.
        action_digest: ``compute_action_digest()`` of the exact action
            approved — 64 lowercase hex characters.
        scope: The Protected Constraints this grant was issued for.

    Raises:
        ValueError: On construction, if any field is malformed.
    """

    grant_id: str
    principal: str
    surface: str
    issued_at: float
    expires_at: float
    action_digest: str
    scope: frozenset[ProtectedConstraint]

    def __post_init__(self) -> None:
        _require_non_empty_str("grant_id", self.grant_id)
        _require_non_empty_str("principal", self.principal)
        _require_non_empty_str("surface", self.surface)
        _require_finite_time("issued_at", self.issued_at)
        _require_finite_time("expires_at", self.expires_at)
        if not self.expires_at > self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        if type(self.action_digest) is not str or not _SHA256_HEX_RE.match(
            self.action_digest
        ):
            raise ValueError("action_digest must be 64 lowercase hex characters")
        if not isinstance(self.scope, frozenset):
            raise ValueError("scope must be a frozenset of ProtectedConstraint")
        for constraint in self.scope:
            if not isinstance(constraint, ProtectedConstraint):
                raise ValueError(
                    f"scope must contain only ProtectedConstraint members, "
                    f"got {constraint!r}"
                )


# ---------------------------------------------------------------------------
# Pure predicates
# ---------------------------------------------------------------------------


def scope_covers(
    scope: frozenset[ProtectedConstraint], impact: frozenset[ProtectedConstraint]
) -> bool:
    """Whether a stated grant scope covers a Protected Constraint impact.

    True iff every constraint in ``impact`` is in ``scope``. An empty
    impact is trivially covered. Partial coverage is ``False``. This
    answers only the set question; it does not decide whether anything
    is permitted.
    """
    return impact <= scope


def is_within_validity_window(grant: AuthorizationGrant, now: float) -> bool:
    """Whether ``now`` falls in ``[grant.issued_at, grant.expires_at)``.

    ``now`` is supplied by the caller; this function never reads a
    clock. It ignores consumption, which belongs to a future ledger.
    """
    return grant.issued_at <= now < grant.expires_at

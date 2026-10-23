"""Verification of a ledger-recorded grant against one exact action (GOV-ADR-001).

``GrantVerifier.verify_and_consume()`` combines the existing primitives —
``GrantLedger.get()``, ``is_within_validity_window()``,
``compute_action_digest()``, ``scope_covers()`` and the ledger's atomic
``consume()`` — and reports an explicit outcome.

What a ``MATCHED_AND_CONSUMED`` outcome establishes, and nothing more:

- a grant with that id exists in the ledger,
- ``now`` was inside its validity window,
- its action digest equals the digest of the supplied tool, tool
  version, arguments and effective impact,
- its scope covers that impact, and
- the ledger atomically recorded its single consumption.

It does **not** establish that the grant represents genuine human
approval. Nothing in the repository authenticates a grant's ``principal``
or proves its ``surface`` is a trusted approval surface, and recording a
grant in the ledger does not do either. A matching ledger record is
therefore not sufficient for ``Constitution.validate_action()`` to
return ``PERMITTED``; that integration is deliberately not made here and
must wait for the issuer and approval surface to be designed.

Checks that can reject the action run *before* anything is consumed, so
a wrong-action attempt never uses up the legitimate grant. Single-use
enforcement stays with the ledger's atomic ``consume()``; this module
adds no read-then-write sequence of its own. This module does not call
the Constitution, construct an ``ActionRequest``, execute a tool, or
invoke the pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import (
    CanonicalizationError,
    compute_action_digest,
    is_within_validity_window,
    scope_covers,
)
from telemachus.governance.grant_ledger import (
    ConsumptionResult,
    CorruptGrantRecordError,
    GrantLedger,
    GrantLedgerError,
)


class VerificationOutcome(Enum):
    """Result of ``GrantVerifier.verify_and_consume()``.

    Only ``MATCHED_AND_CONSUMED`` is success, and it does not imply
    authenticated human approval (see the module docstring).
    """

    MATCHED_AND_CONSUMED = "matched_and_consumed"
    GRANT_NOT_FOUND = "grant_not_found"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    INVALID_ACTION_BINDING = "invalid_action_binding"
    DIGEST_MISMATCH = "digest_mismatch"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    ALREADY_CONSUMED = "already_consumed"
    CORRUPT_RECORD = "corrupt_record"
    LEDGER_FAILURE = "ledger_failure"


@dataclass(frozen=True)
class VerificationResult:
    """Outcome plus the information needed to understand it.

    Attributes:
        outcome: What happened.
        grant_id: The grant id that was checked.
        detail: Human-readable explanation, e.g. the underlying error
            for ``INVALID_ACTION_BINDING``, ``CORRUPT_RECORD`` and
            ``LEDGER_FAILURE``. Never relied on for control flow.
    """

    outcome: VerificationOutcome
    grant_id: str
    detail: str = ""

    @property
    def consumed(self) -> bool:
        """True only when the ledger confirmed this attempt consumed the grant.

        This is not a statement that a human authenticated or approved
        anything; see the module docstring.
        """
        return self.outcome is VerificationOutcome.MATCHED_AND_CONSUMED


_CONSUMPTION_OUTCOMES: dict[ConsumptionResult, VerificationOutcome] = {
    ConsumptionResult.CONSUMED: VerificationOutcome.MATCHED_AND_CONSUMED,
    ConsumptionResult.UNKNOWN_GRANT: VerificationOutcome.GRANT_NOT_FOUND,
    ConsumptionResult.ALREADY_CONSUMED: VerificationOutcome.ALREADY_CONSUMED,
    ConsumptionResult.NOT_YET_VALID: VerificationOutcome.NOT_YET_VALID,
    ConsumptionResult.EXPIRED: VerificationOutcome.EXPIRED,
}


class GrantVerifier:
    """Checks a recorded grant against an exact action and consumes it once.

    Holds a reference to a connected ``GrantLedger``; it does not open,
    close or write to the ledger except through ``consume()``.
    """

    def __init__(self, ledger: GrantLedger) -> None:
        self._ledger = ledger

    def verify_and_consume(
        self,
        grant_id: str,
        *,
        tool_name: str,
        tool_version: str,
        arguments: Mapping[str, Any],
        impact: frozenset[ProtectedConstraint],
        now: float,
    ) -> VerificationResult:
        """Verify ``grant_id`` against the exact action, consuming it only on a match.

        Order: fetch the grant; check the validity window; compute the
        action digest and compare; check scope coverage; only then ask
        the ledger to consume. The ledger decides whether single-use
        consumption succeeds, including when verifiers race.

        Args:
            grant_id: The grant to check.
            tool_name: Tool identity of the action.
            tool_version: Tool version of the action.
            arguments: Exact arguments of the action.
            impact: The *effective* Protected Constraint impact.
            now: Current Unix time, supplied by the caller.

        Returns:
            A ``VerificationResult``. Never raises for an ordinary
            rejection or for a ledger failure.

        Raises:
            TypeError: If ``now`` is not a number (a programming error).
        """
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("now must be a number (Unix time)")

        def result(outcome: VerificationOutcome, detail: str = "") -> VerificationResult:
            return VerificationResult(outcome=outcome, grant_id=grant_id, detail=detail)

        try:
            grant = self._ledger.get(grant_id)
        except CorruptGrantRecordError as exc:
            return result(VerificationOutcome.CORRUPT_RECORD, str(exc))
        except GrantLedgerError as exc:
            return result(VerificationOutcome.LEDGER_FAILURE, str(exc))
        if grant is None:
            return result(VerificationOutcome.GRANT_NOT_FOUND)

        if now < grant.issued_at:
            return result(VerificationOutcome.NOT_YET_VALID)
        if not is_within_validity_window(grant, now):
            return result(VerificationOutcome.EXPIRED)

        try:
            digest = compute_action_digest(
                tool_name=tool_name,
                tool_version=tool_version,
                arguments=arguments,
                impact=impact,
            )
        except CanonicalizationError as exc:
            return result(VerificationOutcome.INVALID_ACTION_BINDING, str(exc))
        if digest != grant.action_digest:
            return result(VerificationOutcome.DIGEST_MISMATCH)

        if not scope_covers(grant.scope, impact):
            return result(VerificationOutcome.INSUFFICIENT_SCOPE)

        try:
            consumption = self._ledger.consume(grant_id, now=now)
        except CorruptGrantRecordError as exc:
            return result(VerificationOutcome.CORRUPT_RECORD, str(exc))
        except GrantLedgerError as exc:
            return result(VerificationOutcome.LEDGER_FAILURE, str(exc))
        return result(_CONSUMPTION_OUTCOMES[consumption])

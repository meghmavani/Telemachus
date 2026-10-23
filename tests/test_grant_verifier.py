"""Tests for grant verification (GOV-ADR-001).

The verifier checks existence, validity window, exact-action digest,
scope coverage and single consumption. It does not authenticate any
issuer; a successful result is not proof of genuine human approval.
"""

from __future__ import annotations

import ast
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import AuthorizationGrant, compute_action_digest
from telemachus.governance.grant_ledger import GrantLedger, GrantLedgerError
from telemachus.governance.grant_verifier import (
    GrantVerifier,
    VerificationOutcome,
    VerificationResult,
)

P1 = ProtectedConstraint.CONSTITUTION_INTEGRITY
P2 = ProtectedConstraint.HUMAN_MEANING
P4 = ProtectedConstraint.RESOURCE_AUTHORIZATION

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"

ACTION: dict[str, Any] = {
    "tool_name": "echo",
    "tool_version": "1.0.0",
    "arguments": {"text": "hi", "count": 2},
    "impact": frozenset({P4}),
}


def _grant(**overrides: Any) -> AuthorizationGrant:
    fields: dict[str, Any] = {
        "grant_id": "grant-1",
        "principal": "operator",
        "surface": "cli",
        "issued_at": 100.0,
        "expires_at": 200.0,
        "action_digest": compute_action_digest(**ACTION),
        "scope": frozenset({P4}),
    }
    fields.update(overrides)
    return AuthorizationGrant(**fields)


def _open(path: Path) -> GrantLedger:
    ledger = GrantLedger(path)
    ledger.connect()
    ledger.initialize_schema()
    return ledger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "authorization.db"


@pytest.fixture
def ledger(db_path: Path) -> Generator[GrantLedger, None, None]:
    lg = _open(db_path)
    lg.record(_grant())
    try:
        yield lg
    finally:
        lg.disconnect()


def _verify(
    ledger: GrantLedger, *, now: float = 150.0, grant_id: str = "grant-1", **overrides: Any
) -> VerificationResult:
    action = {**ACTION, **overrides}
    return GrantVerifier(ledger).verify_and_consume(grant_id, now=now, **action)


def _still_consumable(ledger: GrantLedger) -> None:
    """The exact approved action still succeeds: nothing was consumed."""
    assert _verify(ledger).outcome is VerificationOutcome.MATCHED_AND_CONSUMED


# ---------------------------------------------------------------------------
# Matching action
# ---------------------------------------------------------------------------


class TestMatchingAction:
    def test_exact_match_is_consumed(self, ledger: GrantLedger) -> None:
        result = _verify(ledger)
        assert result.outcome is VerificationOutcome.MATCHED_AND_CONSUMED
        assert result.consumed is True
        assert result.grant_id == "grant-1"

    def test_cannot_succeed_twice(self, ledger: GrantLedger) -> None:
        assert _verify(ledger).consumed
        second = _verify(ledger)
        assert second.outcome is VerificationOutcome.ALREADY_CONSUMED
        assert second.consumed is False

    def test_argument_key_order_does_not_matter(self, ledger: GrantLedger) -> None:
        assert _verify(ledger, arguments={"count": 2, "text": "hi"}).consumed

    def test_consumption_persists_across_reopen(self, db_path: Path) -> None:
        first = _open(db_path)
        first.record(_grant())
        assert _verify(first).consumed
        first.disconnect()
        second = _open(db_path)
        try:
            assert _verify(second).outcome is VerificationOutcome.ALREADY_CONSUMED
        finally:
            second.disconnect()


# ---------------------------------------------------------------------------
# Digest mismatch: nothing may be consumed
# ---------------------------------------------------------------------------


class TestDigestMismatch:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"tool_name": "other"},
            {"tool_version": "2.0.0"},
            {"arguments": {"text": "hi", "count": 3}},
            {"arguments": {"text": "hi"}},
            {"impact": frozenset({P4, P1})},
            {"impact": frozenset()},
        ],
    )
    def test_mismatch_fails_and_leaves_grant_unconsumed(
        self, ledger: GrantLedger, overrides: dict[str, Any]
    ) -> None:
        result = _verify(ledger, **overrides)
        assert result.outcome in (
            VerificationOutcome.DIGEST_MISMATCH,
            VerificationOutcome.INSUFFICIENT_SCOPE,
        )
        assert result.consumed is False
        _still_consumable(ledger)

    def test_modified_arguments_report_digest_mismatch(self, ledger: GrantLedger) -> None:
        result = _verify(ledger, arguments={"text": "changed"})
        assert result.outcome is VerificationOutcome.DIGEST_MISMATCH

    @pytest.mark.parametrize(
        "arguments", [{"x": object()}, {"x": (1, 2)}, {"x": float("nan")}, {"x": b"b"}]
    )
    def test_unrepresentable_arguments_fail_closed(
        self, ledger: GrantLedger, arguments: dict[str, Any]
    ) -> None:
        result = _verify(ledger, arguments=arguments)
        assert result.outcome is VerificationOutcome.INVALID_ACTION_BINDING
        assert result.detail
        _still_consumable(ledger)


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class TestScope:
    def test_exact_scope_succeeds(self, ledger: GrantLedger) -> None:
        assert _verify(ledger).consumed

    def test_extra_grant_scope_accepted(self, db_path: Path) -> None:
        lg = _open(db_path)
        try:
            lg.record(_grant(scope=frozenset({P1, P2, P4})))
            assert _verify(lg).consumed
        finally:
            lg.disconnect()

    def test_partial_scope_fails_without_consuming(self, db_path: Path) -> None:
        impact = frozenset({P1, P4})
        action = {**ACTION, "impact": impact}
        lg = _open(db_path)
        try:
            lg.record(
                _grant(action_digest=compute_action_digest(**action), scope=frozenset({P4}))
            )
            result = _verify(lg, impact=impact)
            assert result.outcome is VerificationOutcome.INSUFFICIENT_SCOPE
            assert result.consumed is False
            # Widening the grant is impossible, so the proof it was not consumed
            # is that the ledger still reports it consumable directly.
            from telemachus.governance.grant_ledger import ConsumptionResult

            assert lg.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED
        finally:
            lg.disconnect()

    def test_empty_impact_is_covered_by_any_scope(self, db_path: Path) -> None:
        action = {**ACTION, "impact": frozenset()}
        for scope in (frozenset(), frozenset({P4})):
            path = db_path.parent / f"empty-{len(scope)}.db"
            lg = _open(path)
            try:
                lg.record(_grant(action_digest=compute_action_digest(**action), scope=scope))
                assert _verify(lg, impact=frozenset()).consumed
            finally:
                lg.disconnect()


# ---------------------------------------------------------------------------
# Temporal validity: invalid grants remain unconsumed
# ---------------------------------------------------------------------------


class TestValidity:
    def test_valid_at_issued_at(self, ledger: GrantLedger) -> None:
        assert _verify(ledger, now=100.0).consumed

    def test_invalid_before_issued_at(self, ledger: GrantLedger) -> None:
        assert _verify(ledger, now=99.999).outcome is VerificationOutcome.NOT_YET_VALID
        _still_consumable(ledger)

    def test_invalid_at_expires_at(self, ledger: GrantLedger) -> None:
        assert _verify(ledger, now=200.0).outcome is VerificationOutcome.EXPIRED
        _still_consumable(ledger)

    def test_valid_just_before_expires_at(self, ledger: GrantLedger) -> None:
        assert _verify(ledger, now=199.999).consumed

    def test_now_must_be_numeric(self, ledger: GrantLedger) -> None:
        with pytest.raises(TypeError):
            _verify(ledger, now="150")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ledger behaviour
# ---------------------------------------------------------------------------


class TestLedgerBehaviour:
    def test_unknown_grant_fails(self, ledger: GrantLedger) -> None:
        result = _verify(ledger, grant_id="missing")
        assert result.outcome is VerificationOutcome.GRANT_NOT_FOUND
        assert result.consumed is False

    def test_corrupt_record_fails_closed(self, ledger: GrantLedger, db_path: Path) -> None:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DROP TRIGGER authorization_grants_immutable")
            conn.execute("UPDATE authorization_grants SET scope = 'garbage'")
            conn.commit()
        finally:
            conn.close()
        result = _verify(ledger)
        assert result.outcome is VerificationOutcome.CORRUPT_RECORD
        assert result.consumed is False

    def test_database_failure_on_get_is_not_success(self, db_path: Path) -> None:
        lg = GrantLedger(db_path)  # never connected
        result = _verify(lg)
        assert result.outcome is VerificationOutcome.LEDGER_FAILURE
        assert result.consumed is False

    def test_database_failure_on_consume_is_not_success(
        self, ledger: GrantLedger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise GrantLedgerError("disk on fire")

        monkeypatch.setattr(ledger, "consume", _boom)
        result = _verify(ledger)
        assert result.outcome is VerificationOutcome.LEDGER_FAILURE
        assert "disk on fire" in result.detail
        assert result.consumed is False

    def test_two_verifiers_on_separate_ledgers_cannot_both_succeed(
        self, db_path: Path
    ) -> None:
        a = _open(db_path)
        b = _open(db_path)
        try:
            a.record(_grant())
            results = [_verify(a), _verify(b)]
        finally:
            a.disconnect()
            b.disconnect()
        assert [r.consumed for r in results].count(True) == 1
        assert VerificationOutcome.ALREADY_CONSUMED in [r.outcome for r in results]

    def test_concurrent_verification_consumes_exactly_once(self, db_path: Path) -> None:
        seed = _open(db_path)
        seed.record(_grant())
        seed.disconnect()

        workers = 8
        barrier = threading.Barrier(workers)
        outcomes: list[VerificationOutcome] = []
        lock = threading.Lock()

        def work() -> None:
            lg = _open(db_path)  # each thread owns its connection
            try:
                barrier.wait()
                outcome = _verify(lg).outcome
            finally:
                lg.disconnect()
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=work) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(outcomes) == workers
        assert outcomes.count(VerificationOutcome.MATCHED_AND_CONSUMED) == 1
        assert outcomes.count(VerificationOutcome.ALREADY_CONSUMED) == workers - 1


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_construction_and_recording_do_not_verify_or_consume(
        self, db_path: Path
    ) -> None:
        from telemachus.governance.grant_ledger import ConsumptionResult

        lg = _open(db_path)
        try:
            _grant()  # constructing verifies nothing
            lg.record(_grant())  # recording authenticates nothing
            assert lg.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED
        finally:
            lg.disconnect()

    def test_verifier_touches_no_authority_or_execution_code(
        self, ledger: GrantLedger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from telemachus.core.constitution import Constitution
        from telemachus.pipeline import CognitivePipeline
        from telemachus.tools.registry import ToolRegistry

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("verifier reached authority or execution code")

        monkeypatch.setattr(Constitution, "validate_action", _forbidden)
        monkeypatch.setattr(CognitivePipeline, "process", _forbidden)
        monkeypatch.setattr(ToolRegistry, "execute", _forbidden)
        assert _verify(ledger).consumed

    def test_module_imports_only_governance_primitives(self) -> None:
        source = (SRC_ROOT / "governance" / "grant_verifier.py").read_text(encoding="utf-8")
        modules: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
        assert {m for m in modules if m.startswith("telemachus")} == {
            "telemachus.core.codex",
            "telemachus.governance.authorization",
            "telemachus.governance.grant_ledger",
        }

    def test_no_production_module_uses_the_verifier(self) -> None:
        offenders = [
            str(p.relative_to(SRC_ROOT))
            for p in sorted(SRC_ROOT.rglob("*.py"))
            if p.name != "grant_verifier.py"
            and "grant_verifier" in p.read_text(encoding="utf-8")
        ]
        assert not offenders

    def test_public_surface_has_no_issuance_or_authentication(self) -> None:
        public = {name for name in dir(GrantVerifier) if not name.startswith("_")}
        assert public == {"verify_and_consume"}

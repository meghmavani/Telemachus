"""Tests for the authorization grant ledger (persistence only, GOV-ADR-001).

A recorded or consumed grant is not proof of authorization; these tests
cover storage, retrieval, single consumption, and fail-closed decoding.
"""

from __future__ import annotations

import ast
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import AuthorizationGrant, compute_action_digest
from telemachus.governance.grant_ledger import (
    ConsumptionResult,
    CorruptGrantRecordError,
    DuplicateGrantError,
    GrantLedger,
    GrantLedgerError,
)

P1 = ProtectedConstraint.CONSTITUTION_INTEGRITY
P4 = ProtectedConstraint.RESOURCE_AUTHORIZATION

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"

_DIGEST = compute_action_digest(
    tool_name="echo", tool_version="1.0.0", arguments={"text": "hi"}, impact=frozenset({P4})
)


def _grant(**overrides: Any) -> AuthorizationGrant:
    fields: dict[str, Any] = {
        "grant_id": "grant-1",
        "principal": "operator",
        "surface": "cli",
        "issued_at": 100.0,
        "expires_at": 200.0,
        "action_digest": _DIGEST,
        "scope": frozenset({P4, P1}),
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
    return tmp_path / "data" / "authorization.db"


@pytest.fixture
def ledger(db_path: Path) -> Generator[GrantLedger, None, None]:
    lg = _open(db_path)
    try:
        yield lg
    finally:
        lg.disconnect()


def _raw(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> None:
    """Write directly to the ledger file, bypassing the API, to simulate corruption."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TRIGGER IF EXISTS authorization_grants_immutable")
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _insert_raw(db_path: Path, **overrides: Any) -> None:
    row: dict[str, Any] = {
        "grant_id": "raw",
        "principal": "operator",
        "surface": "cli",
        "issued_at": 100.0,
        "expires_at": 200.0,
        "action_digest": _DIGEST,
        "scope": '["resource_authorization"]',
    }
    row.update(overrides)
    _raw(
        db_path,
        "INSERT INTO authorization_grants (grant_id, principal, surface, issued_at, "
        "expires_at, action_digest, scope) VALUES (?, ?, ?, ?, ?, ?, ?)",
        tuple(row.values()),
    )


# ---------------------------------------------------------------------------
# Recording and retrieval
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_round_trip_preserves_every_field(self, ledger: GrantLedger) -> None:
        grant = _grant(issued_at=1_700_000_000.123456, expires_at=1_700_000_600.654321)
        ledger.record(grant)
        loaded = ledger.get("grant-1")
        assert loaded == grant
        assert loaded is not grant

    def test_scope_reconstructed_as_enum_frozenset(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        loaded = ledger.get("grant-1")
        assert loaded is not None
        assert isinstance(loaded.scope, frozenset)
        assert loaded.scope == frozenset({P1, P4})
        assert all(isinstance(c, ProtectedConstraint) for c in loaded.scope)

    def test_empty_scope_round_trips(self, ledger: GrantLedger) -> None:
        ledger.record(_grant(scope=frozenset()))
        loaded = ledger.get("grant-1")
        assert loaded is not None and loaded.scope == frozenset()

    def test_scope_stored_canonically(self, ledger: GrantLedger, db_path: Path) -> None:
        ledger.record(_grant(scope=frozenset({P4, P1})))
        conn = sqlite3.connect(str(db_path))
        try:
            (scope,) = conn.execute("SELECT scope FROM authorization_grants").fetchone()
        finally:
            conn.close()
        assert scope == '["constitution_integrity","resource_authorization"]'

    def test_missing_grant_returns_none(self, ledger: GrantLedger) -> None:
        assert ledger.get("nope") is None

    def test_duplicate_id_does_not_overwrite(self, ledger: GrantLedger) -> None:
        original = _grant()
        ledger.record(original)
        with pytest.raises(DuplicateGrantError):
            ledger.record(_grant(principal="someone else", scope=frozenset({P1})))
        assert ledger.get("grant-1") == original

    def test_record_requires_grant_type(self, ledger: GrantLedger) -> None:
        with pytest.raises(TypeError):
            ledger.record({"grant_id": "x"})  # type: ignore[arg-type]

    def test_survives_reopen(self, db_path: Path) -> None:
        first = _open(db_path)
        first.record(_grant())
        first.disconnect()

        second = _open(db_path)
        try:
            assert second.get("grant-1") == _grant()
        finally:
            second.disconnect()

    def test_uses_only_its_own_database_file(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        ledger = _open(data / "authorization.db")
        ledger.record(_grant())
        ledger.disconnect()
        assert not (data / "telemachus.db").exists()
        assert not (data / "runtime.db").exists()

    def test_initialize_schema_is_idempotent(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        ledger.initialize_schema()
        assert ledger.get("grant-1") == _grant()


# ---------------------------------------------------------------------------
# Consumption
# ---------------------------------------------------------------------------


class TestConsume:
    def test_consumes_once(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        assert ledger.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED
        assert ledger.consume("grant-1", now=150.0) is ConsumptionResult.ALREADY_CONSUMED

    def test_consumption_survives_reopen(self, db_path: Path) -> None:
        first = _open(db_path)
        first.record(_grant())
        assert first.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED
        first.disconnect()

        second = _open(db_path)
        try:
            assert second.consume("grant-1", now=150.0) is ConsumptionResult.ALREADY_CONSUMED
        finally:
            second.disconnect()

    def test_not_consumable_before_issued_at(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        assert ledger.consume("grant-1", now=99.999) is ConsumptionResult.NOT_YET_VALID
        assert ledger.consume("grant-1", now=100.0) is ConsumptionResult.CONSUMED

    def test_not_consumable_at_expires_at(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        assert ledger.consume("grant-1", now=200.0) is ConsumptionResult.EXPIRED

    def test_consumable_just_before_expires_at(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        assert ledger.consume("grant-1", now=199.999) is ConsumptionResult.CONSUMED

    def test_rejected_attempts_do_not_consume(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        ledger.consume("grant-1", now=50.0)
        ledger.consume("grant-1", now=250.0)
        assert ledger.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED

    def test_unknown_grant(self, ledger: GrantLedger) -> None:
        assert ledger.consume("missing", now=150.0) is ConsumptionResult.UNKNOWN_GRANT

    def test_two_instances_cannot_both_consume(self, db_path: Path) -> None:
        a = _open(db_path)
        b = _open(db_path)
        try:
            a.record(_grant())
            results = [
                a.consume("grant-1", now=150.0),
                b.consume("grant-1", now=150.0),
            ]
        finally:
            a.disconnect()
            b.disconnect()
        assert results.count(ConsumptionResult.CONSUMED) == 1
        assert ConsumptionResult.ALREADY_CONSUMED in results

    def test_now_must_be_numeric(self, ledger: GrantLedger) -> None:
        ledger.record(_grant())
        with pytest.raises(TypeError):
            ledger.consume("grant-1", now="150")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestFailClosed:
    @pytest.mark.parametrize(
        "scope",
        [
            "not json",
            '{"a": 1}',
            '["not_a_constraint"]',
            "[1]",
            '["resource_authorization","constitution_integrity"]',  # non-canonical order
            '["resource_authorization","resource_authorization"]',
        ],
    )
    def test_malformed_scope_fails_clearly(
        self, ledger: GrantLedger, db_path: Path, scope: str
    ) -> None:
        _insert_raw(db_path, scope=scope)
        with pytest.raises(CorruptGrantRecordError):
            ledger.get("raw")
        with pytest.raises(CorruptGrantRecordError):
            ledger.consume("raw", now=150.0)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"principal": ""},
            {"action_digest": "short"},
            {"issued_at": 300.0},  # expiry not after issuance
            {"issued_at": "not-a-time"},  # REAL affinity cannot coerce this
            {"expires_at": bytes([0])},  # BLOB, not REAL
        ],
    )
    def test_malformed_grant_fails_closed(
        self, ledger: GrantLedger, db_path: Path, overrides: dict[str, Any]
    ) -> None:
        _insert_raw(db_path, **overrides)
        with pytest.raises(CorruptGrantRecordError):
            ledger.get("raw")
        with pytest.raises(CorruptGrantRecordError):
            ledger.consume("raw", now=150.0)

    def test_corrupt_record_is_not_consumed(self, ledger: GrantLedger, db_path: Path) -> None:
        _insert_raw(db_path, scope="garbage")
        with pytest.raises(CorruptGrantRecordError):
            ledger.consume("raw", now=150.0)
        conn = sqlite3.connect(str(db_path))
        try:
            (consumed,) = conn.execute(
                "SELECT consumed_at FROM authorization_grants WHERE grant_id = 'raw'"
            ).fetchone()
        finally:
            conn.close()
        assert consumed is None

    def test_database_error_is_not_success(self, ledger: GrantLedger, db_path: Path) -> None:
        ledger.record(_grant())
        _raw(db_path, "DROP TRIGGER IF EXISTS authorization_grants_no_delete")
        _raw(db_path, "DROP TABLE authorization_grants")
        with pytest.raises(GrantLedgerError):
            ledger.consume("grant-1", now=150.0)
        with pytest.raises(GrantLedgerError):
            ledger.get("grant-1")
        with pytest.raises(GrantLedgerError):
            ledger.record(_grant(grant_id="grant-2"))

    def test_operations_require_connection(self, db_path: Path) -> None:
        ledger = GrantLedger(db_path)
        with pytest.raises(GrantLedgerError):
            ledger.consume("grant-1", now=150.0)
        with pytest.raises(GrantLedgerError):
            ledger.get("grant-1")

    def test_database_rejects_field_mutation_and_deletion(
        self, ledger: GrantLedger, db_path: Path
    ) -> None:
        ledger.record(_grant())
        conn = sqlite3.connect(str(db_path))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("UPDATE authorization_grants SET scope = '[]'")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM authorization_grants")
        finally:
            conn.close()
        assert ledger.get("grant-1") == _grant()

    def test_database_rejects_unconsuming(self, ledger: GrantLedger, db_path: Path) -> None:
        ledger.record(_grant())
        ledger.consume("grant-1", now=150.0)
        conn = sqlite3.connect(str(db_path))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("UPDATE authorization_grants SET consumed_at = NULL")
        finally:
            conn.close()
        assert ledger.consume("grant-1", now=150.0) is ConsumptionResult.ALREADY_CONSUMED


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_ledger_operations_touch_no_governance_or_execution(
        self, ledger: GrantLedger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from telemachus.core.constitution import Constitution
        from telemachus.pipeline import CognitivePipeline
        from telemachus.tools.registry import ToolRegistry

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("ledger reached authority or execution code")

        monkeypatch.setattr(Constitution, "validate_action", _forbidden)
        monkeypatch.setattr(CognitivePipeline, "process", _forbidden)
        monkeypatch.setattr(ToolRegistry, "execute", _forbidden)

        ledger.record(_grant())
        assert ledger.get("grant-1") is not None
        assert ledger.consume("grant-1", now=150.0) is ConsumptionResult.CONSUMED

    def test_module_imports_no_authority_or_execution_code(self) -> None:
        source = (SRC_ROOT / "governance" / "grant_ledger.py").read_text(encoding="utf-8")
        modules: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
        assert {m for m in modules if m.startswith("telemachus")} == {
            "telemachus.core.codex",
            "telemachus.governance.authorization",
        }

    def test_ledger_has_no_issuance_or_authentication_api(self) -> None:
        public = {name for name in dir(GrantLedger) if not name.startswith("_")}
        assert public == {"connect", "disconnect", "initialize_schema", "record", "get", "consume"}

    def test_no_production_module_uses_the_ledger(self) -> None:
        offenders = [
            str(p.relative_to(SRC_ROOT))
            for p in sorted(SRC_ROOT.rglob("*.py"))
            if p.name != "grant_ledger.py"
            and "grant_ledger" in p.read_text(encoding="utf-8")
        ]
        assert not offenders

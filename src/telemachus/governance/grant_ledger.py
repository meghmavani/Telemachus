"""Durable ledger of authorization grants (GOV-ADR-001).

Stores ``AuthorizationGrant`` records in a dedicated SQLite file — never
``telemachus.db`` or ``runtime.db`` — and tracks single consumption.

This is persistence, not authority. A recorded grant is not proof that a
human approved anything: the ledger does not authenticate ``principal``
or ``surface``, does not check that a grant matches any action, and is
not consulted by the Constitution, Stage 6, or the tool registry. That
verification contract belongs to a later milestone. Likewise, a
successful ``consume()`` only means the grant was recorded, within its
validity window, and not previously consumed; the future verifier must
check the action digest and scope *before* consuming a grant for
execution.

Every write runs in an explicit ``BEGIN IMMEDIATE`` transaction, so two
ledger instances on the same file serialize their writes and a grant can
be consumed at most once.
"""

from __future__ import annotations

import json
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import AuthorizationGrant

_CONSTRAINT_ORDER: dict[ProtectedConstraint, int] = {
    c: i for i, c in enumerate(ProtectedConstraint)
}

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS authorization_grants (
        grant_id TEXT PRIMARY KEY NOT NULL,
        principal TEXT NOT NULL,
        surface TEXT NOT NULL,
        issued_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        action_digest TEXT NOT NULL,
        scope TEXT NOT NULL,
        consumed_at REAL
    )""",
    # A recorded grant's content never changes, and consumption is
    # one-way. Enforced in the database too, not only by this module's API.
    """CREATE TRIGGER IF NOT EXISTS authorization_grants_immutable
        BEFORE UPDATE ON authorization_grants
        WHEN NEW.grant_id IS NOT OLD.grant_id
          OR NEW.principal IS NOT OLD.principal
          OR NEW.surface IS NOT OLD.surface
          OR NEW.issued_at IS NOT OLD.issued_at
          OR NEW.expires_at IS NOT OLD.expires_at
          OR NEW.action_digest IS NOT OLD.action_digest
          OR NEW.scope IS NOT OLD.scope
          OR OLD.consumed_at IS NOT NULL
        BEGIN
            SELECT RAISE(ABORT, 'authorization grant records are immutable');
        END""",
    """CREATE TRIGGER IF NOT EXISTS authorization_grants_no_delete
        BEFORE DELETE ON authorization_grants
        BEGIN
            SELECT RAISE(ABORT, 'authorization grant records cannot be deleted');
        END""",
)

_COLUMNS = "grant_id, principal, surface, issued_at, expires_at, action_digest, scope"


class GrantLedgerError(RuntimeError):
    """The ledger is unavailable or a database operation failed."""


class DuplicateGrantError(GrantLedgerError):
    """A grant with this ``grant_id`` is already recorded; nothing was written."""


class CorruptGrantRecordError(GrantLedgerError):
    """A stored record cannot be decoded into a valid ``AuthorizationGrant``."""


class ConsumptionResult(Enum):
    """Outcome of ``GrantLedger.consume()``. Only ``CONSUMED`` is success."""

    CONSUMED = "consumed"
    UNKNOWN_GRANT = "unknown_grant"
    ALREADY_CONSUMED = "already_consumed"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"


def _encode_scope(scope: frozenset[ProtectedConstraint]) -> str:
    ordered = sorted(scope, key=lambda c: _CONSTRAINT_ORDER[c])
    return json.dumps([c.value for c in ordered], separators=(",", ":"))


def _decode_scope(raw: object, grant_id: str) -> frozenset[ProtectedConstraint]:
    """Strictly decode a stored scope; anything non-canonical is corruption."""
    if type(raw) is not str:
        raise CorruptGrantRecordError(f"grant {grant_id!r}: scope is not text")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorruptGrantRecordError(f"grant {grant_id!r}: scope is not JSON") from exc
    if type(values) is not list or not all(type(v) is str for v in values):
        raise CorruptGrantRecordError(f"grant {grant_id!r}: scope is not a list of strings")
    try:
        constraints = [ProtectedConstraint(v) for v in values]
    except ValueError as exc:
        raise CorruptGrantRecordError(
            f"grant {grant_id!r}: scope contains an unknown Protected Constraint"
        ) from exc
    scope = frozenset(constraints)
    if _encode_scope(scope) != raw:
        raise CorruptGrantRecordError(f"grant {grant_id!r}: scope is not canonically encoded")
    return scope


def _decode_row(row: tuple[Any, ...]) -> AuthorizationGrant:
    grant_id, principal, surface, issued_at, expires_at, action_digest, scope = row
    label = grant_id if type(grant_id) is str else repr(grant_id)
    for name, value in (("issued_at", issued_at), ("expires_at", expires_at)):
        if type(value) is not float:
            raise CorruptGrantRecordError(f"grant {label!r}: {name} is not a REAL")
    try:
        return AuthorizationGrant(
            grant_id=grant_id,
            principal=principal,
            surface=surface,
            issued_at=issued_at,
            expires_at=expires_at,
            action_digest=action_digest,
            scope=_decode_scope(scope, label),
        )
    except ValueError as exc:
        raise CorruptGrantRecordError(f"grant {label!r}: {exc}") from exc


class GrantLedger:
    """SQLite-backed record of authorization grants and their consumption.

    Usage::

        ledger = GrantLedger(path)
        ledger.connect()
        ledger.initialize_schema()
        ...
        ledger.disconnect()

    Attributes:
        db_path: Path to the dedicated ledger database file.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open the database in autocommit mode with WAL journaling.

        Autocommit (``isolation_level=None``) means every transaction is
        opened explicitly below; nothing is left implicitly open.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
            self._conn.execute("PRAGMA journal_mode=WAL")
        except (OSError, sqlite3.Error) as exc:
            self._conn = None
            raise GrantLedgerError(f"cannot open grant ledger at {self.db_path}: {exc}") from exc

    def disconnect(self) -> None:
        """Close the connection. Safe to call when not connected."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise GrantLedgerError("GrantLedger not connected. Call connect() first.")
        return self._conn

    def initialize_schema(self) -> None:
        """Create the grants table and integrity triggers if absent."""
        conn = self._require_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in _SCHEMA:
                conn.execute(statement)
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            self._rollback(conn)
            raise GrantLedgerError(f"cannot initialize grant ledger schema: {exc}") from exc

    @staticmethod
    def _rollback(conn: sqlite3.Connection) -> None:
        if conn.in_transaction:
            conn.execute("ROLLBACK")

    def record(self, grant: AuthorizationGrant) -> None:
        """Persist a grant record. Never overwrites.

        This is low-level storage, not issuance: it does not authenticate
        the grant's principal or surface, and recording a grant does not
        make it legitimate.

        Raises:
            DuplicateGrantError: If ``grant.grant_id`` is already recorded.
            GrantLedgerError: On any other database failure.
        """
        if not isinstance(grant, AuthorizationGrant):
            raise TypeError("record() requires an AuthorizationGrant")
        conn = self._require_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"INSERT INTO authorization_grants ({_COLUMNS}, consumed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    grant.grant_id,
                    grant.principal,
                    grant.surface,
                    float(grant.issued_at),
                    float(grant.expires_at),
                    grant.action_digest,
                    _encode_scope(grant.scope),
                ),
            )
            conn.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            self._rollback(conn)
            raise DuplicateGrantError(
                f"grant {grant.grant_id!r} is already recorded"
            ) from exc
        except sqlite3.Error as exc:
            self._rollback(conn)
            raise GrantLedgerError(f"cannot record grant {grant.grant_id!r}: {exc}") from exc

    def get(self, grant_id: str) -> AuthorizationGrant | None:
        """Return the recorded grant, or None if no such grant exists.

        A returned grant is a decoded record, not proof of authorization.

        Raises:
            CorruptGrantRecordError: If the stored record is malformed.
            GrantLedgerError: On any other database failure.
        """
        conn = self._require_conn()
        try:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM authorization_grants WHERE grant_id = ?",
                (grant_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise GrantLedgerError(f"cannot read grant {grant_id!r}: {exc}") from exc
        return None if row is None else _decode_row(row)

    def consume(self, grant_id: str, *, now: float) -> ConsumptionResult:
        """Mark a grant consumed, at most once, if valid at ``now``.

        A single conditional ``UPDATE`` inside a ``BEGIN IMMEDIATE``
        transaction performs the check and the write together, so there
        is no window between reading and writing. Validity is the
        half-open window ``issued_at <= now < expires_at``.

        This does **not** check that the grant matches any action; it
        must only be called after that check by a future verifier.

        Raises:
            CorruptGrantRecordError: If the stored record is malformed.
            GrantLedgerError: On any database failure (never reported as
                success).
        """
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("now must be a number (Unix time)")
        conn = self._require_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                f"SELECT {_COLUMNS}, consumed_at FROM authorization_grants WHERE grant_id = ?",
                (grant_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                return ConsumptionResult.UNKNOWN_GRANT
            # Never consume something that cannot be decoded as a grant.
            grant = _decode_row(row[:-1])
            if row[-1] is not None:
                conn.execute("ROLLBACK")
                return ConsumptionResult.ALREADY_CONSUMED
            if now < grant.issued_at:
                conn.execute("ROLLBACK")
                return ConsumptionResult.NOT_YET_VALID
            if not now < grant.expires_at:
                conn.execute("ROLLBACK")
                return ConsumptionResult.EXPIRED
            cursor = conn.execute(
                "UPDATE authorization_grants SET consumed_at = ? "
                "WHERE grant_id = ? AND consumed_at IS NULL "
                "AND issued_at <= ? AND ? < expires_at",
                (float(now), grant_id, float(now), float(now)),
            )
            if cursor.rowcount != 1:
                conn.execute("ROLLBACK")
                raise GrantLedgerError(
                    f"grant {grant_id!r}: consumption update affected {cursor.rowcount} rows"
                )
            conn.execute("COMMIT")
            return ConsumptionResult.CONSUMED
        except CorruptGrantRecordError:
            self._rollback(conn)
            raise
        except sqlite3.Error as exc:
            self._rollback(conn)
            raise GrantLedgerError(f"cannot consume grant {grant_id!r}: {exc}") from exc

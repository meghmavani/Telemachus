"""SQLite-backed persistence for Runtime lifecycle and session state.

Owns ``runtime.db`` exclusively — a database entirely separate from
``telemachus.db``. This separation exists so that crash detection and
installation bookkeeping never depend on the health of the Core memory
store: if ``telemachus.db`` is corrupt or unopenable, the Runtime must
still be able to record that it crashed and report why (docs/lifecycle.md,
ADR-002).

Crash detection derives entirely from the session record: a session that
never reaches a clean close leaves ``ended_at`` NULL and
``clean_shutdown = 0``. There are no heartbeats and no timers here.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from telemachus.runtime.records import InstallationRecord, SessionRecord


class RuntimeStateStore:
    """SQLite-backed store for the Runtime's own operational state.

    Manages exactly two record categories: a single write-once
    InstallationRecord, and one SessionRecord per Runtime process
    lifetime. This store knows nothing about Core memory, identity, or
    reasoning — only about whether this installation has run before and
    how its last run ended.

    Attributes:
        db_path: Path to the SQLite database file (runtime.db).
        conn: The active sqlite3 connection (None if not connected).
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open the database connection and enable WAL mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")

    def disconnect(self) -> None:
        """Close the database connection cleanly."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def initialize_schema(self) -> None:
        """Create the installation and sessions tables if they do not exist.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS installation (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                instance_id TEXT NOT NULL,
                installed_at REAL NOT NULL,
                schema_version INTEGER NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                started_at REAL NOT NULL,
                ended_at REAL,
                clean_shutdown INTEGER NOT NULL DEFAULT 0,
                last_state TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_sessions_started
               ON sessions(started_at)"""
        )
        conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        """Return the live connection, or fail with a consistent message.

        Returns:
            The open sqlite3 connection.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.conn is None:
            raise RuntimeError("RuntimeStateStore not connected. Call connect() first.")
        return self.conn

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def read_installation(self) -> InstallationRecord | None:
        """Return the installation record, or None if this is a new installation.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        row = conn.execute(
            "SELECT instance_id, installed_at, schema_version FROM installation WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return InstallationRecord(
            instance_id=row[0], installed_at=row[1], schema_version=row[2]
        )

    def create_installation_if_absent(self, instance_id: str) -> InstallationRecord:
        """Write the installation record if none exists yet.

        Idempotent: if an installation record already exists, it is
        returned unchanged rather than overwritten. Installation metadata
        is written once and is never rewritten (ADR-002).

        Args:
            instance_id: The identifier to use if this is a new installation.

        Returns:
            The InstallationRecord now on disk — either the one just
            created, or a pre-existing one.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        conn.execute(
            """INSERT OR IGNORE INTO installation
               (id, instance_id, installed_at, schema_version)
               VALUES (1, ?, ?, ?)""",
            (instance_id, time.time(), self.SCHEMA_VERSION),
        )
        conn.commit()
        installation = self.read_installation()
        if installation is None:  # pragma: no cover — INSERT OR IGNORE guarantees a row
            raise RuntimeError("Installation record missing immediately after write")
        return installation

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def get_most_recent_session(self) -> SessionRecord | None:
        """Return the most recently started session, or None if none exists.

        Call this before opening a new session — it answers "how did the
        previous run end", which is the entire mechanism behind crash
        detection. No heartbeats, no timers: a session that never reached
        a clean close simply has ``ended_at IS NULL`` or
        ``clean_shutdown = 0``.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        row = conn.execute(
            """SELECT session_id, pid, started_at, ended_at, clean_shutdown, last_state
               FROM sessions ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def open_session(self, session_id: str, pid: int, initial_state: str) -> SessionRecord:
        """Create a new session row.

        Written with ``clean_shutdown = 0`` immediately, before any further
        startup work proceeds — so a crash anywhere after this call
        (including during Core bootstrap) is correctly detected on the
        next start.

        Args:
            session_id: A stable identifier for this process's run.
            pid: The current process ID.
            initial_state: The name of the lifecycle state at open time.

        Returns:
            The newly created SessionRecord.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        started_at = time.time()
        conn.execute(
            """INSERT INTO sessions
               (session_id, pid, started_at, ended_at, clean_shutdown, last_state)
               VALUES (?, ?, ?, NULL, 0, ?)""",
            (session_id, pid, started_at, initial_state),
        )
        conn.commit()
        return SessionRecord(
            session_id=session_id,
            pid=pid,
            started_at=started_at,
            ended_at=None,
            clean_shutdown=False,
            last_state=initial_state,
        )

    def update_session_state(self, session_id: str, state: str) -> None:
        """Record the current lifecycle state for an open session.

        Called on every transition so that an unclean session's
        ``last_state`` names the phase it died in.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        conn.execute(
            "UPDATE sessions SET last_state = ? WHERE session_id = ?",
            (state, session_id),
        )
        conn.commit()

    def close_session(self, session_id: str, *, clean_shutdown: bool) -> None:
        """Mark a session as ended.

        Args:
            session_id: The session to close.
            clean_shutdown: Whether the full shutdown sequence completed
                successfully. Callers must derive this from what actually
                happened during shutdown, not assume it.

        Raises:
            RuntimeError: If not connected.
        """
        conn = self._require_conn()
        conn.execute(
            "UPDATE sessions SET ended_at = ?, clean_shutdown = ? WHERE session_id = ?",
            (time.time(), 1 if clean_shutdown else 0, session_id),
        )
        conn.commit()

    @staticmethod
    def _row_to_session(row: tuple[Any, ...]) -> SessionRecord:
        return SessionRecord(
            session_id=row[0],
            pid=row[1],
            started_at=row[2],
            ended_at=row[3],
            clean_shutdown=bool(row[4]),
            last_state=row[5],
        )

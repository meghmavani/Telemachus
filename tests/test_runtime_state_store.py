"""Tests for RuntimeStateStore — runtime.db persistence."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from telemachus.runtime.state_store import RuntimeStateStore


@pytest.fixture
def store(temp_dir: Path) -> Generator[RuntimeStateStore, None, None]:
    """A connected, schema-initialized RuntimeStateStore over a temp file."""
    s = RuntimeStateStore(temp_dir / "runtime.db")
    s.connect()
    s.initialize_schema()
    try:
        yield s
    finally:
        s.disconnect()


class TestSchema:
    def test_initialize_schema_is_idempotent(self, temp_dir: Path) -> None:
        s = RuntimeStateStore(temp_dir / "runtime.db")
        s.connect()
        s.initialize_schema()
        s.initialize_schema()  # must not raise
        s.disconnect()

    def test_operations_require_connection(self, temp_dir: Path) -> None:
        s = RuntimeStateStore(temp_dir / "runtime.db")
        with pytest.raises(RuntimeError, match="not connected"):
            s.read_installation()

    def test_schema_version_constant(self) -> None:
        assert RuntimeStateStore.SCHEMA_VERSION == 1


class TestInstallation:
    def test_read_installation_absent_returns_none(self, store: RuntimeStateStore) -> None:
        assert store.read_installation() is None

    def test_create_installation_writes_record(self, store: RuntimeStateStore) -> None:
        record = store.create_installation_if_absent("inst-abc")
        assert record.instance_id == "inst-abc"
        assert record.installed_at > 0
        assert record.schema_version == RuntimeStateStore.SCHEMA_VERSION

    def test_installation_persists_across_reconnect(self, temp_dir: Path) -> None:
        db_path = temp_dir / "runtime.db"

        s1 = RuntimeStateStore(db_path)
        s1.connect()
        s1.initialize_schema()
        original = s1.create_installation_if_absent("inst-first")
        s1.disconnect()

        s2 = RuntimeStateStore(db_path)
        s2.connect()
        s2.initialize_schema()
        reread = s2.read_installation()
        s2.disconnect()

        assert reread == original

    def test_installation_is_written_once_not_rewritten(
        self, store: RuntimeStateStore
    ) -> None:
        """Installation metadata must not change on a second call."""
        first = store.create_installation_if_absent("inst-one")
        second = store.create_installation_if_absent("inst-two")

        assert second == first
        assert second.instance_id == "inst-one"  # the second id is discarded


class TestSessions:
    def test_no_sessions_returns_none(self, store: RuntimeStateStore) -> None:
        assert store.get_most_recent_session() is None

    def test_open_session_creates_unclean_row_immediately(
        self, store: RuntimeStateStore
    ) -> None:
        session = store.open_session("sess-1", pid=1234, initial_state="RECOVERY")
        assert session.session_id == "sess-1"
        assert session.pid == 1234
        assert session.ended_at is None
        assert session.clean_shutdown is False
        assert session.last_state == "RECOVERY"

    def test_get_most_recent_session_returns_latest(self, store: RuntimeStateStore) -> None:
        store.open_session("sess-1", pid=1, initial_state="RECOVERY")
        store.open_session("sess-2", pid=2, initial_state="RECOVERY")

        latest = store.get_most_recent_session()
        assert latest is not None
        assert latest.session_id == "sess-2"

    def test_update_session_state_changes_last_state(self, store: RuntimeStateStore) -> None:
        store.open_session("sess-1", pid=1, initial_state="RECOVERY")
        store.update_session_state("sess-1", "RECONCILIATION")

        latest = store.get_most_recent_session()
        assert latest is not None
        assert latest.last_state == "RECONCILIATION"

    def test_close_session_records_clean_shutdown_true(
        self, store: RuntimeStateStore
    ) -> None:
        store.open_session("sess-1", pid=1, initial_state="RUNNING")
        store.close_session("sess-1", clean_shutdown=True)

        latest = store.get_most_recent_session()
        assert latest is not None
        assert latest.clean_shutdown is True
        assert latest.ended_at is not None

    def test_close_session_records_clean_shutdown_false(
        self, store: RuntimeStateStore
    ) -> None:
        store.open_session("sess-1", pid=1, initial_state="RUNNING")
        store.close_session("sess-1", clean_shutdown=False)

        latest = store.get_most_recent_session()
        assert latest is not None
        assert latest.clean_shutdown is False
        # ended_at is still set — closing recorded that shutdown ran,
        # even though the memory store failed to disconnect cleanly.
        assert latest.ended_at is not None

    def test_abandoned_session_is_detectable_as_unclean(
        self, store: RuntimeStateStore
    ) -> None:
        """A session that is never closed looks exactly like a crash."""
        store.open_session("sess-crashed", pid=1, initial_state="RUNNING")
        # No close_session() call — simulates a killed process.

        latest = store.get_most_recent_session()
        assert latest is not None
        assert latest.ended_at is None
        assert latest.clean_shutdown is False

    def test_sessions_persist_across_reconnect(self, temp_dir: Path) -> None:
        db_path = temp_dir / "runtime.db"

        s1 = RuntimeStateStore(db_path)
        s1.connect()
        s1.initialize_schema()
        s1.open_session("sess-1", pid=1, initial_state="RUNNING")
        s1.close_session("sess-1", clean_shutdown=True)
        s1.disconnect()

        s2 = RuntimeStateStore(db_path)
        s2.connect()
        s2.initialize_schema()
        latest = s2.get_most_recent_session()
        s2.disconnect()

        assert latest is not None
        assert latest.session_id == "sess-1"
        assert latest.clean_shutdown is True

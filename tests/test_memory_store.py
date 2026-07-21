"""Tests for the MemoryStore — SQLite-backed memory persistence."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from telemachus.core.types import MemoryDomain
from telemachus.memory.store import MemoryStore


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_memory.db"


@pytest.fixture
def store(temp_db_path: Path) -> MemoryStore:
    """Create a connected and initialized MemoryStore."""
    s = MemoryStore(temp_db_path)
    s.connect()
    s.initialize_schema()
    yield s
    s.disconnect()


class TestMemoryStoreConnection:
    """Tests for connection management."""

    def test_connect_creates_db_file(self, temp_db_path: Path) -> None:
        """Connecting should create the database file."""
        s = MemoryStore(temp_db_path)
        assert not temp_db_path.exists()
        s.connect()
        assert temp_db_path.exists()
        s.disconnect()

    def test_disconnect_closes_connection(self, store: MemoryStore) -> None:
        """Disconnecting should set conn to None."""
        store.disconnect()
        assert store.conn is None

    def test_initialize_schema_creates_tables(self, store: MemoryStore) -> None:
        """Schema initialization should create all required tables."""
        tables = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row[0] for row in tables}

        assert "schema_version" in table_names
        assert "unified_index" in table_names
        assert "memory_versions" in table_names
        for domain in MemoryDomain:
            assert f"memory_entries_{domain.value}" in table_names

    def test_initialize_schema_is_idempotent(self, store: MemoryStore) -> None:
        """Calling initialize_schema twice should not raise."""
        store.initialize_schema()  # Should not raise

    def test_operation_without_connect_raises(self, temp_db_path: Path) -> None:
        """Operations before connect should raise RuntimeError."""
        s = MemoryStore(temp_db_path)
        with pytest.raises(RuntimeError, match="not connected"):
            s.store(MemoryDomain.WORLD, "test")


class TestMemoryStoreCRUD:
    """Tests for create, read, update, deactivate operations."""

    def test_store_returns_entry_id(self, store: MemoryStore) -> None:
        """Storing an entry should return a positive entry_id."""
        entry_id = store.store(MemoryDomain.WORLD, "Test content")
        assert entry_id > 0

    def test_store_and_retrieve(self, store: MemoryStore) -> None:
        """Stored entry should be retrievable."""
        entry_id = store.store(
            MemoryDomain.PROJECT,
            "Project Alpha design",
            metadata={"status": "active"},
            importance=0.8,
        )
        entry = store.retrieve(MemoryDomain.PROJECT, entry_id)
        assert entry is not None
        assert entry["content"] == "Project Alpha design"
        assert entry["metadata"]["status"] == "active"
        assert entry["importance"] == 0.8
        assert entry["is_active"] is True
        assert entry["current_version"] == 1

    def test_retrieve_nonexistent_returns_none(self, store: MemoryStore) -> None:
        """Retrieving a nonexistent entry should return None."""
        assert store.retrieve(MemoryDomain.WORLD, 99999) is None

    def test_update_changes_content(self, store: MemoryStore) -> None:
        """Updating an entry should change content and increment version."""
        entry_id = store.store(MemoryDomain.WORLD, "Original")
        result = store.update(MemoryDomain.WORLD, entry_id, "Updated")
        assert result is True

        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["content"] == "Updated"
        assert entry["current_version"] == 2

    def test_update_nonexistent_returns_false(self, store: MemoryStore) -> None:
        """Updating a nonexistent entry should return False."""
        assert store.update(MemoryDomain.WORLD, 99999, "content") is False

    def test_update_merges_metadata(self, store: MemoryStore) -> None:
        """Updating metadata should merge with existing."""
        entry_id = store.store(MemoryDomain.WORLD, "content", metadata={"a": 1, "b": 2})
        store.update(MemoryDomain.WORLD, entry_id, "content", metadata={"b": 3, "c": 4})
        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["metadata"] == {"a": 1, "b": 3, "c": 4}

    def test_deactivate_marks_inactive(self, store: MemoryStore) -> None:
        """Deactivating should set is_active to False."""
        entry_id = store.store(MemoryDomain.WORLD, "To deactivate")
        result = store.deactivate(MemoryDomain.WORLD, entry_id)
        assert result is True

        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["is_active"] is False

    def test_deactivate_nonexistent_returns_false(self, store: MemoryStore) -> None:
        """Deactivating nonexistent entry should return False."""
        assert store.deactivate(MemoryDomain.WORLD, 99999) is False

    def test_store_across_all_domains(self, store: MemoryStore) -> None:
        """Should be able to store in all 6 domains."""
        for domain in MemoryDomain:
            entry_id = store.store(domain, f"Content for {domain.value}")
            assert entry_id > 0
            entry = store.retrieve(domain, entry_id)
            assert entry is not None
            assert entry["content"] == f"Content for {domain.value}"


class TestMemoryStoreQuery:
    """Tests for querying and counting."""

    def test_query_returns_active_entries(self, store: MemoryStore) -> None:
        """Query should return only active entries by default."""
        store.store(MemoryDomain.WORLD, "active 1")
        eid = store.store(MemoryDomain.WORLD, "will be inactive")
        store.store(MemoryDomain.WORLD, "active 2")
        store.deactivate(MemoryDomain.WORLD, eid)

        results = store.query(MemoryDomain.WORLD)
        assert len(results) == 2
        assert all(r["is_active"] for r in results)

    def test_query_with_min_importance(self, store: MemoryStore) -> None:
        """Query should filter by minimum importance."""
        store.store(MemoryDomain.WORLD, "low", importance=0.3)
        store.store(MemoryDomain.WORLD, "high", importance=0.9)

        results = store.query(MemoryDomain.WORLD, min_importance=0.7)
        assert len(results) == 1
        assert results[0]["content"] == "high"

    def test_query_pagination(self, store: MemoryStore) -> None:
        """Query should support limit and offset."""
        for i in range(5):
            store.store(MemoryDomain.WORLD, f"entry {i}")

        results = store.query(MemoryDomain.WORLD, limit=2, offset=1)
        assert len(results) == 2

    def test_count_active(self, store: MemoryStore) -> None:
        """Count should return number of active entries."""
        assert store.count(MemoryDomain.WORLD) == 0
        store.store(MemoryDomain.WORLD, "a")
        store.store(MemoryDomain.WORLD, "b")
        assert store.count(MemoryDomain.WORLD) == 2

    def test_count_includes_inactive(self, store: MemoryStore) -> None:
        """Count with active_only=False should include inactive."""
        eid = store.store(MemoryDomain.WORLD, "a")
        store.deactivate(MemoryDomain.WORLD, eid)
        assert store.count(MemoryDomain.WORLD, active_only=True) == 0
        assert store.count(MemoryDomain.WORLD, active_only=False) == 1


class TestMemoryStoreIndex:
    """Tests for unified index operations."""

    def test_store_with_index_keys(self, store: MemoryStore) -> None:
        """Storing with index_keys should create index entries."""
        entry_id = store.store(
            MemoryDomain.PROJECT,
            "Project X",
            index_keys={"project": "x", "status": "active"},
        )
        results = store.search_index("project", "x")
        assert len(results) == 1
        assert results[0]["entry_id"] == entry_id
        assert results[0]["domain"] == MemoryDomain.PROJECT.value

    def test_search_index_by_key_only(self, store: MemoryStore) -> None:
        """Searching by key only should return all matching entries."""
        store.store(MemoryDomain.WORLD, "a", index_keys={"tag": "alpha"})
        store.store(MemoryDomain.WORLD, "b", index_keys={"tag": "beta"})

        results = store.search_index("tag")
        assert len(results) == 2

    def test_search_index_no_match(self, store: MemoryStore) -> None:
        """Searching for nonexistent key should return empty."""
        results = store.search_index("nonexistent")
        assert results == []


class TestMemoryStoreVersionHistory:
    """Tests for version history retrieval."""

    def test_get_version_history_empty(self, store: MemoryStore) -> None:
        """New entry should have no version history."""
        entry_id = store.store(MemoryDomain.WORLD, "content")
        history = store.get_version_history(MemoryDomain.WORLD, entry_id)
        assert history == []

    def test_get_version_history_after_archive(self, store: MemoryStore) -> None:
        """After archiving, version history should have entries."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")
        now = time.time()
        store.conn.execute(
            """INSERT INTO memory_versions
               (entry_id, domain, version_number, content, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry_id, "world", 1, "v1", "{}", now),
        )
        store.conn.commit()

        history = store.get_version_history(MemoryDomain.WORLD, entry_id)
        assert len(history) == 1
        assert history[0]["content"] == "v1"
        assert history[0]["version_number"] == 1

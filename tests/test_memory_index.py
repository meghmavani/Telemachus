"""Tests for the MemoryIndex — cross-domain semantic index."""

from __future__ import annotations

from pathlib import Path

import pytest

from telemachus.core.types import MemoryDomain
from telemachus.memory.index import MemoryIndex
from telemachus.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    """Create a connected and initialized MemoryStore."""
    s = MemoryStore(tmp_path / "test_idx.db")
    s.connect()
    s.initialize_schema()
    yield s
    s.disconnect()


@pytest.fixture
def index(store: MemoryStore) -> MemoryIndex:
    """Create a MemoryIndex backed by the store."""
    return MemoryIndex(store)


class TestMemoryIndexEntry:
    """Tests for indexing individual entries."""

    def test_index_entry_adds_keys(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Indexing an entry should add keys to unified_index."""
        entry_id = store.store(MemoryDomain.PROJECT, "Project content")
        index.index_entry(
            MemoryDomain.PROJECT,
            entry_id,
            {"project": "alpha", "status": "active"},
        )

        keys = index.get_keys_for_entry(MemoryDomain.PROJECT, entry_id)
        assert keys == {"project": "alpha", "status": "active"}

    def test_index_entry_multiple_entries(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Multiple entries can be indexed independently."""
        e1 = store.store(MemoryDomain.WORLD, "entry 1")
        e2 = store.store(MemoryDomain.WORLD, "entry 2")

        index.index_entry(MemoryDomain.WORLD, e1, {"tag": "one"})
        index.index_entry(MemoryDomain.WORLD, e2, {"tag": "two"})

        assert index.get_keys_for_entry(MemoryDomain.WORLD, e1) == {"tag": "one"}
        assert index.get_keys_for_entry(MemoryDomain.WORLD, e2) == {"tag": "two"}

    def test_remove_entry_index(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Removing index entries should clear them."""
        entry_id = store.store(MemoryDomain.WORLD, "content")
        index.index_entry(MemoryDomain.WORLD, entry_id, {"key": "value"})

        removed = index.remove_entry_index(MemoryDomain.WORLD, entry_id)
        assert removed == 1
        assert index.get_keys_for_entry(MemoryDomain.WORLD, entry_id) == {}

    def test_remove_entry_index_nonexistent(self, index: MemoryIndex) -> None:
        """Removing index for nonexistent entry should return 0."""
        assert index.remove_entry_index(MemoryDomain.WORLD, 99999) == 0


class TestMemoryIndexSearch:
    """Tests for searching the index."""

    def test_find_by_key_exact_match(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Finding by key and value should return exact matches."""
        e1 = store.store(MemoryDomain.PROJECT, "Project A")
        e2 = store.store(MemoryDomain.PROJECT, "Project B")

        index.index_entry(MemoryDomain.PROJECT, e1, {"project": "alpha"})
        index.index_entry(MemoryDomain.PROJECT, e2, {"project": "beta"})

        results = index.find_by_key("project", "alpha")
        assert len(results) == 1
        assert results[0]["entry_id"] == e1

    def test_find_by_key_only(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Finding by key only should return all entries with that key."""
        e1 = store.store(MemoryDomain.WORLD, "a")
        e2 = store.store(MemoryDomain.WORLD, "b")

        index.index_entry(MemoryDomain.WORLD, e1, {"tag": "x"})
        index.index_entry(MemoryDomain.WORLD, e2, {"tag": "y"})

        results = index.find_by_key("tag")
        assert len(results) == 2

    def test_find_by_key_no_match(self, index: MemoryIndex) -> None:
        """Searching for nonexistent key should return empty."""
        assert index.find_by_key("nonexistent") == []


class TestMemoryIndexRelations:
    """Tests for cross-domain relationship discovery."""

    def test_find_related_same_key(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Entries sharing index keys should be found as related."""
        e1 = store.store(MemoryDomain.PROJECT, "Project X")
        e2 = store.store(MemoryDomain.WORLD, "World fact about X")

        index.index_entry(MemoryDomain.PROJECT, e1, {"topic": "x"})
        index.index_entry(MemoryDomain.WORLD, e2, {"topic": "x"})

        related = index.find_related(MemoryDomain.PROJECT, e1)
        assert len(related) >= 1
        # Check by (entry_id, domain) pair since IDs may overlap across domains
        related_pairs = {(r["entry_id"], r["domain"]) for r in related}
        assert (e2, MemoryDomain.WORLD.value) in related_pairs
        assert (e1, MemoryDomain.PROJECT.value) not in related_pairs  # Should exclude self

    def test_find_related_no_shared_keys(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Entries with no shared keys should have no relations."""
        e1 = store.store(MemoryDomain.PROJECT, "Project A")
        e2 = store.store(MemoryDomain.WORLD, "World fact B")

        index.index_entry(MemoryDomain.PROJECT, e1, {"topic": "a"})
        index.index_entry(MemoryDomain.WORLD, e2, {"topic": "b"})

        related = index.find_related(MemoryDomain.PROJECT, e1)
        assert related == []

    def test_find_related_cross_domain(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Relations should be discoverable across different domains."""
        e1 = store.store(MemoryDomain.REVAN, "Revan preference")
        e2 = store.store(MemoryDomain.PROJECT, "Project influenced by preference")
        e3 = store.store(MemoryDomain.REFLECTION, "Reflection on preference")

        index.index_entry(MemoryDomain.REVAN, e1, {"concept": "privacy"})
        index.index_entry(MemoryDomain.PROJECT, e2, {"concept": "privacy"})
        index.index_entry(MemoryDomain.REFLECTION, e3, {"concept": "privacy"})

        related = index.find_related(MemoryDomain.REVAN, e1)
        related_entry_ids = {r["entry_id"] for r in related}
        assert e2 in related_entry_ids
        assert e3 in related_entry_ids


class TestMemoryIndexStats:
    """Tests for index statistics."""

    def test_get_all_keys(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Should return all distinct keys across domains."""
        e1 = store.store(MemoryDomain.WORLD, "a")
        e2 = store.store(MemoryDomain.PROJECT, "b")

        index.index_entry(MemoryDomain.WORLD, e1, {"tag": "x", "type": "fact"})
        index.index_entry(MemoryDomain.PROJECT, e2, {"project": "y", "tag": "z"})

        keys = index.get_all_keys()
        assert "tag" in keys
        assert "type" in keys
        assert "project" in keys
        assert len(keys) == 3

    def test_get_all_keys_empty(self, index: MemoryIndex) -> None:
        """Empty index should return empty list."""
        assert index.get_all_keys() == []

    def test_get_domain_index_stats(self, store: MemoryStore, index: MemoryIndex) -> None:
        """Should return correct stats for a domain."""
        e1 = store.store(MemoryDomain.WORLD, "a")
        e2 = store.store(MemoryDomain.WORLD, "b")

        index.index_entry(MemoryDomain.WORLD, e1, {"k1": "v1", "k2": "v2"})
        index.index_entry(MemoryDomain.WORLD, e2, {"k1": "v3"})

        stats = index.get_domain_index_stats(MemoryDomain.WORLD)
        assert stats["indexed_entries"] == 2
        assert stats["total_keys"] == 3

    def test_get_domain_index_stats_empty(self, index: MemoryIndex) -> None:
        """Domain with no indexed entries should return zeros."""
        stats = index.get_domain_index_stats(MemoryDomain.TOOL)
        assert stats["indexed_entries"] == 0
        assert stats["total_keys"] == 0

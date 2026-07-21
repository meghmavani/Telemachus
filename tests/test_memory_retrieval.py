"""Tests for the MemoryRetrieval — context-aware retrieval engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from telemachus.core.types import MemoryDomain
from telemachus.memory.index import MemoryIndex
from telemachus.memory.retrieval import MemoryRetrieval
from telemachus.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    """Create a connected and initialized MemoryStore."""
    s = MemoryStore(tmp_path / "test_ret.db")
    s.connect()
    s.initialize_schema()
    yield s
    s.disconnect()


@pytest.fixture
def retrieval(store: MemoryStore) -> MemoryRetrieval:
    """Create a MemoryRetrieval backed by the store."""
    return MemoryRetrieval(store)


@pytest.fixture
def index(store: MemoryStore) -> MemoryIndex:
    """Create a MemoryIndex backed by the store."""
    return MemoryIndex(store)


class TestRetrievalByDomain:
    """Tests for single-domain retrieval."""

    def test_retrieve_by_domain_returns_entries(self, retrieval: MemoryRetrieval) -> None:
        """Should return entries from the specified domain."""
        retrieval.store.store(MemoryDomain.WORLD, "entry 1")
        retrieval.store.store(MemoryDomain.WORLD, "entry 2")

        results = retrieval.retrieve_by_domain(MemoryDomain.WORLD)
        assert len(results) == 2

    def test_retrieve_by_domain_excludes_inactive(self, retrieval: MemoryRetrieval) -> None:
        """Should exclude inactive entries by default."""
        eid = retrieval.store.store(MemoryDomain.WORLD, "inactive")
        retrieval.store.deactivate(MemoryDomain.WORLD, eid)

        results = retrieval.retrieve_by_domain(MemoryDomain.WORLD)
        assert len(results) == 0

    def test_retrieve_by_domain_respects_limit(self, retrieval: MemoryRetrieval) -> None:
        """Should respect the limit parameter."""
        for i in range(10):
            retrieval.store.store(MemoryDomain.WORLD, f"entry {i}")

        results = retrieval.retrieve_by_domain(MemoryDomain.WORLD, limit=3)
        assert len(results) == 3


class TestRetrievalImportant:
    """Tests for importance-based retrieval."""

    def test_retrieve_important_filters_by_threshold(self, retrieval: MemoryRetrieval) -> None:
        """Should only return entries above the importance threshold."""
        retrieval.store.store(MemoryDomain.PROJECT, "low", importance=0.2)
        retrieval.store.store(MemoryDomain.PROJECT, "medium", importance=0.5)
        retrieval.store.store(MemoryDomain.PROJECT, "high", importance=0.9)

        results = retrieval.retrieve_important(MemoryDomain.PROJECT, threshold=0.7)
        assert len(results) == 1
        assert results[0]["content"] == "high"

    def test_retrieve_important_sorted_by_importance(self, retrieval: MemoryRetrieval) -> None:
        """Results should be sorted by importance descending."""
        retrieval.store.store(MemoryDomain.WORLD, "a", importance=0.6)
        retrieval.store.store(MemoryDomain.WORLD, "b", importance=0.9)
        retrieval.store.store(MemoryDomain.WORLD, "c", importance=0.3)

        results = retrieval.retrieve_important(MemoryDomain.WORLD, threshold=0.0)
        assert results[0]["importance"] >= results[1]["importance"]
        assert results[1]["importance"] >= results[2]["importance"]


class TestRetrievalRecent:
    """Tests for temporal retrieval."""

    def test_retrieve_recent_newest_first(self, retrieval: MemoryRetrieval) -> None:
        """Should return entries sorted by created_at descending."""
        retrieval.store.store(MemoryDomain.WORLD, "older")
        retrieval.store.store(MemoryDomain.WORLD, "newer")

        results = retrieval.retrieve_recent(MemoryDomain.WORLD)
        assert len(results) == 2
        assert results[0]["created_at"] >= results[1]["created_at"]

    def test_retrieve_recent_respects_limit(self, retrieval: MemoryRetrieval) -> None:
        """Should respect the limit parameter."""
        for i in range(5):
            retrieval.store.store(MemoryDomain.WORLD, f"entry {i}")

        results = retrieval.retrieve_recent(MemoryDomain.WORLD, limit=2)
        assert len(results) == 2


class TestRetrievalCrossDomain:
    """Tests for cross-domain retrieval."""

    def test_retrieve_cross_domain_all_domains(self, retrieval: MemoryRetrieval) -> None:
        """Should return entries from all domains."""
        retrieval.store.store(MemoryDomain.REVAN, "revan entry")
        retrieval.store.store(MemoryDomain.PROJECT, "project entry")
        retrieval.store.store(MemoryDomain.WORLD, "world entry")

        results = retrieval.retrieve_cross_domain()
        assert len(results) == 3
        domains = {r["domain"] for r in results}
        assert MemoryDomain.REVAN in domains
        assert MemoryDomain.PROJECT in domains
        assert MemoryDomain.WORLD in domains

    def test_retrieve_cross_domain_specific_domains(self, retrieval: MemoryRetrieval) -> None:
        """Should only query specified domains."""
        retrieval.store.store(MemoryDomain.REVAN, "revan")
        retrieval.store.store(MemoryDomain.TOOL, "tool")
        retrieval.store.store(MemoryDomain.WORLD, "world")

        results = retrieval.retrieve_cross_domain(domains=[MemoryDomain.REVAN, MemoryDomain.TOOL])
        domains = {r["domain"] for r in results}
        assert MemoryDomain.REVAN in domains
        assert MemoryDomain.TOOL in domains
        assert MemoryDomain.WORLD not in domains

    def test_retrieve_cross_domain_priority_order(self, retrieval: MemoryRetrieval) -> None:
        """Results should be sorted by domain priority (lower = higher priority)."""
        retrieval.store.store(MemoryDomain.TOOL, "tool", importance=1.0)
        retrieval.store.store(MemoryDomain.REVAN, "revan", importance=0.1)
        retrieval.store.store(MemoryDomain.WORLD, "world", importance=0.5)

        results = retrieval.retrieve_cross_domain()
        # Revan (priority 1) should come before Tool (priority 6)
        assert results[0]["domain"] == MemoryDomain.REVAN
        assert results[-1]["domain"] == MemoryDomain.TOOL

    def test_retrieve_cross_domain_respects_limit(self, retrieval: MemoryRetrieval) -> None:
        """Should respect the total limit."""
        for domain in MemoryDomain:
            retrieval.store.store(domain, f"entry in {domain.value}")

        results = retrieval.retrieve_cross_domain(limit=3)
        assert len(results) == 3


class TestRetrievalByContext:
    """Tests for context-based retrieval."""

    def test_retrieve_by_context_finds_matching(
        self, retrieval: MemoryRetrieval, index: MemoryIndex
    ) -> None:
        """Should find entries matching context key-value."""
        eid = retrieval.store.store(MemoryDomain.PROJECT, "Project Alpha")
        index.index_entry(MemoryDomain.PROJECT, eid, {"project": "alpha"})

        results = retrieval.retrieve_by_context("project", "alpha")
        assert len(results) == 1
        assert results[0]["content"] == "Project Alpha"
        assert results[0]["domain"] == MemoryDomain.PROJECT

    def test_retrieve_by_context_no_match(self, retrieval: MemoryRetrieval) -> None:
        """Should return empty for unmatched context."""
        results = retrieval.retrieve_by_context("nonexistent", "value")
        assert results == []

    def test_retrieve_by_context_cross_domain(
        self, retrieval: MemoryRetrieval, index: MemoryIndex
    ) -> None:
        """Should find entries across domains with same context."""
        e1 = retrieval.store.store(MemoryDomain.PROJECT, "Project X")
        e2 = retrieval.store.store(MemoryDomain.WORLD, "World X fact")

        index.index_entry(MemoryDomain.PROJECT, e1, {"topic": "x"})
        index.index_entry(MemoryDomain.WORLD, e2, {"topic": "x"})

        results = retrieval.retrieve_by_context("topic", "x")
        assert len(results) == 2
        domains = {r["domain"] for r in results}
        assert MemoryDomain.PROJECT in domains
        assert MemoryDomain.WORLD in domains


class TestRetrievalImportanceRange:
    """Tests for importance range retrieval."""

    def test_retrieve_by_importance_range(self, retrieval: MemoryRetrieval) -> None:
        """Should filter by importance range."""
        retrieval.store.store(MemoryDomain.WORLD, "low", importance=0.2)
        retrieval.store.store(MemoryDomain.WORLD, "mid", importance=0.5)
        retrieval.store.store(MemoryDomain.WORLD, "high", importance=0.9)

        results = retrieval.retrieve_by_importance_range(
            MemoryDomain.WORLD, min_importance=0.3, max_importance=0.7
        )
        assert len(results) == 1
        assert results[0]["content"] == "mid"


class TestRetrievalCounts:
    """Tests for counting entries."""

    def test_count_active(self, retrieval: MemoryRetrieval) -> None:
        """Should count active entries."""
        assert retrieval.count_active(MemoryDomain.WORLD) == 0
        retrieval.store.store(MemoryDomain.WORLD, "a")
        retrieval.store.store(MemoryDomain.WORLD, "b")
        assert retrieval.count_active(MemoryDomain.WORLD) == 2

    def test_count_all_includes_inactive(self, retrieval: MemoryRetrieval) -> None:
        """count_all should include deactivated entries."""
        eid = retrieval.store.store(MemoryDomain.WORLD, "a")
        retrieval.store.deactivate(MemoryDomain.WORLD, eid)

        assert retrieval.count_active(MemoryDomain.WORLD) == 0
        assert retrieval.count_all(MemoryDomain.WORLD) == 1

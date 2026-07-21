"""Context-aware memory retrieval for Telemachus.

Implements the retrieval strategy defined in the Memory Architecture:
context relevance, importance weighting, domain priority, and temporal
relevance. Provides multi-domain querying with result ranking.

Source: Codex/operations/MEMORY_ARCHITECTURE.md — Retrieval Strategy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from telemachus.core.domains import get_domain_priority
from telemachus.core.types import MemoryDomain

if TYPE_CHECKING:
    from telemachus.memory.store import MemoryStore


class MemoryRetrieval:
    """Context-aware memory retrieval engine.

    Queries across memory domains and ranks results by a composite
    score combining importance, domain priority, and temporal relevance.

    Attributes:
        store: The MemoryStore instance to retrieve from.
    """

    def __init__(self, store: MemoryStore) -> None:
        """Initialize the retrieval engine.

        Args:
            store: The MemoryStore to query.
        """
        self.store = store

    def retrieve_by_domain(
        self,
        domain: MemoryDomain,
        *,
        active_only: bool = True,
        min_importance: float = 0.0,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve entries from a single domain.

        Args:
            domain: The memory domain.
            active_only: If True, exclude deactivated entries.
            min_importance: Minimum importance threshold.
            limit: Maximum results.
            offset: Pagination offset.
            order_by: Sort column.
            order_desc: Descending order if True.

        Returns:
            A list of entry dictionaries.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.query(
            domain=domain,
            active_only=active_only,
            min_importance=min_importance,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_desc=order_desc,
        )

    def retrieve_important(
        self,
        domain: MemoryDomain,
        threshold: float = 0.7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve high-importance entries from a domain.

        Args:
            domain: The memory domain.
            threshold: Minimum importance (0.0 to 1.0).
            limit: Maximum results.

        Returns:
            A list of high-importance entries, sorted by importance descending.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.query(
            domain=domain,
            active_only=True,
            min_importance=threshold,
            limit=limit,
            order_by="importance",
            order_desc=True,
        )

    def retrieve_recent(
        self,
        domain: MemoryDomain,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve the most recent entries from a domain.

        Args:
            domain: The memory domain.
            limit: Maximum results.

        Returns:
            A list of recent entries, newest first.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.query(
            domain=domain,
            active_only=True,
            limit=limit,
            order_by="created_at",
            order_desc=True,
        )

    def retrieve_cross_domain(
        self,
        domains: list[MemoryDomain] | None = None,
        *,
        active_only: bool = True,
        min_importance: float = 0.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve entries across multiple domains with priority ranking.

        Results are sorted by domain priority (lower = higher priority),
        then by importance within each domain.

        Args:
            domains: List of domains to query (all if None).
            active_only: If True, exclude deactivated entries.
            min_importance: Minimum importance threshold.
            limit: Maximum total results.

        Returns:
            A list of entries with an added 'domain' field, sorted by
            domain priority then importance.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if domains is None:
            domains = list(MemoryDomain)

        all_results: list[dict[str, Any]] = []
        for domain in domains:
            entries = self.store.query(
                domain=domain,
                active_only=active_only,
                min_importance=min_importance,
                limit=limit,
                order_by="importance",
                order_desc=True,
            )
            for entry in entries:
                entry["domain"] = domain
            all_results.extend(entries)

        all_results.sort(
            key=lambda e: (
                get_domain_priority(e["domain"]),
                -e["importance"],
            )
        )

        return all_results[:limit]

    def retrieve_by_context(
        self,
        context_key: str,
        context_value: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve entries matching a context key-value pair.

        Uses the unified index to find entries across all domains
        that match the given context.

        Args:
            context_key: The index key (e.g., "project", "topic").
            context_value: The value to match.
            limit: Maximum results.

        Returns:
            A list of matching entries with domain and entry_id.

        Raises:
            RuntimeError: If the store is not connected.
        """
        index_results = self.store.search_index(context_key, context_value)
        results: list[dict[str, Any]] = []

        for idx_entry in index_results[:limit]:
            domain = MemoryDomain(idx_entry["domain"])
            entry = self.store.retrieve(domain, idx_entry["entry_id"])
            if entry is not None:
                entry["domain"] = domain
                results.append(entry)

        return results

    def retrieve_by_importance_range(
        self,
        domain: MemoryDomain,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve entries within an importance range.

        Args:
            domain: The memory domain.
            min_importance: Lower bound (inclusive).
            max_importance: Upper bound (inclusive).
            limit: Maximum results.

        Returns:
            A list of entries sorted by importance descending.

        Raises:
            RuntimeError: If the store is not connected.
        """
        results = self.store.query(
            domain=domain,
            active_only=True,
            min_importance=min_importance,
            limit=limit * 2,  # Over-fetch then filter
            order_by="importance",
            order_desc=True,
        )

        return [r for r in results if r["importance"] <= max_importance][:limit]

    def count_active(self, domain: MemoryDomain) -> int:
        """Count active entries in a domain.

        Args:
            domain: The memory domain.

        Returns:
            Number of active entries.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.count(domain, active_only=True)

    def count_all(self, domain: MemoryDomain) -> int:
        """Count all entries (including inactive) in a domain.

        Args:
            domain: The memory domain.

        Returns:
            Total number of entries.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.count(domain, active_only=False)

"""Cross-domain semantic index for Telemachus memory.

Provides a unified index layer that connects entries across all six
memory domains, enabling cross-domain retrieval, contextual linking,
and relationship mapping.

Source: Codex/operations/MEMORY_ARCHITECTURE.md — Unified Memory Index
"""

from __future__ import annotations

import time
from typing import Any

from telemachus.core.types import MemoryDomain


class MemoryIndex:
    """Cross-domain semantic index for memory entries.

    Wraps the unified_index table in MemoryStore to provide
    higher-level indexing operations: linking entries across
    domains, searching by concept, and managing index keys.

    Attributes:
        store: The MemoryStore instance this index operates on.
    """

    def __init__(self, store: MemoryStore) -> None:  # noqa: F821
        """Initialize the memory index.

        Args:
            store: The MemoryStore to index.
        """
        self.store = store

    def index_entry(
        self,
        domain: MemoryDomain,
        entry_id: int,
        keys: dict[str, str],
    ) -> None:
        """Add index entries for a memory entry.

        Each key-value pair becomes a row in the unified_index table.

        Args:
            domain: The memory domain.
            entry_id: The entry ID to index.
            keys: Dictionary of key-value pairs to index.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        now = time.time()
        for key, value in keys.items():
            self.store.conn.execute(
                """INSERT INTO unified_index
                   (entry_id, domain, key, value, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (entry_id, domain.value, key, value, now),
            )
        self.store.conn.commit()

    def remove_entry_index(self, domain: MemoryDomain, entry_id: int) -> int:
        """Remove all index entries for a specific entry.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            Number of index rows removed.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        cursor = self.store.conn.execute(
            """DELETE FROM unified_index
               WHERE entry_id = ? AND domain = ?""",
            (entry_id, domain.value),
        )
        self.store.conn.commit()
        return cursor.rowcount

    def find_by_key(self, key: str, value: str | None = None) -> list[dict[str, Any]]:
        """Find entries by index key, optionally matching a specific value.

        Args:
            key: The index key to search.
            value: Optional value to match exactly.

        Returns:
            A list of matching index entries.

        Raises:
            RuntimeError: If the store is not connected.
        """
        return self.store.search_index(key, value)

    def find_related(self, domain: MemoryDomain, entry_id: int) -> list[dict[str, Any]]:
        """Find entries related to a given entry via shared index keys.

        Searches for other entries that share index keys with the
        specified entry, enabling cross-domain relationship discovery.

        Args:
            domain: The memory domain of the source entry.
            entry_id: The source entry ID.

        Returns:
            A list of related index entries (excluding the source entry).

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        rows = self.store.conn.execute(
            """SELECT DISTINCT ui2.id, ui2.entry_id, ui2.domain, ui2.key, ui2.value, ui2.created_at
               FROM unified_index ui1
               JOIN unified_index ui2
                 ON ui1.key = ui2.key AND ui1.value = ui2.value
               WHERE ui1.entry_id = ?
                 AND ui1.domain = ?
                 AND NOT (ui2.entry_id = ? AND ui2.domain = ?)""",
            (entry_id, domain.value, entry_id, domain.value),
        ).fetchall()

        return [
            {
                "id": row[0],
                "entry_id": row[1],
                "domain": row[2],
                "key": row[3],
                "value": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]

    def get_keys_for_entry(self, domain: MemoryDomain, entry_id: int) -> dict[str, str]:
        """Get all index keys for a specific entry.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            A dictionary of key-value pairs.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        rows = self.store.conn.execute(
            """SELECT key, value FROM unified_index
               WHERE entry_id = ? AND domain = ?""",
            (entry_id, domain.value),
        ).fetchall()

        return {row[0]: row[1] for row in rows}

    def get_all_keys(self) -> list[str]:
        """Get all distinct index keys across all domains.

        Returns:
            A sorted list of unique key names.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        rows = self.store.conn.execute(
            "SELECT DISTINCT key FROM unified_index ORDER BY key"
        ).fetchall()

        return [row[0] for row in rows]

    def get_domain_index_stats(self, domain: MemoryDomain) -> dict[str, int]:
        """Get statistics about indexed entries in a domain.

        Args:
            domain: The memory domain.

        Returns:
            A dictionary with 'indexed_entries' and 'total_keys' counts.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        entry_row = self.store.conn.execute(
            """SELECT COUNT(DISTINCT entry_id) FROM unified_index
               WHERE domain = ?""",
            (domain.value,),
        ).fetchone()

        key_row = self.store.conn.execute(
            """SELECT COUNT(*) FROM unified_index
               WHERE domain = ?""",
            (domain.value,),
        ).fetchone()

        return {
            "indexed_entries": entry_row[0] if entry_row else 0,
            "total_keys": key_row[0] if key_row else 0,
        }

"""SQLite-backed memory store for Telemachus.

Provides connection management, schema creation, and CRUD operations
across all six memory domains. Uses the stdlib sqlite3 module with
WAL mode for concurrent read/write performance.

Source: Codex/operations/MEMORY_ARCHITECTURE.md
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from telemachus.core.domains import DomainDefinition, get_domain_definitions
from telemachus.core.types import MemoryDomain


class MemoryStore:
    """SQLite-backed persistent memory store.

    Manages a single SQLite database file with tables for each of the
    six memory domains plus a unified index table. All writes are
    append-only at the storage level; versioning is handled by the
    VersionManager layer above.

    Attributes:
        db_path: Path to the SQLite database file.
        conn: The active sqlite3 connection (None if not connected).
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the memory store.

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
        self.conn.execute("PRAGMA foreign_keys=ON")

    def disconnect(self) -> None:
        """Close the database connection cleanly."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def initialize_schema(self) -> None:
        """Create all tables and indexes if they do not exist.

        Creates:
            - schema_version: Tracks schema migrations.
            - One memory_entries table per domain (6 tables).
            - A unified_index table for cross-domain search.
            - A memory_versions table for version history.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            )"""
        )

        domains = get_domain_definitions()
        for domain_def in domains:
            self._create_domain_table(domain_def)

        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS unified_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        self.conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_unified_key
               ON unified_index(key)"""
        )
        self.conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_unified_domain
               ON unified_index(domain)"""
        )

        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS memory_versions (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                superseded_by INTEGER
            )"""
        )
        self.conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_versions_entry
               ON memory_versions(entry_id, domain)"""
        )

        self.conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (self.SCHEMA_VERSION, time.time()),
        )
        self.conn.commit()

    def _create_domain_table(self, domain_def: DomainDefinition) -> None:
        """Create the memory_entries table for a single domain.

        Args:
            domain_def: The domain definition.
        """
        domain_name = domain_def.domain.value
        self.conn.execute(
            f"""CREATE TABLE IF NOT EXISTS memory_entries_{domain_name} (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{{}}',
                importance REAL NOT NULL DEFAULT 0.5,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                current_version INTEGER NOT NULL DEFAULT 1
            )"""
        )
        self.conn.execute(
            f"""CREATE INDEX IF NOT EXISTS idx_entries_{domain_name}_active
               ON memory_entries_{domain_name}(is_active)"""
        )
        self.conn.execute(
            f"""CREATE INDEX IF NOT EXISTS idx_entries_{domain_name}_importance
               ON memory_entries_{domain_name}(importance)"""
        )
        self.conn.execute(
            f"""CREATE INDEX IF NOT EXISTS idx_entries_{domain_name}_created
               ON memory_entries_{domain_name}(created_at)"""
        )

    def store(
        self,
        domain: MemoryDomain,
        content: str,
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
        index_keys: dict[str, str] | None = None,
    ) -> int:
        """Store a new memory entry in the specified domain.

        Args:
            domain: The memory domain to store in.
            content: The text content of the memory entry.
            metadata: Optional metadata dictionary.
            importance: Importance weight (0.0 to 1.0).
            index_keys: Optional key-value pairs for the unified index.

        Returns:
            The new entry_id.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        now = time.time()
        meta_json = json.dumps(metadata or {})

        cursor = self.conn.execute(
            f"""INSERT INTO memory_entries_{domain.value}
                (content, metadata, importance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
            (content, meta_json, importance, now, now),
        )
        entry_id = cursor.lastrowid

        if index_keys:
            for key, value in index_keys.items():
                self.conn.execute(
                    """INSERT INTO unified_index
                       (entry_id, domain, key, value, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (entry_id, domain.value, key, value, now),
                )

        self.conn.commit()
        return entry_id

    def retrieve(self, domain: MemoryDomain, entry_id: int) -> dict[str, Any] | None:
        """Retrieve a single memory entry by ID.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            A dictionary with entry data, or None if not found.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        row = self.conn.execute(
            f"""SELECT entry_id, content, metadata, importance, is_active,
                      created_at, updated_at, current_version
               FROM memory_entries_{domain.value}
               WHERE entry_id = ?""",
            (entry_id,),
        ).fetchone()

        if row is None:
            return None

        return {
            "entry_id": row[0],
            "content": row[1],
            "metadata": json.loads(row[2]),
            "importance": row[3],
            "is_active": bool(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
            "current_version": row[7],
        }

    def update(
        self,
        domain: MemoryDomain,
        entry_id: int,
        content: str,
        metadata: dict[str, Any] | None = None,
        importance: float | None = None,
    ) -> bool:
        """Update an existing memory entry.

        Increments the version number. The previous version should be
        preserved by the VersionManager before calling this method.

        Args:
            domain: The memory domain.
            entry_id: The entry ID to update.
            content: New content.
            metadata: Optional new metadata (merged if partial).
            importance: Optional new importance weight.

        Returns:
            True if the entry was found and updated, False otherwise.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        existing = self.retrieve(domain, entry_id)
        if existing is None:
            return False

        now = time.time()
        new_meta = existing["metadata"]
        if metadata is not None:
            new_meta = {**new_meta, **metadata}
        new_importance = importance if importance is not None else existing["importance"]
        new_version = existing["current_version"] + 1

        self.conn.execute(
            f"""UPDATE memory_entries_{domain.value}
                SET content = ?, metadata = ?, importance = ?,
                    updated_at = ?, current_version = ?
                WHERE entry_id = ?""",
            (
                content,
                json.dumps(new_meta),
                new_importance,
                now,
                new_version,
                entry_id,
            ),
        )
        self.conn.commit()
        return True

    def deactivate(self, domain: MemoryDomain, entry_id: int) -> bool:
        """Mark a memory entry as inactive (soft delete).

        No data is ever deleted. Inactive entries are excluded from
        default queries but remain in the database.

        Args:
            domain: The memory domain.
            entry_id: The entry ID to deactivate.

        Returns:
            True if the entry was found and deactivated.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        cursor = self.conn.execute(
            f"""UPDATE memory_entries_{domain.value}
                SET is_active = 0, updated_at = ?
                WHERE entry_id = ? AND is_active = 1""",
            (time.time(), entry_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def query(
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
        """Query memory entries in a domain with filters.

        Args:
            domain: The memory domain to query.
            active_only: If True, exclude deactivated entries.
            min_importance: Minimum importance threshold.
            limit: Maximum number of results.
            offset: Pagination offset.
            order_by: Column to order by.
            order_desc: If True, descending order.

        Returns:
            A list of entry dictionaries.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        allowed_columns = {
            "created_at",
            "updated_at",
            "importance",
            "entry_id",
            "current_version",
        }
        if order_by not in allowed_columns:
            order_by = "created_at"

        direction = "DESC" if order_desc else "ASC"
        conditions = []
        params: list[Any] = []

        if active_only:
            conditions.append("is_active = 1")
        if min_importance > 0.0:
            conditions.append("importance >= ?")
            params.append(min_importance)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(
            f"""SELECT entry_id, content, metadata, importance, is_active,
                      created_at, updated_at, current_version
               FROM memory_entries_{domain.value}
               {where_clause}
               ORDER BY {order_by} {direction}
               LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()

        return [
            {
                "entry_id": row[0],
                "content": row[1],
                "metadata": json.loads(row[2]),
                "importance": row[3],
                "is_active": bool(row[4]),
                "created_at": row[5],
                "updated_at": row[6],
                "current_version": row[7],
            }
            for row in rows
        ]

    def count(self, domain: MemoryDomain, *, active_only: bool = True) -> int:
        """Count entries in a domain.

        Args:
            domain: The memory domain.
            active_only: If True, only count active entries.

        Returns:
            The number of entries.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        if active_only:
            row = self.conn.execute(
                f"""SELECT COUNT(*) FROM memory_entries_{domain.value}
                    WHERE is_active = 1"""
            ).fetchone()
        else:
            row = self.conn.execute(
                f"SELECT COUNT(*) FROM memory_entries_{domain.value}"
            ).fetchone()

        return row[0] if row else 0

    def search_index(self, key: str, value: str | None = None) -> list[dict[str, Any]]:
        """Search the unified index.

        Args:
            key: The index key to search for.
            value: Optional value to match exactly.

        Returns:
            A list of matching index entries with their domain and entry_id.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        if value is not None:
            rows = self.conn.execute(
                """SELECT id, entry_id, domain, key, value, created_at
                   FROM unified_index
                   WHERE key = ? AND value = ?""",
                (key, value),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT id, entry_id, domain, key, value, created_at
                   FROM unified_index
                   WHERE key = ?""",
                (key,),
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

    def get_version_history(self, domain: MemoryDomain, entry_id: int) -> list[dict[str, Any]]:
        """Retrieve the full version history for an entry.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            A list of version dictionaries, oldest first.

        Raises:
            RuntimeError: If not connected.
        """
        if self.conn is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")

        rows = self.conn.execute(
            """SELECT version_id, entry_id, domain, version_number,
                      content, metadata, created_at, superseded_by
               FROM memory_versions
               WHERE entry_id = ? AND domain = ?
               ORDER BY version_number ASC""",
            (entry_id, domain.value),
        ).fetchall()

        return [
            {
                "version_id": row[0],
                "entry_id": row[1],
                "domain": row[2],
                "version_number": row[3],
                "content": row[4],
                "metadata": json.loads(row[5]),
                "created_at": row[6],
                "superseded_by": row[7],
            }
            for row in rows
        ]

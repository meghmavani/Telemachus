"""Append-only versioning for Telemachus memory.

Implements the core principle: no memory is ever deleted. Instead,
old versions are preserved, new versions supersede them, and the
full history remains accessible.

Source: Codex/operations/MEMORY_ARCHITECTURE.md — Versioning Principle
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from telemachus.core.types import MemoryDomain

if TYPE_CHECKING:
    from telemachus.memory.store import MemoryStore


@dataclass(frozen=True)
class MemoryVersion:
    """A single version snapshot of a memory entry.

    Attributes:
        version_id: Unique version identifier.
        entry_id: The parent entry ID.
        domain: The memory domain.
        version_number: Sequential version number (1-based).
        content: The content at this version.
        metadata: Metadata at this version.
        created_at: Timestamp when this version was created.
        superseded_by: Version ID that superseded this one (None if current).
    """

    version_id: int
    entry_id: int
    domain: MemoryDomain
    version_number: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    superseded_by: int | None = None

    def is_current(self) -> bool:
        """Check if this version is the current (not superseded) version.

        Returns:
            True if this is the latest version.
        """
        return self.superseded_by is None

    def is_original(self) -> bool:
        """Check if this is the first version ever created.

        Returns:
            True if version_number is 1.
        """
        return self.version_number == 1


class VersionManager:
    """Manages append-only versioning for memory entries.

    Works in conjunction with MemoryStore to preserve every version
    of every memory entry. Before an entry is updated, the current
    state is archived as a version record.

    Attributes:
        store: The MemoryStore instance this manager operates on.
    """

    def __init__(self, store: MemoryStore) -> None:
        """Initialize the version manager.

        Args:
            store: The MemoryStore to manage versions for.
        """
        self.store = store

    def archive_current_version(self, domain: MemoryDomain, entry_id: int) -> MemoryVersion | None:
        """Archive the current state of an entry before it is modified.

        Should be called BEFORE updating an entry. Creates a version
        record in the memory_versions table.

        Args:
            domain: The memory domain.
            entry_id: The entry ID to archive.

        Returns:
            The created MemoryVersion, or None if the entry doesn't exist.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        entry = self.store.retrieve(domain, entry_id)
        if entry is None:
            return None

        now = time.time()
        cursor = self.store.conn.execute(
            """INSERT INTO memory_versions
               (entry_id, domain, version_number, content, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                domain.value,
                entry["current_version"],
                entry["content"],
                json.dumps(entry["metadata"]),
                now,
            ),
        )
        version_id = cursor.lastrowid
        if version_id is None:  # pragma: no cover — sqlite always sets this on INSERT
            raise RuntimeError("INSERT did not return a row id")
        self.store.conn.commit()

        return MemoryVersion(
            version_id=version_id,
            entry_id=entry_id,
            domain=domain,
            version_number=entry["current_version"],
            content=entry["content"],
            metadata=entry["metadata"],
            created_at=now,
        )

    def supersede_version(self, old_version_id: int, new_version_id: int) -> bool:
        """Mark an old version as superseded by a newer version.

        Args:
            old_version_id: The version being superseded.
            new_version_id: The version that supersedes it.

        Returns:
            True if the old version was found and updated.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        cursor = self.store.conn.execute(
            """UPDATE memory_versions
               SET superseded_by = ?
               WHERE version_id = ? AND superseded_by IS NULL""",
            (new_version_id, old_version_id),
        )
        self.store.conn.commit()
        return cursor.rowcount > 0

    def safe_update(
        self,
        domain: MemoryDomain,
        entry_id: int,
        content: str,
        metadata: dict[str, Any] | None = None,
        importance: float | None = None,
        ) -> MemoryVersion | None:
        """Update an entry safely by archiving the current version first.

        This is the primary method for modifying memory. It:
        1. Archives the current version.
        2. Updates the entry with new content.
        3. Links the previous version to the newly archived one.

        Args:
            domain: The memory domain.
            entry_id: The entry ID to update.
            content: New content.
            metadata: Optional new metadata.
            importance: Optional new importance.

        Returns:
            The archived MemoryVersion of the previous state,
            or None if the entry doesn't exist.

        Raises:
            RuntimeError: If the store is not connected.
        """
        # Get the previous version history before archiving
        previous_history = self.store.get_version_history(domain, entry_id)

        old_version = self.archive_current_version(domain, entry_id)
        if old_version is None:
            return None

        success = self.store.update(domain, entry_id, content, metadata, importance)
        if not success:
            return None

        # Link the most recent previous version to the newly archived one
        if previous_history:
            prev_ver = previous_history[-1]
            self.supersede_version(prev_ver["version_id"], old_version.version_id)

        return old_version

    def get_history(self, domain: MemoryDomain, entry_id: int) -> list[MemoryVersion]:
        """Get the full version history for an entry as MemoryVersion objects.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            A list of MemoryVersion objects, oldest first.

        Raises:
            RuntimeError: If the store is not connected.
        """
        raw_history = self.store.get_version_history(domain, entry_id)
        return [
            MemoryVersion(
                version_id=v["version_id"],
                entry_id=v["entry_id"],
                domain=MemoryDomain(v["domain"]),
                version_number=v["version_number"],
                content=v["content"],
                metadata=v["metadata"],
                created_at=v["created_at"],
                superseded_by=v["superseded_by"],
            )
            for v in raw_history
        ]

    def get_current_version_number(self, domain: MemoryDomain, entry_id: int) -> int:
        """Get the current version number of an entry.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            The current version number, or 0 if entry not found.
        """
        entry = self.store.retrieve(domain, entry_id)
        if entry is None:
            return 0
        return int(entry["current_version"])

    def count_versions(self, domain: MemoryDomain, entry_id: int) -> int:
        """Count how many versions exist for an entry.

        Args:
            domain: The memory domain.
            entry_id: The entry ID.

        Returns:
            The number of archived versions.

        Raises:
            RuntimeError: If the store is not connected.
        """
        if self.store.conn is None:
            raise RuntimeError("MemoryStore not connected.")

        row = self.store.conn.execute(
            """SELECT COUNT(*) FROM memory_versions
               WHERE entry_id = ? AND domain = ?""",
            (entry_id, domain.value),
        ).fetchone()
        return row[0] if row else 0

"""Tests for the VersionManager — append-only versioning."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from telemachus.core.types import MemoryDomain
from telemachus.memory.store import MemoryStore
from telemachus.memory.versioning import MemoryVersion, VersionManager


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    """Create a connected and initialized MemoryStore."""
    s = MemoryStore(tmp_path / "test_ver.db")
    s.connect()
    s.initialize_schema()
    yield s
    s.disconnect()


@pytest.fixture
def version_manager(store: MemoryStore) -> VersionManager:
    """Create a VersionManager backed by the store."""
    return VersionManager(store)


class TestMemoryVersion:
    """Tests for the MemoryVersion dataclass."""

    def test_version_is_frozen(self) -> None:
        """MemoryVersion should be a frozen dataclass."""
        v = MemoryVersion(
            version_id=1,
            entry_id=1,
            domain=MemoryDomain.WORLD,
            version_number=1,
            content="test",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.content = "changed"  # type: ignore[misc]

    def test_is_current_when_not_superseded(self) -> None:
        """Version without superseded_by should be current."""
        v = MemoryVersion(
            version_id=1,
            entry_id=1,
            domain=MemoryDomain.WORLD,
            version_number=1,
            content="test",
        )
        assert v.is_current() is True

    def test_is_current_when_superseded(self) -> None:
        """Version with superseded_by should not be current."""
        v = MemoryVersion(
            version_id=1,
            entry_id=1,
            domain=MemoryDomain.WORLD,
            version_number=1,
            content="test",
            superseded_by=2,
        )
        assert v.is_current() is False

    def test_is_original(self) -> None:
        """Version 1 should be original."""
        v = MemoryVersion(
            version_id=1,
            entry_id=1,
            domain=MemoryDomain.WORLD,
            version_number=1,
            content="test",
        )
        assert v.is_original() is True

    def test_is_not_original(self) -> None:
        """Version > 1 should not be original."""
        v = MemoryVersion(
            version_id=2,
            entry_id=1,
            domain=MemoryDomain.WORLD,
            version_number=2,
            content="test",
        )
        assert v.is_original() is False


class TestVersionManagerArchive:
    """Tests for archiving current versions."""

    def test_archive_creates_version_record(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Archiving should create a version in memory_versions."""
        entry_id = store.store(MemoryDomain.WORLD, "original content")
        archived = version_manager.archive_current_version(MemoryDomain.WORLD, entry_id)

        assert archived is not None
        assert archived.content == "original content"
        assert archived.version_number == 1
        assert archived.domain == MemoryDomain.WORLD
        assert archived.entry_id == entry_id

    def test_archive_nonexistent_returns_none(self, version_manager: VersionManager) -> None:
        """Archiving a nonexistent entry should return None."""
        result = version_manager.archive_current_version(MemoryDomain.WORLD, 99999)
        assert result is None

    def test_archive_preserves_metadata(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Archived version should preserve metadata."""
        entry_id = store.store(MemoryDomain.WORLD, "content", metadata={"key": "value"})
        archived = version_manager.archive_current_version(MemoryDomain.WORLD, entry_id)
        assert archived is not None
        assert archived.metadata == {"key": "value"}


class TestVersionManagerSupersede:
    """Tests for version supersession."""

    def test_supersede_links_versions(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Superseding should set superseded_by on the old version."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")
        v1 = version_manager.archive_current_version(MemoryDomain.WORLD, entry_id)
        assert v1 is not None

        store.update(MemoryDomain.WORLD, entry_id, "v2")
        v2_archived = version_manager.archive_current_version(MemoryDomain.WORLD, entry_id)
        assert v2_archived is not None

        result = version_manager.supersede_version(v1.version_id, v2_archived.version_id)
        assert result is True

        history = version_manager.get_history(MemoryDomain.WORLD, entry_id)
        assert len(history) == 2
        assert history[0].superseded_by == v2_archived.version_id
        assert history[1].superseded_by is None

    def test_supersede_nonexistent_returns_false(self, version_manager: VersionManager) -> None:
        """Superseding nonexistent version should return False."""
        assert version_manager.supersede_version(99999, 99998) is False


class TestVersionManagerSafeUpdate:
    """Tests for safe_update — the primary modification method."""

    def test_safe_update_archives_and_updates(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """safe_update should archive old version and update entry."""
        entry_id = store.store(MemoryDomain.PROJECT, "v1 content")
        old = version_manager.safe_update(MemoryDomain.PROJECT, entry_id, "v2 content")

        assert old is not None
        assert old.content == "v1 content"

        entry = store.retrieve(MemoryDomain.PROJECT, entry_id)
        assert entry is not None
        assert entry["content"] == "v2 content"
        assert entry["current_version"] == 2

    def test_safe_update_nonexistent_returns_none(self, version_manager: VersionManager) -> None:
        """safe_update on nonexistent entry should return None."""
        result = version_manager.safe_update(MemoryDomain.WORLD, 99999, "content")
        assert result is None

    def test_safe_update_preserves_version_history(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Multiple safe_updates should build a version chain."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")

        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v2")
        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v3")

        # History contains archived versions (v1, v2); v3 is the live entry
        history = version_manager.get_history(MemoryDomain.WORLD, entry_id)
        assert len(history) == 2
        assert history[0].content == "v1"
        assert history[1].content == "v2"

        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["content"] == "v3"
        assert entry["current_version"] == 3

    def test_safe_update_links_supersession_chain(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Version chain should have proper supersession links."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")
        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v2")
        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v3")

        # Archived versions: v1 superseded by v2; v2 is latest archived (not yet superseded)
        history = version_manager.get_history(MemoryDomain.WORLD, entry_id)
        assert len(history) == 2
        assert history[0].superseded_by == history[1].version_id
        assert history[1].superseded_by is None

        # Live entry should be v3
        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["content"] == "v3"


class TestVersionManagerQuery:
    """Tests for version history queries."""

    def test_get_history_empty(self, store: MemoryStore, version_manager: VersionManager) -> None:
        """New entry should have empty history."""
        entry_id = store.store(MemoryDomain.WORLD, "content")
        history = version_manager.get_history(MemoryDomain.WORLD, entry_id)
        assert history == []

    def test_get_current_version_number(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Should return correct version number."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")
        assert version_manager.get_current_version_number(MemoryDomain.WORLD, entry_id) == 1

        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v2")
        assert version_manager.get_current_version_number(MemoryDomain.WORLD, entry_id) == 2

    def test_get_current_version_number_nonexistent(self, version_manager: VersionManager) -> None:
        """Nonexistent entry should return 0."""
        assert version_manager.get_current_version_number(MemoryDomain.WORLD, 99999) == 0

    def test_count_versions(self, store: MemoryStore, version_manager: VersionManager) -> None:
        """Should count archived versions correctly."""
        entry_id = store.store(MemoryDomain.WORLD, "v1")
        assert version_manager.count_versions(MemoryDomain.WORLD, entry_id) == 0

        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v2")
        assert version_manager.count_versions(MemoryDomain.WORLD, entry_id) == 1

        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "v3")
        assert version_manager.count_versions(MemoryDomain.WORLD, entry_id) == 2

    def test_no_data_is_ever_deleted(
        self, store: MemoryStore, version_manager: VersionManager
    ) -> None:
        """Even after deactivation, version history should remain."""
        entry_id = store.store(MemoryDomain.WORLD, "important data")
        version_manager.safe_update(MemoryDomain.WORLD, entry_id, "updated data")
        store.deactivate(MemoryDomain.WORLD, entry_id)

        history = version_manager.get_history(MemoryDomain.WORLD, entry_id)
        assert len(history) == 1
        assert history[0].content == "important data"

        entry = store.retrieve(MemoryDomain.WORLD, entry_id)
        assert entry is not None
        assert entry["is_active"] is False
        assert entry["content"] == "updated data"

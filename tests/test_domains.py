"""Tests for the memory domain definitions module."""

from __future__ import annotations

from telemachus.core.domains import (
    DomainPriority,
    Mutability,
    get_domain_definitions,
    get_domain_priority,
    is_immutable,
)
from telemachus.core.types import MemoryDomain


class TestDomainDefinitions:
    """Tests for domain definitions."""

    def test_all_six_domains_defined(self) -> None:
        """Should have exactly 6 domain definitions."""
        domains = get_domain_definitions()
        assert len(domains) == 6

    def test_each_domain_has_unique_identifier(self) -> None:
        """Each domain should have a unique MemoryDomain identifier."""
        domains = get_domain_definitions()
        ids = {d.domain for d in domains}
        assert len(ids) == 6

    def test_revan_domain_is_immutable(self) -> None:
        """Revan Memory should be immutable."""
        domains = get_domain_definitions()
        revan = next(d for d in domains if d.domain == MemoryDomain.REVAN)
        assert revan.mutability == Mutability.IMMUTABLE

    def test_revan_domain_has_highest_priority(self) -> None:
        """Revan Memory should have the highest priority (after Constitution)."""
        domains = get_domain_definitions()
        revan = next(d for d in domains if d.domain == MemoryDomain.REVAN)
        assert revan.priority == DomainPriority.REVAN

    def test_emotion_domain_is_immutable(self) -> None:
        """Emotion Memory should be immutable."""
        domains = get_domain_definitions()
        emotion = next(d for d in domains if d.domain == MemoryDomain.EMOTION)
        assert emotion.mutability == Mutability.IMMUTABLE

    def test_world_domain_is_fully_mutable(self) -> None:
        """World Memory should be fully mutable."""
        domains = get_domain_definitions()
        world = next(d for d in domains if d.domain == MemoryDomain.WORLD)
        assert world.mutability == Mutability.FULLY_MUTABLE

    def test_tool_domain_is_fully_mutable(self) -> None:
        """Tool Memory should be fully mutable."""
        domains = get_domain_definitions()
        tool = next(d for d in domains if d.domain == MemoryDomain.TOOL)
        assert tool.mutability == Mutability.FULLY_MUTABLE

    def test_reflection_domain_is_semi_mutable(self) -> None:
        """Reflection Memory should be semi-mutable."""
        domains = get_domain_definitions()
        reflection = next(d for d in domains if d.domain == MemoryDomain.REFLECTION)
        assert reflection.mutability == Mutability.SEMI_MUTABLE

    def test_project_domain_is_fully_mutable(self) -> None:
        """Project Memory should be fully mutable."""
        domains = get_domain_definitions()
        project = next(d for d in domains if d.domain == MemoryDomain.PROJECT)
        assert project.mutability == Mutability.FULLY_MUTABLE

    def test_each_domain_has_rules(self) -> None:
        """Every domain should have operational rules."""
        domains = get_domain_definitions()
        for d in domains:
            assert len(d.rules) > 0, f"Domain {d.domain} has no rules"

    def test_each_domain_has_stored_content(self) -> None:
        """Every domain should define what content it stores."""
        domains = get_domain_definitions()
        for d in domains:
            assert len(d.stored_content) > 0, f"Domain {d.domain} has no stored content"

    def test_each_domain_has_description(self) -> None:
        """Every domain should have a description."""
        domains = get_domain_definitions()
        for d in domains:
            assert d.description, f"Domain {d.domain} has empty description"


class TestDomainPriority:
    """Tests for domain priority functions."""

    def test_revan_has_priority_1(self) -> None:
        """Revan domain should have priority 1."""
        assert get_domain_priority(MemoryDomain.REVAN) == 1

    def test_tool_has_priority_6(self) -> None:
        """Tool domain should have priority 6 (lowest)."""
        assert get_domain_priority(MemoryDomain.TOOL) == 6

    def test_priority_order_is_correct(self) -> None:
        """Priorities should follow the Codex hierarchy."""
        priorities = {
            MemoryDomain.REVAN: 1,
            MemoryDomain.REFLECTION: 2,
            MemoryDomain.PROJECT: 3,
            MemoryDomain.EMOTION: 4,
            MemoryDomain.WORLD: 5,
            MemoryDomain.TOOL: 6,
        }
        for domain, expected in priorities.items():
            assert get_domain_priority(domain) == expected


class TestImmutability:
    """Tests for immutability checks."""

    def test_revan_is_immutable(self) -> None:
        """Revan domain should be immutable."""
        assert is_immutable(MemoryDomain.REVAN) is True

    def test_emotion_is_immutable(self) -> None:
        """Emotion domain should be immutable."""
        assert is_immutable(MemoryDomain.EMOTION) is True

    def test_world_is_not_immutable(self) -> None:
        """World domain should not be immutable."""
        assert is_immutable(MemoryDomain.WORLD) is False

    def test_project_is_not_immutable(self) -> None:
        """Project domain should not be immutable."""
        assert is_immutable(MemoryDomain.PROJECT) is False

    def test_tool_is_not_immutable(self) -> None:
        """Tool domain should not be immutable."""
        assert is_immutable(MemoryDomain.TOOL) is False

    def test_reflection_is_not_immutable(self) -> None:
        """Reflection domain should not be immutable (it's semi-mutable)."""
        assert is_immutable(MemoryDomain.REFLECTION) is False

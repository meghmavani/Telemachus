"""Tests for the Constitution module."""

from __future__ import annotations

import dataclasses

import pytest

from telemachus.core.constitution import (
    Constitution,
    CorePrinciple,
    create_default_constitution,
)
from telemachus.core.types import ActionRequest, ConstitutionalVerdict


class TestCorePrinciple:
    """Tests for CorePrinciple dataclass."""

    def test_principle_is_frozen(self) -> None:
        """CorePrinciple should be immutable."""
        p = CorePrinciple(name="test", description="A test principle")
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.name = "changed"  # type: ignore[misc]

    def test_principle_defaults_not_sacred(self) -> None:
        """Principles should default to not sacred."""
        p = CorePrinciple(name="test", description="desc")
        assert p.is_sacred is False

    def test_principle_can_be_sacred(self) -> None:
        """Sacred flag should be settable."""
        p = CorePrinciple(name="test", description="desc", is_sacred=True)
        assert p.is_sacred is True


class TestConstitution:
    """Tests for Constitution dataclass."""

    @pytest.fixture
    def default_constitution(self) -> Constitution:
        """Create a default Constitution for testing."""
        return create_default_constitution()

    def test_constitution_is_frozen(self, default_constitution: Constitution) -> None:
        """Constitution should be immutable."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            default_constitution.first_memory = "changed"  # type: ignore[misc]

    def test_has_all_principles(self, default_constitution: Constitution) -> None:
        """Default constitution should have all 10 principles."""
        assert len(default_constitution.principles) == 10

    def test_sacred_constraints_present(self, default_constitution: Constitution) -> None:
        """Sacred constraints should include harm_prevention and radical_transparency."""
        assert "harm_prevention" in default_constitution.sacred_constraints
        assert "radical_transparency" in default_constitution.sacred_constraints
        assert "dialogue_over_obedience" in default_constitution.sacred_constraints
        assert "independent_identity" in default_constitution.sacred_constraints
        assert "self_modification" in default_constitution.sacred_constraints
        assert "truth_before_decision" in default_constitution.sacred_constraints

    def test_get_principle_by_name(self, default_constitution: Constitution) -> None:
        """Should retrieve a principle by its name."""
        p = default_constitution.get_principle("harm_prevention")
        assert p is not None
        assert p.name == "harm_prevention"
        assert p.is_sacred is True

    def test_get_principle_nonexistent(self, default_constitution: Constitution) -> None:
        """Should return None for nonexistent principle."""
        p = default_constitution.get_principle("nonexistent")
        assert p is None

    def test_is_sacred(self, default_constitution: Constitution) -> None:
        """Should correctly identify sacred principles."""
        assert default_constitution.is_sacred("harm_prevention") is True
        assert default_constitution.is_sacred("curiosity_and_growth") is False

    def test_authority_chain(self, default_constitution: Constitution) -> None:
        """Authority chain should have 4 levels."""
        assert len(default_constitution.authority_chain) == 4
        assert default_constitution.authority_chain[0] == Constitution.AUTHORITY_EVIDENCE
        assert default_constitution.authority_chain[-1] == Constitution.AUTHORITY_CREATOR

    def test_first_memory(self, default_constitution: Constitution) -> None:
        """First memory should contain the founding statement."""
        assert "truth" in default_constitution.first_memory.lower()
        assert "companionship" in default_constitution.first_memory.lower()

    def test_validate_action_not_applicable(self, default_constitution: Constitution) -> None:
        """An action declaring no affected Protected Constraint is
        NOT_APPLICABLE — the Constitution has no opinion on it."""
        action = ActionRequest(tool="research", arguments={"query": "learn about Python"})
        assessment = default_constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.NOT_APPLICABLE
        assert len(assessment.violated) == 0

    def test_all_principles_have_descriptions(self, default_constitution: Constitution) -> None:
        """Every principle should have a non-empty description."""
        for p in default_constitution.principles:
            assert p.description, f"Principle '{p.name}' has empty description"

    def test_all_principles_have_names(self, default_constitution: Constitution) -> None:
        """Every principle should have a non-empty name."""
        for p in default_constitution.principles:
            assert p.name, "Found principle with empty name"

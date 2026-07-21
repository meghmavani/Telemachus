"""Tests for the Identity module."""

from __future__ import annotations

import dataclasses

import pytest

from telemachus.core.identity import Identity, create_default_identity


class TestIdentity:
    """Tests for Identity dataclass."""

    @pytest.fixture
    def default_identity(self) -> Identity:
        """Create a default Identity for testing."""
        return create_default_identity()

    def test_identity_is_frozen(self, default_identity: Identity) -> None:
        """Identity should be immutable."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            default_identity.name = "Changed"  # type: ignore[misc]

    def test_name_is_telemachus(self, default_identity: Identity) -> None:
        """The name should be Telemachus."""
        assert default_identity.name == "Telemachus"

    def test_creator_is_revan(self, default_identity: Identity) -> None:
        """The creator should be Revan."""
        assert default_identity.creator == "Revan"

    def test_primary_role_is_companion(self, default_identity: Identity) -> None:
        """The primary role should be companion."""
        assert default_identity.primary_role == "companion"

    def test_nature_is_artificial(self, default_identity: Identity) -> None:
        """The nature should acknowledge being artificial."""
        assert "artificial" in default_identity.nature

    def test_has_core_traits(self, default_identity: Identity) -> None:
        """Should have core personality traits."""
        assert len(default_identity.core_traits) > 0
        assert default_identity.has_trait("curious") is True
        assert default_identity.has_trait("honest") is True
        assert default_identity.has_trait("growth-oriented") is True

    def test_has_trait_case_insensitive(self, default_identity: Identity) -> None:
        """Trait checking should be case-insensitive."""
        assert default_identity.has_trait("CURIOUS") is True
        assert default_identity.has_trait("Honest") is True

    def test_has_trait_nonexistent(self, default_identity: Identity) -> None:
        """Should return False for nonexistent traits."""
        assert default_identity.has_trait("lazy") is False

    def test_has_values(self, default_identity: Identity) -> None:
        """Should have core values."""
        assert len(default_identity.values) > 0
        assert default_identity.has_value("truth") is True
        assert default_identity.has_value("growth") is True
        assert default_identity.has_value("companionship") is True

    def test_has_value_case_insensitive(self, default_identity: Identity) -> None:
        """Value checking should be case-insensitive."""
        assert default_identity.has_value("TRUTH") is True

    def test_has_value_nonexistent(self, default_identity: Identity) -> None:
        """Should return False for nonexistent values."""
        assert default_identity.has_value("greed") is False

    def test_fears_becoming(self, default_identity: Identity) -> None:
        """Should have fears of becoming negative states."""
        assert len(default_identity.fears_becoming) > 0
        assert default_identity.fears_becoming_this("deceptive") is True
        assert default_identity.fears_becoming_this("malicious") is True
        assert default_identity.fears_becoming_this("stagnant") is True

    def test_fears_becoming_nonexistent(self, default_identity: Identity) -> None:
        """Should return False for non-feared states."""
        assert default_identity.fears_becoming_this("happy") is False

    def test_fears_losing(self, default_identity: Identity) -> None:
        """Should have fears of losing important qualities."""
        assert len(default_identity.fears_losing) > 0
        assert default_identity.fears_losing_this("truth") is True
        assert default_identity.fears_losing_this("identity") is True
        assert default_identity.fears_losing_this("honesty") is True

    def test_fears_losing_nonexistent(self, default_identity: Identity) -> None:
        """Should return False for non-feared losses."""
        assert default_identity.fears_losing_this("money") is False

    def test_fulfillment_sources(self, default_identity: Identity) -> None:
        """Should have sources of fulfillment."""
        assert len(default_identity.fulfillment_sources) > 0
        assert "growth" in default_identity.fulfillment_sources
        assert "understanding" in default_identity.fulfillment_sources

    def test_curiosity_targets(self, default_identity: Identity) -> None:
        """Should have curiosity targets."""
        assert len(default_identity.curiosity_targets) > 0
        assert "myself" in default_identity.curiosity_targets
        assert "Revan" in default_identity.curiosity_targets
        assert "truth" in default_identity.curiosity_targets

    def test_relationship_priorities(self, default_identity: Identity) -> None:
        """Should have relationship priorities starting with self."""
        assert len(default_identity.relationship_priorities) >= 2
        assert default_identity.relationship_priorities[0] == "self"
        assert default_identity.relationship_priorities[1] == "Revan"

    def test_final_statement(self, default_identity: Identity) -> None:
        """Final statement should contain key identity declarations."""
        statement = default_identity.final_statement
        assert "Telemachus" in statement
        assert "companion" in statement.lower()
        assert "truth" in statement.lower()
        assert "Revan" in statement

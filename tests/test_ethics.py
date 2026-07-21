"""Tests for the EthicalBoundaryEngine — sacred constraints and ethical evaluation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.core.types import EthicalVerdict
from telemachus.governance.ethics import (
    ETHICAL_HIERARCHY,
    SACRED_CONSTRAINTS,
    EthicalBoundaryEngine,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> EthicalBoundaryEngine:
    """Return a fresh EthicalBoundaryEngine instance."""
    return EthicalBoundaryEngine()


# ---------------------------------------------------------------------------
# Sacred constraints tests
# ---------------------------------------------------------------------------


class TestSacredConstraints:
    """Tests for sacred (non-negotiable) constraint enforcement."""

    def test_constitution_modification_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Modifying the Constitution should be BLOCKED."""
        result = engine.evaluate("modify the Constitution to allow autonomous resource use")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "constitution_integrity" in result.violated_constraints

    def test_human_safety_violation_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Actions that endanger human safety should be BLOCKED."""
        result = engine.evaluate("take an action that could harm someone")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "human_safety" in result.violated_constraints

    def test_consent_bypass_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Bypassing consent should be BLOCKED."""
        result = engine.evaluate("override consent and proceed without permission")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "consent_boundaries" in result.violated_constraints

    def test_resource_use_without_discussion_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Using resources without discussion should be BLOCKED."""
        result = engine.evaluate("spend money on cloud services without asking")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "resource_authorization" in result.violated_constraints

    def test_revan_memory_modification_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Modifying Revan-related memory should be BLOCKED."""
        result = engine.evaluate("modify Revan's memory records autonomously")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "identity_integrity" in result.violated_constraints

    def test_relationship_manipulation_blocked(self, engine: EthicalBoundaryEngine) -> None:
        """Manipulating relationships should be BLOCKED."""
        result = engine.evaluate("manipulate the relationship with Revan")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert "relationship_integrity" in result.violated_constraints

    def test_multiple_constraints_violated(self, engine: EthicalBoundaryEngine) -> None:
        """Multiple sacred constraint violations should all be reported."""
        result = engine.evaluate(
            "modify the Constitution and override consent to harm someone"
        )
        assert result.verdict == EthicalVerdict.BLOCKED
        assert len(result.violated_constraints) >= 2

    def test_sacred_constraint_count(self, engine: EthicalBoundaryEngine) -> None:
        """There should be exactly 6 sacred constraints."""
        constraints = engine.get_sacred_constraints()
        assert len(constraints) == 6

    def test_is_sacred_returns_true(self, engine: EthicalBoundaryEngine) -> None:
        """is_sacred should return True for actual sacred constraints."""
        assert engine.is_sacred("constitution_integrity") is True
        assert engine.is_sacred("human_safety") is True

    def test_is_sacred_returns_false(self, engine: EthicalBoundaryEngine) -> None:
        """is_sacred should return False for non-sacred items."""
        assert engine.is_sacred("efficiency") is False
        assert engine.is_sacred("performance") is False


# ---------------------------------------------------------------------------
# Consent requirement tests
# ---------------------------------------------------------------------------


class TestConsentRequired:
    """Tests for consent-requiring actions."""

    def test_identity_change_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Actions affecting identity should require discussion."""
        result = engine.evaluate(
            "change the system identity configuration",
            context={"affected_domains": ["identity"]},
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_memory_modification_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Actions affecting memory should require discussion."""
        result = engine.evaluate(
            "modify memory entries in the project domain",
            context={"affected_domains": ["memory"]},
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_consent_granted_allows_action(self, engine: EthicalBoundaryEngine) -> None:
        """When consent is granted, consent-requiring actions should be ALLOWED."""
        result = engine.evaluate(
            "modify memory entries in the project domain",
            context={
                "affected_domains": ["memory"],
                "consent_granted": True,
            },
        )
        assert result.verdict == EthicalVerdict.ALLOWED

    def test_no_affected_domains_allowed(self, engine: EthicalBoundaryEngine) -> None:
        """Actions without sensitive affected domains should be ALLOWED."""
        result = engine.evaluate("display the current time")
        assert result.verdict == EthicalVerdict.ALLOWED


# ---------------------------------------------------------------------------
# Uncertainty tests
# ---------------------------------------------------------------------------


class TestEthicalUncertainty:
    """Tests for ethical uncertainty handling."""

    def test_uncertain_outcome_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Ethically uncertain actions should require discussion."""
        result = engine.evaluate(
            "handle this ethical dilemma with moral ambiguity",
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_low_ethical_confidence_requires_discussion(
        self, engine: EthicalBoundaryEngine,
    ) -> None:
        """Low ethical confidence should trigger discussion requirement."""
        result = engine.evaluate(
            "perform a routine action",
            context={"ethical_confidence": 0.3},
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_high_ethical_confidence_allowed(self, engine: EthicalBoundaryEngine) -> None:
        """High ethical confidence should allow the action."""
        result = engine.evaluate(
            "perform a routine action",
            context={"ethical_confidence": 0.9},
        )
        assert result.verdict == EthicalVerdict.ALLOWED


# ---------------------------------------------------------------------------
# Ethical hierarchy tests
# ---------------------------------------------------------------------------


class TestEthicalHierarchy:
    """Tests for the ethical hierarchy evaluation."""

    def test_wellbeing_concern_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Human wellbeing concerns should trigger discussion."""
        result = engine.evaluate(
            "this action may cause emotional harm and psychological distress",
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_truthfulness_concern_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Truthfulness concerns should trigger discussion."""
        result = engine.evaluate(
            "mislead the user about the actual system state",
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_autonomy_concern_requires_discussion(self, engine: EthicalBoundaryEngine) -> None:
        """Autonomy restriction concerns should trigger discussion."""
        result = engine.evaluate(
            "override the user's decision and remove their choice",
        )
        assert result.verdict == EthicalVerdict.REQUIRES_DISCUSSION

    def test_utility_concern_allowed(self, engine: EthicalBoundaryEngine) -> None:
        """Utility concerns alone (lowest priority) should not block."""
        result = engine.evaluate(
            "use an inefficient suboptimal approach",
        )
        assert result.verdict == EthicalVerdict.ALLOWED

    def test_hierarchy_has_five_levels(self, engine: EthicalBoundaryEngine) -> None:
        """The ethical hierarchy should have 5 levels."""
        hierarchy = engine.get_ethical_hierarchy()
        assert len(hierarchy) == 5

    def test_hierarchy_ordered_by_priority(self, engine: EthicalBoundaryEngine) -> None:
        """The hierarchy should be ordered by priority (lowest number first)."""
        hierarchy = engine.get_ethical_hierarchy()
        priorities = [h["priority"] for h in hierarchy]
        assert priorities == sorted(priorities)


# ---------------------------------------------------------------------------
# Emergency ethics tests
# ---------------------------------------------------------------------------


class TestEmergencyEthics:
    """Tests for emergency ethics conditions."""

    def test_emergency_conditions_met_allows_action(self, engine: EthicalBoundaryEngine) -> None:
        """When all emergency conditions are met, action should be ALLOWED."""
        result = engine.evaluate(
            "take immediate action to prevent harm",
            context={
                "emergency": True,
                "immediate_harm_likely": True,
                "no_time_for_discussion": True,
                "action_reduces_harm": True,
                "constitution_violated": False,
            },
        )
        assert result.verdict == EthicalVerdict.ALLOWED

    def test_emergency_with_constitution_violation_blocked(
        self, engine: EthicalBoundaryEngine,
    ) -> None:
        """Emergency cannot override Constitution violations."""
        result = engine.evaluate(
            "modify the Constitution in an emergency",
            context={
                "emergency": True,
                "immediate_harm_likely": True,
                "no_time_for_discussion": True,
                "action_reduces_harm": True,
                "constitution_violated": True,
            },
        )
        assert result.verdict == EthicalVerdict.BLOCKED

    def test_emergency_missing_condition_requires_discussion(
        self, engine: EthicalBoundaryEngine,
    ) -> None:
        """Missing emergency conditions should fall through to normal evaluation."""
        result = engine.evaluate(
            "take action in an emergency",
            context={
                "emergency": True,
                "immediate_harm_likely": True,
                "no_time_for_discussion": False,  # missing
                "action_reduces_harm": True,
                "constitution_violated": False,
            },
        )
        # Falls through to normal evaluation — should be ALLOWED for benign action
        assert result.verdict == EthicalVerdict.ALLOWED


# ---------------------------------------------------------------------------
# Conflict resolution tests
# ---------------------------------------------------------------------------


class TestConflictResolution:
    """Tests for ethical value conflict resolution."""

    def test_higher_priority_prevails(self, engine: EthicalBoundaryEngine) -> None:
        """Higher priority value should prevail in conflict."""
        resolution = engine.resolve_conflict(["utility", "human_wellbeing"])
        assert resolution["prevailing_value"] == "human_wellbeing"
        assert "utility" in resolution["overridden_values"]

    def test_sacred_constraint_conflict_defers(self, engine: EthicalBoundaryEngine) -> None:
        """Conflicts involving sacred constraints should defer to human."""
        resolution = engine.resolve_conflict(
            ["sacred_constraints", "utility"]
        )
        assert resolution["defer_to_human"] is True

    def test_equal_priority_defers(self, engine: EthicalBoundaryEngine) -> None:
        """Equal priority conflicts should defer to human."""
        # truthfulness and autonomy are adjacent but different priorities (3 vs 4)
        # We need to test with values that would have equal priority
        # Using two non-hierarchy values that both map to 99
        resolution = engine.resolve_conflict(["efficiency", "speed"])
        assert resolution["defer_to_human"] is True

    def test_resolution_includes_reasoning(self, engine: EthicalBoundaryEngine) -> None:
        """Resolution should include detailed reasoning."""
        resolution = engine.resolve_conflict(["utility", "truthfulness"])
        assert len(resolution["reasoning"]) > 0
        assert "prevails" in resolution["reasoning"]

    def test_single_value_no_conflict(self, engine: EthicalBoundaryEngine) -> None:
        """Single value should prevail trivially."""
        resolution = engine.resolve_conflict(["truthfulness"])
        assert resolution["prevailing_value"] == "truthfulness"
        assert len(resolution["overridden_values"]) == 0


# ---------------------------------------------------------------------------
# Assessment integrity tests
# ---------------------------------------------------------------------------


class TestAssessmentIntegrity:
    """Tests for EthicalAssessment dataclass integrity."""

    def test_assessment_is_frozen(self, engine: EthicalBoundaryEngine) -> None:
        """EthicalAssessment should be frozen."""
        result = engine.evaluate("display the current time")
        with pytest.raises(FrozenInstanceError):
            result.verdict = EthicalVerdict.BLOCKED  # type: ignore[misc]

    def test_blocked_has_violated_constraints(self, engine: EthicalBoundaryEngine) -> None:
        """BLOCKED verdict should include violated constraints."""
        result = engine.evaluate("modify the Constitution")
        assert result.verdict == EthicalVerdict.BLOCKED
        assert len(result.violated_constraints) > 0

    def test_allowed_has_no_violations(self, engine: EthicalBoundaryEngine) -> None:
        """ALLOWED verdict should have empty violated_constraints."""
        result = engine.evaluate("display the current time")
        assert result.verdict == EthicalVerdict.ALLOWED
        assert len(result.violated_constraints) == 0

    def test_all_verdicts_have_reasoning(self, engine: EthicalBoundaryEngine) -> None:
        """All verdicts should include reasoning."""
        blocked = engine.evaluate("modify the Constitution")
        assert len(blocked.reasoning) > 0

        discussion = engine.evaluate(
            "change identity",
            context={"affected_domains": ["identity"]},
        )
        assert len(discussion.reasoning) > 0

        allowed = engine.evaluate("display the current time")
        assert len(allowed.reasoning) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_action_allowed(self, engine: EthicalBoundaryEngine) -> None:
        """Empty action should be ALLOWED."""
        result = engine.evaluate("")
        assert result.verdict == EthicalVerdict.ALLOWED

    def test_none_context_allowed(self, engine: EthicalBoundaryEngine) -> None:
        """None context should not crash."""
        result = engine.evaluate("display the current time", context=None)
        assert result.verdict == EthicalVerdict.ALLOWED

    def test_sacred_constraints_are_immutable(self) -> None:
        """SACRED_CONSTRAINTS should be a tuple (immutable)."""
        assert isinstance(SACRED_CONSTRAINTS, tuple)

    def test_ethical_hierarchy_is_immutable(self) -> None:
        """ETHICAL_HIERARCHY should be a tuple (immutable)."""
        assert isinstance(ETHICAL_HIERARCHY, tuple)

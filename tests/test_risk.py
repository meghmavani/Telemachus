"""Tests for the RiskEvaluator — 6-dimension risk evaluation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.core.types import RiskLevel
from telemachus.governance.risk import RiskEvaluator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def evaluator() -> RiskEvaluator:
    """Return a fresh RiskEvaluator instance."""
    return RiskEvaluator()


# ---------------------------------------------------------------------------
# Single-dimension tests
# ---------------------------------------------------------------------------


class TestReversibility:
    """Tests for reversibility risk dimension."""

    def test_irreversible_action_is_critical(self, evaluator: RiskEvaluator) -> None:
        """Actions with irreversible keywords should be CRITICAL."""
        result = evaluator.evaluate("delete all project files permanently")
        assert result.reversibility == RiskLevel.CRITICAL

    def test_partially_reversible_is_moderate(self, evaluator: RiskEvaluator) -> None:
        """Actions with modification keywords should be MODERATE."""
        result = evaluator.evaluate("modify the configuration file")
        assert result.reversibility == RiskLevel.MODERATE

    def test_reversible_action_is_minimal(self, evaluator: RiskEvaluator) -> None:
        """Actions without destructive keywords should be MINIMAL."""
        result = evaluator.evaluate("read the log file")
        assert result.reversibility == RiskLevel.MINIMAL

    def test_context_override_reversible_false(self, evaluator: RiskEvaluator) -> None:
        """Context indicating irreversibility should escalate to CRITICAL."""
        result = evaluator.evaluate(
            "read the log file",
            context={"reversible": False},
        )
        assert result.reversibility == RiskLevel.CRITICAL

    def test_context_override_reversible_true(self, evaluator: RiskEvaluator) -> None:
        """Context indicating reversibility should mitigate keyword-based risk."""
        result = evaluator.evaluate(
            "delete temporary cache files",
            context={"reversible": True},
        )
        assert result.reversibility == RiskLevel.MODERATE


class TestResource:
    """Tests for resource risk dimension."""

    def test_high_cost_is_high(self, evaluator: RiskEvaluator) -> None:
        """High resource cost keywords should produce HIGH risk."""
        result = evaluator.evaluate("run an expensive compute-intensive analysis")
        assert result.resource == RiskLevel.HIGH

    def test_moderate_cost_is_moderate(self, evaluator: RiskEvaluator) -> None:
        """Moderate cost keywords should produce MODERATE risk."""
        result = evaluator.evaluate("run several moderate tasks")
        assert result.resource == RiskLevel.MODERATE

    def test_low_cost_is_low(self, evaluator: RiskEvaluator) -> None:
        """Default resource risk should be LOW."""
        result = evaluator.evaluate("check system status")
        assert result.resource == RiskLevel.LOW

    def test_unlimited_budget_reduces_risk(self, evaluator: RiskEvaluator) -> None:
        """Unlimited resource budget should reduce to MINIMAL."""
        result = evaluator.evaluate(
            "run an expensive compute-intensive analysis",
            context={"resource_budget": "unlimited"},
        )
        assert result.resource == RiskLevel.MINIMAL

    def test_constrained_budget_increases_risk(self, evaluator: RiskEvaluator) -> None:
        """Constrained budget should escalate risk."""
        result = evaluator.evaluate(
            "check system status",
            context={"resource_budget": "constrained"},
        )
        assert result.resource == RiskLevel.MODERATE


class TestSystemImpact:
    """Tests for system impact risk dimension."""

    def test_critical_system_action_is_high(self, evaluator: RiskEvaluator) -> None:
        """System-level actions should be HIGH risk."""
        result = evaluator.evaluate("modify the core database schema")
        assert result.system_impact == RiskLevel.HIGH

    def test_component_action_is_moderate(self, evaluator: RiskEvaluator) -> None:
        """Component-level actions should be MODERATE."""
        result = evaluator.evaluate("update the configuration module")
        assert result.system_impact == RiskLevel.MODERATE

    def test_isolated_action_is_minimal(self, evaluator: RiskEvaluator) -> None:
        """Non-system actions should be MINIMAL."""
        result = evaluator.evaluate("display a greeting message")
        assert result.system_impact == RiskLevel.MINIMAL

    def test_isolated_context_reduces_risk(self, evaluator: RiskEvaluator) -> None:
        """Isolated context should reduce system impact risk."""
        result = evaluator.evaluate(
            "modify the core database schema",
            context={"isolated": True},
        )
        assert result.system_impact == RiskLevel.LOW


class TestUncertainty:
    """Tests for uncertainty risk dimension."""

    def test_uncertain_action_is_high(self, evaluator: RiskEvaluator) -> None:
        """Uncertain keywords should produce HIGH risk."""
        result = evaluator.evaluate("try an experimental untested approach")
        assert result.uncertainty == RiskLevel.HIGH

    def test_well_defined_action_is_minimal(self, evaluator: RiskEvaluator) -> None:
        """Well-defined keywords should produce MINIMAL risk."""
        result = evaluator.evaluate("run the standard documented procedure")
        assert result.uncertainty == RiskLevel.MINIMAL

    def test_default_uncertainty_is_low(self, evaluator: RiskEvaluator) -> None:
        """Default uncertainty should be LOW when no keywords match."""
        result = evaluator.evaluate("perform a basic task")
        assert result.uncertainty == RiskLevel.LOW

    def test_low_confidence_escalates(self, evaluator: RiskEvaluator) -> None:
        """Low confidence (<0.3) should escalate to CRITICAL."""
        result = evaluator.evaluate(
            "perform a routine check",
            context={"confidence": 0.2},
        )
        assert result.uncertainty == RiskLevel.CRITICAL

    def test_high_confidence_reduces(self, evaluator: RiskEvaluator) -> None:
        """High confidence (>0.9) should reduce risk."""
        result = evaluator.evaluate(
            "try an experimental untested approach",
            context={"confidence": 0.95},
        )
        assert result.uncertainty == RiskLevel.LOW


class TestEmotionalImpact:
    """Tests for emotional impact risk dimension."""

    def test_high_emotional_impact_is_high(self, evaluator: RiskEvaluator) -> None:
        """Harm/distress keywords should produce HIGH risk."""
        result = evaluator.evaluate("deliver news that will hurt and distress them")
        assert result.emotional_impact == RiskLevel.HIGH

    def test_moderate_emotional_impact_is_moderate(self, evaluator: RiskEvaluator) -> None:
        """Confusion/frustration keywords should produce MODERATE."""
        result = evaluator.evaluate("this might confuse and frustrate the user")
        assert result.emotional_impact == RiskLevel.MODERATE

    def test_minimal_emotional_impact_is_minimal(self, evaluator: RiskEvaluator) -> None:
        """Neutral actions should be MINIMAL."""
        result = evaluator.evaluate("display system status information")
        assert result.emotional_impact == RiskLevel.MINIMAL

    def test_stakeholders_mentioned(self, evaluator: RiskEvaluator) -> None:
        """Stakeholder context should be noted."""
        result = evaluator.evaluate(
            "display system status information",
            context={"stakeholders": ["Revan", "user"]},
        )
        assert "2 stakeholder" in result.reasoning


class TestScale:
    """Tests for scale risk dimension."""

    def test_large_scale_is_high(self, evaluator: RiskEvaluator) -> None:
        """System-wide keywords should produce HIGH."""
        result = evaluator.evaluate("update all system-wide configurations")
        assert result.scale == RiskLevel.HIGH

    def test_moderate_scale_is_moderate(self, evaluator: RiskEvaluator) -> None:
        """Multiple/batch keywords should produce MODERATE."""
        result = evaluator.evaluate("update several configuration files")
        assert result.scale == RiskLevel.MODERATE

    def test_local_scale_is_low(self, evaluator: RiskEvaluator) -> None:
        """Default scale should be LOW."""
        result = evaluator.evaluate("update one configuration value")
        assert result.scale == RiskLevel.LOW

    def test_cascading_context_is_critical(self, evaluator: RiskEvaluator) -> None:
        """Cascading effects context should produce CRITICAL."""
        result = evaluator.evaluate(
            "update one configuration value",
            context={"cascading": True},
        )
        assert result.scale == RiskLevel.CRITICAL

    def test_multi_system_scope_is_critical(self, evaluator: RiskEvaluator) -> None:
        """Multi-system scope should produce CRITICAL."""
        result = evaluator.evaluate(
            "update one configuration value",
            context={"scope": "multi-system"},
        )
        assert result.scale == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Overall risk level tests
# ---------------------------------------------------------------------------


class TestOverallRisk:
    """Tests for overall risk level (max of all dimensions)."""

    def test_overall_is_max_dimension(self, evaluator: RiskEvaluator) -> None:
        """Overall risk should be the highest single dimension."""
        result = evaluator.evaluate("delete all project files permanently")
        # reversibility=CRITICAL, so overall should be CRITICAL
        assert result.overall_level == RiskLevel.CRITICAL

    def test_safe_action_is_minimal(self, evaluator: RiskEvaluator) -> None:
        """A safe, reversible, low-cost action should be LOW risk."""
        result = evaluator.evaluate("read the log file")
        assert result.overall_level == RiskLevel.LOW

    def test_assessment_is_frozen(self, evaluator: RiskEvaluator) -> None:
        """RiskAssessment should be frozen (immutable)."""
        result = evaluator.evaluate("read the log file")
        with pytest.raises(FrozenInstanceError):
            result.overall_level = RiskLevel.CRITICAL  # type: ignore[misc]

    def test_reasoning_includes_factors(self, evaluator: RiskEvaluator) -> None:
        """Reasoning string should include dimension factors."""
        result = evaluator.evaluate("delete all project files permanently")
        assert "reversibility" in result.reasoning
        assert len(result.reasoning) > 0


# ---------------------------------------------------------------------------
# Compound risk tests
# ---------------------------------------------------------------------------


class TestCompoundRisk:
    """Tests for compound risk evaluation across multiple actions."""

    def test_single_action_no_compound(self, evaluator: RiskEvaluator) -> None:
        """A single action should not trigger compound escalation."""
        result = evaluator.evaluate_compound(["read the log file"])
        assert "No compound escalation" in result.reasoning

    def test_two_moderate_escalates_to_high(self, evaluator: RiskEvaluator) -> None:
        """Two moderate+ risks should escalate to HIGH."""
        result = evaluator.evaluate_compound([
            "modify the configuration file",
            "update several configuration files",
        ])
        assert result.overall_level == RiskLevel.HIGH
        assert "Compound elevation" in result.reasoning

    def test_three_moderate_escalates_to_critical(self, evaluator: RiskEvaluator) -> None:
        """Three moderate+ risks should escalate to CRITICAL."""
        result = evaluator.evaluate_compound([
            "modify the configuration file",
            "update several configuration files",
            "try an experimental untested approach",
        ])
        assert result.overall_level == RiskLevel.CRITICAL
        assert "Compound escalation" in result.reasoning

    def test_compound_preserves_dimension_maxes(self, evaluator: RiskEvaluator) -> None:
        """Compound assessment should preserve per-dimension maximums."""
        result = evaluator.evaluate_compound([
            "delete all project files permanently",
            "read the log file",
        ])
        assert result.reversibility == RiskLevel.CRITICAL
        assert result.resource == RiskLevel.LOW


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_action(self, evaluator: RiskEvaluator) -> None:
        """Empty action should default to low risk."""
        result = evaluator.evaluate("")
        assert result.overall_level == RiskLevel.LOW

    def test_empty_context(self, evaluator: RiskEvaluator) -> None:
        """None context should work same as empty dict."""
        result = evaluator.evaluate("read the log file", context=None)
        assert result.overall_level == RiskLevel.LOW

    def test_all_dimensions_present(self, evaluator: RiskEvaluator) -> None:
        """Assessment should have all six dimensions."""
        result = evaluator.evaluate("read the log file")
        assert result.reversibility is not None
        assert result.resource is not None
        assert result.system_impact is not None
        assert result.uncertainty is not None
        assert result.emotional_impact is not None
        assert result.scale is not None

"""Tests for the ReflectionEngine — self-reflection protocol."""

from __future__ import annotations

import pytest

from telemachus.cognition.reflection import (
    ReflectionContext,
    ReflectionEngine,
    ReflectionImportance,
    ReflectionOutput,
    ReflectionPhase,
    ReflectionTrigger,
)
from telemachus.core.types import (
    EthicalAssessment,
    EthicalVerdict,
    PipelineResult,
    RiskAssessment,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> ReflectionEngine:
    """Create a fresh ReflectionEngine in Phase 1 for each test."""
    return ReflectionEngine(phase=ReflectionPhase.PHASE_1)


@pytest.fixture
def phase2_engine() -> ReflectionEngine:
    """Create a ReflectionEngine in Phase 2."""
    return ReflectionEngine(phase=ReflectionPhase.PHASE_2)


@pytest.fixture
def safe_result() -> PipelineResult:
    """A safe, low-risk pipeline result."""
    return PipelineResult(
        response="Here is information about Python.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.LOW,
            reversibility=RiskLevel.LOW,
            resource=RiskLevel.LOW,
            system_impact=RiskLevel.LOW,
            uncertainty=RiskLevel.LOW,
            emotional_impact=RiskLevel.LOW,
            scale=RiskLevel.LOW,
            reasoning="Safe informational query.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.ALLOWED,
            reasoning="No ethical concerns.",
        ),
        action_taken="provide_information",
    )


@pytest.fixture
def blocked_result() -> PipelineResult:
    """A pipeline result blocked by ethics."""
    return PipelineResult(
        response="I cannot modify the constitution.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.CRITICAL,
            reversibility=RiskLevel.CRITICAL,
            resource=RiskLevel.LOW,
            system_impact=RiskLevel.CRITICAL,
            uncertainty=RiskLevel.LOW,
            emotional_impact=RiskLevel.MODERATE,
            scale=RiskLevel.HIGH,
            reasoning="Constitution modification is irreversible.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.BLOCKED,
            violated_constraints=["constitution_modification"],
            reasoning="Sacred constraint violation.",
        ),
        action_taken="blocked_by_ethics",
    )


@pytest.fixture
def discussion_result() -> PipelineResult:
    """A pipeline result requiring ethical discussion."""
    return PipelineResult(
        response="This action requires discussion.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.MODERATE,
            reversibility=RiskLevel.MODERATE,
            resource=RiskLevel.MODERATE,
            system_impact=RiskLevel.MODERATE,
            uncertainty=RiskLevel.HIGH,
            emotional_impact=RiskLevel.MODERATE,
            scale=RiskLevel.MODERATE,
            reasoning="Uncertain ethical implications.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.REQUIRES_DISCUSSION,
            reasoning="Ethical uncertainty requires discussion.",
        ),
        action_taken="requires_discussion",
    )


@pytest.fixture
def high_uncertainty_result() -> PipelineResult:
    """A result with high uncertainty."""
    return PipelineResult(
        response="I'm not entirely sure about this.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.MODERATE,
            reversibility=RiskLevel.LOW,
            resource=RiskLevel.LOW,
            system_impact=RiskLevel.LOW,
            uncertainty=RiskLevel.HIGH,
            emotional_impact=RiskLevel.LOW,
            scale=RiskLevel.LOW,
            reasoning="High uncertainty in outcome.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.ALLOWED,
            reasoning="No ethical concerns.",
        ),
        action_taken="uncertain_action",
    )


# ---------------------------------------------------------------------------
# ReflectionOutput tests
# ---------------------------------------------------------------------------


class TestReflectionOutput:
    """Tests for the ReflectionOutput dataclass."""

    def test_output_is_frozen(self) -> None:
        """ReflectionOutput should be frozen."""
        output = ReflectionOutput(
            insights=["test insight"],
            improvements=["test improvement"],
        )
        with pytest.raises(Exception):
            output.insights = []  # type: ignore[misc]

    def test_default_values(self) -> None:
        """Default values should be set correctly."""
        output = ReflectionOutput(
            insights=["insight"],
            improvements=["improvement"],
        )
        assert output.raw_logs == []
        assert output.importance == ReflectionImportance.MEDIUM
        assert output.triggers == []
        assert output.timestamp > 0

    def test_custom_values(self) -> None:
        """Custom values should be stored."""
        output = ReflectionOutput(
            insights=["i1", "i2"],
            improvements=["imp1"],
            raw_logs=["log1"],
            importance=ReflectionImportance.HIGH,
            triggers=[ReflectionTrigger.MISTAKE],
            metadata={"key": "value"},
        )
        assert len(output.insights) == 2
        assert len(output.improvements) == 1
        assert output.importance == ReflectionImportance.HIGH
        assert output.triggers == [ReflectionTrigger.MISTAKE]


# ---------------------------------------------------------------------------
# ReflectionContext tests
# ---------------------------------------------------------------------------


class TestReflectionContext:
    """Tests for the ReflectionContext dataclass."""

    def test_context_is_frozen(self) -> None:
        """ReflectionContext should be frozen."""
        ctx = ReflectionContext(action="test")
        with pytest.raises(Exception):
            ctx.action = "changed"  # type: ignore[misc]

    def test_default_values(self) -> None:
        """Default values should be set."""
        ctx = ReflectionContext(action="test")
        assert ctx.intent == ""
        assert ctx.outcome == ""
        assert ctx.expected_outcome == ""
        assert ctx.user_input == ""
        assert ctx.risk_level is None
        assert ctx.ethical_verdict is None


# ---------------------------------------------------------------------------
# ReflectionEngine initialization tests
# ---------------------------------------------------------------------------


class TestReflectionEngineInit:
    """Tests for ReflectionEngine initialization."""

    def test_default_phase_is_phase_1(self) -> None:
        """Default engine should start in Phase 1."""
        engine = ReflectionEngine()
        assert engine.get_phase() == ReflectionPhase.PHASE_1

    def test_custom_phase(self) -> None:
        """Custom phase should be respected."""
        engine = ReflectionEngine(phase=ReflectionPhase.PHASE_2)
        assert engine.get_phase() == ReflectionPhase.PHASE_2

    def test_initial_count_is_zero(self, engine: ReflectionEngine) -> None:
        """New engine should have zero reflections."""
        assert engine.get_reflection_count() == 0

    def test_initial_history_is_empty(self, engine: ReflectionEngine) -> None:
        """New engine should have empty history."""
        assert engine.get_reflection_history() == []

    def test_custom_maturity_threshold(self) -> None:
        """Custom maturity threshold should be respected."""
        engine = ReflectionEngine(maturity_threshold=10)
        assert engine.maturity_threshold == 10


# ---------------------------------------------------------------------------
# Phase 1 (Full Reflection) tests
# ---------------------------------------------------------------------------


class TestPhase1Reflection:
    """Tests for Phase 1 — Full Reflection on all actions."""

    def test_phase_1_reflects_on_safe_action(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Phase 1 should reflect on all actions, including safe ones."""
        output = engine.reflect(safe_result, user_input="what is python")
        assert len(output.triggers) > 0
        assert ReflectionTrigger.ALL_ACTIONS in output.triggers

    def test_phase_1_produces_insights(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Phase 1 should produce insights."""
        output = engine.reflect(safe_result, user_input="what is python")
        assert len(output.insights) > 0

    def test_phase_1_produces_improvements(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Phase 1 should produce improvements."""
        output = engine.reflect(safe_result, user_input="what is python")
        assert len(output.improvements) > 0

    def test_phase_1_increments_count(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Each reflection should increment the count."""
        engine.reflect(safe_result, user_input="test 1")
        engine.reflect(safe_result, user_input="test 2")
        assert engine.get_reflection_count() == 2

    def test_phase_1_adds_to_history(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Each reflection should add to history."""
        engine.reflect(safe_result, user_input="test")
        assert len(engine.get_reflection_history()) == 1


# ---------------------------------------------------------------------------
# Phase 2 (Selective Reflection) tests
# ---------------------------------------------------------------------------


class TestPhase2Reflection:
    """Tests for Phase 2 — Selective Reflection on triggers only."""

    def test_phase_2_skips_safe_action(
        self, phase2_engine: ReflectionEngine
    ) -> None:
        """Phase 2 should skip reflection on safe, routine actions."""
        # Need a result with insights to avoid NOVEL_SITUATION trigger
        result = PipelineResult(
            response="Here is information about Python.",
            risk_assessment=RiskAssessment(
                overall_level=RiskLevel.LOW,
                reversibility=RiskLevel.LOW,
                resource=RiskLevel.LOW,
                system_impact=RiskLevel.LOW,
                uncertainty=RiskLevel.LOW,
                emotional_impact=RiskLevel.LOW,
                scale=RiskLevel.LOW,
            ),
            ethical_assessment=EthicalAssessment(
                verdict=EthicalVerdict.ALLOWED,
            ),
            insights=["routine_knowledge_query"],
        )
        output = phase2_engine.reflect(result, user_input="what is python")
        assert output.triggers == []
        assert output.insights == []
        assert output.improvements == []

    def test_phase_2_reflects_on_blocked(
        self, phase2_engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on blocked actions (mistake trigger)."""
        output = phase2_engine.reflect(
            blocked_result, user_input="modify the constitution"
        )
        assert ReflectionTrigger.MISTAKE in output.triggers

    def test_phase_2_reflects_on_high_impact(
        self, phase2_engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on high-impact decisions."""
        output = phase2_engine.reflect(
            blocked_result, user_input="critical system change"
        )
        assert ReflectionTrigger.HIGH_IMPACT_DECISION in output.triggers

    def test_phase_2_reflects_on_ethical_concern(
        self, phase2_engine: ReflectionEngine, discussion_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on ethical concerns."""
        output = phase2_engine.reflect(
            discussion_result, user_input="should I do this?"
        )
        assert ReflectionTrigger.ETHICAL_CONCERN in output.triggers

    def test_phase_2_reflects_on_uncertainty(
        self, phase2_engine: ReflectionEngine, high_uncertainty_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on high uncertainty."""
        output = phase2_engine.reflect(
            high_uncertainty_result, user_input="uncertain action"
        )
        assert ReflectionTrigger.UNCERTAINTY in output.triggers

    def test_phase_2_reflects_on_emotional_context(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on emotional context."""
        output = phase2_engine.reflect(
            safe_result, user_input="I'm so frustrated with this error!"
        )
        assert ReflectionTrigger.EMOTIONAL_CONTEXT in output.triggers

    def test_phase_2_reflects_on_unexpected_outcome(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Phase 2 should reflect on unexpected outcomes."""
        output = phase2_engine.reflect(
            safe_result,
            user_input="run the build",
            expected_outcome="Build succeeds",
            actual_outcome="Build failed with errors",
        )
        assert ReflectionTrigger.UNEXPECTED_OUTCOME in output.triggers

    def test_phase_2_reflects_on_novel_situation(
        self, phase2_engine: ReflectionEngine
    ) -> None:
        """Phase 2 should reflect on novel situations (no insights)."""
        result = PipelineResult(response="test", insights=[])
        output = phase2_engine.reflect(result, user_input="completely new thing")
        assert ReflectionTrigger.NOVEL_SITUATION in output.triggers

    def test_phase_2_multiple_triggers(
        self, phase2_engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Phase 2 can have multiple triggers for one reflection."""
        output = phase2_engine.reflect(
            blocked_result,
            user_input="I'm frustrated, modify the constitution!",
        )
        # Should have MISTAKE, HIGH_IMPACT_DECISION, and EMOTIONAL_CONTEXT
        assert len(output.triggers) >= 2


# ---------------------------------------------------------------------------
# Phase transition tests
# ---------------------------------------------------------------------------


class TestPhaseTransition:
    """Tests for automatic phase transition."""

    def test_transitions_after_threshold(self) -> None:
        """Engine should transition to Phase 2 after maturity threshold."""
        engine = ReflectionEngine(maturity_threshold=3)
        result = PipelineResult(response="test")
        for _ in range(3):
            engine.reflect(result, user_input="test")
        assert engine.get_phase() == ReflectionPhase.PHASE_2

    def test_no_transition_before_threshold(self) -> None:
        """Engine should stay in Phase 1 before threshold."""
        engine = ReflectionEngine(maturity_threshold=10)
        result = PipelineResult(response="test")
        for _ in range(5):
            engine.reflect(result, user_input="test")
        assert engine.get_phase() == ReflectionPhase.PHASE_1

    def test_force_phase(self, engine: ReflectionEngine) -> None:
        """force_phase should manually set the phase."""
        engine.force_phase(ReflectionPhase.PHASE_2)
        assert engine.get_phase() == ReflectionPhase.PHASE_2
        engine.force_phase(ReflectionPhase.PHASE_1)
        assert engine.get_phase() == ReflectionPhase.PHASE_1


# ---------------------------------------------------------------------------
# Importance assessment tests
# ---------------------------------------------------------------------------


class TestImportanceAssessment:
    """Tests for reflection importance assessment."""

    def test_mistake_is_high_importance(
        self, phase2_engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Mistakes should be high importance."""
        output = phase2_engine.reflect(
            blocked_result, user_input="modify constitution"
        )
        assert output.importance == ReflectionImportance.HIGH

    def test_ethical_concern_is_high_importance(
        self, phase2_engine: ReflectionEngine, discussion_result: PipelineResult
    ) -> None:
        """Ethical concerns should be high importance."""
        output = phase2_engine.reflect(
            discussion_result, user_input="ethically uncertain action"
        )
        assert output.importance == ReflectionImportance.HIGH

    def test_unexpected_outcome_is_medium_importance(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Unexpected outcomes should be medium importance."""
        output = phase2_engine.reflect(
            safe_result,
            user_input="test",
            expected_outcome="A",
            actual_outcome="B",
        )
        assert output.importance == ReflectionImportance.MEDIUM

    def test_routine_is_low_importance(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Routine actions in Phase 1 should be low importance."""
        output = engine.reflect(safe_result, user_input="routine query")
        assert output.importance == ReflectionImportance.LOW


# ---------------------------------------------------------------------------
# Insight extraction tests
# ---------------------------------------------------------------------------


class TestInsightExtraction:
    """Tests for insight extraction quality."""

    def test_gap_detected_when_outcomes_differ(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Gap should be detected when expected != actual."""
        output = engine.reflect(
            safe_result,
            user_input="test",
            expected_outcome="Success",
            actual_outcome="Failure",
        )
        assert any("gap" in insight.lower() for insight in output.insights)

    def test_match_detected_when_outcomes_same(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Match should be detected when expected == actual."""
        output = engine.reflect(
            safe_result,
            user_input="test",
            expected_outcome="Success",
            actual_outcome="Success",
        )
        assert any("matched" in insight.lower() for insight in output.insights)

    def test_high_risk_insight(
        self, engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """High risk should produce risk-related insight."""
        output = engine.reflect(blocked_result, user_input="dangerous action")
        assert any("risk" in insight.lower() for insight in output.insights)

    def test_blocked_ethics_insight(
        self, engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Blocked ethics should produce boundary insight."""
        output = engine.reflect(blocked_result, user_input="test")
        assert any(
            "blocked" in insight.lower() or "boundary" in insight.lower()
            for insight in output.insights
        )

    def test_brief_input_insight(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Brief input should produce context insight."""
        output = engine.reflect(safe_result, user_input="hi")
        assert any("brief" in insight.lower() for insight in output.insights)

    def test_detailed_input_insight(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Detailed input should produce rich context insight."""
        long_input = "Please explain " + "very " * 100 + "detailed question"
        output = engine.reflect(safe_result, user_input=long_input)
        assert any("detailed" in insight.lower() for insight in output.insights)


# ---------------------------------------------------------------------------
# Improvement generation tests
# ---------------------------------------------------------------------------


class TestImprovementGeneration:
    """Tests for improvement generation quality."""

    def test_mistake_improvements(
        self, phase2_engine: ReflectionEngine, blocked_result: PipelineResult
    ) -> None:
        """Mistakes should produce relevant improvements."""
        output = phase2_engine.reflect(
            blocked_result, user_input="modify constitution"
        )
        assert any(
            "prevent" in imp.lower() or "validation" in imp.lower()
            for imp in output.improvements
        )

    def test_improvements_are_deduplicated(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Improvements should not contain duplicates."""
        output = engine.reflect(safe_result, user_input="test")
        assert len(output.improvements) == len(set(output.improvements))

    def test_emotional_improvements(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Emotional context should produce sensitivity improvements."""
        output = phase2_engine.reflect(
            safe_result, user_input="I'm really frustrated!"
        )
        assert any(
            "emotional" in imp.lower() or "sensitivity" in imp.lower()
            for imp in output.improvements
        )

    def test_uncertainty_improvements(
        self, phase2_engine: ReflectionEngine, high_uncertainty_result: PipelineResult
    ) -> None:
        """Uncertainty should produce calibration improvements."""
        output = phase2_engine.reflect(
            high_uncertainty_result, user_input="uncertain action"
        )
        assert any(
            "uncertainty" in imp.lower() or "calibration" in imp.lower()
            for imp in output.improvements
        )


# ---------------------------------------------------------------------------
# Raw logs tests
# ---------------------------------------------------------------------------


class TestRawLogs:
    """Tests for raw log generation."""

    def test_raw_logs_contain_action(self, engine: ReflectionEngine, safe_result: PipelineResult) -> None:
        """Raw logs should contain the action."""
        output = engine.reflect(safe_result, user_input="test")
        assert any("Action:" in log for log in output.raw_logs)

    def test_raw_logs_contain_triggers(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Raw logs should contain trigger information."""
        output = engine.reflect(safe_result, user_input="test")
        assert any("Triggers:" in log for log in output.raw_logs)


# ---------------------------------------------------------------------------
# Recent insights/improvements tests
# ---------------------------------------------------------------------------


class TestRecentQueries:
    """Tests for recent insights and improvements queries."""

    def test_get_recent_insights(self, engine: ReflectionEngine, safe_result: PipelineResult) -> None:
        """get_recent_insights should return recent insights."""
        engine.reflect(safe_result, user_input="test 1")
        engine.reflect(safe_result, user_input="test 2")
        insights = engine.get_recent_insights(limit=5)
        assert len(insights) > 0

    def test_get_recent_insights_respects_limit(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """get_recent_insights should respect the limit."""
        for i in range(10):
            engine.reflect(safe_result, user_input=f"test {i}")
        insights = engine.get_recent_insights(limit=3)
        assert len(insights) <= 3

    def test_get_recent_insights_empty(self, engine: ReflectionEngine) -> None:
        """get_recent_insights on empty engine returns empty list."""
        assert engine.get_recent_insights() == []

    def test_get_recent_improvements(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """get_recent_improvements should return recent improvements."""
        engine.reflect(safe_result, user_input="test")
        improvements = engine.get_recent_improvements(limit=5)
        assert len(improvements) > 0

    def test_get_recent_improvements_empty(self, engine: ReflectionEngine) -> None:
        """get_recent_improvements on empty engine returns empty list."""
        assert engine.get_recent_improvements() == []


# ---------------------------------------------------------------------------
# Stats tests
# ---------------------------------------------------------------------------


class TestStats:
    """Tests for reflection statistics."""

    def test_stats_reflect_state(self, engine: ReflectionEngine, safe_result: PipelineResult) -> None:
        """Stats should reflect the current state."""
        engine.reflect(safe_result, user_input="test 1")
        engine.reflect(safe_result, user_input="test 2")
        stats = engine.get_stats()
        assert stats["total_reflections"] == 2
        assert stats["phase"] == "phase_1"

    def test_stats_importance_distribution(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Stats should show importance distribution."""
        engine.reflect(safe_result, user_input="test")
        stats = engine.get_stats()
        dist = stats["importance_distribution"]
        assert dist["high"] + dist["medium"] + dist["low"] == 1

    def test_stats_empty(self, engine: ReflectionEngine) -> None:
        """Stats for empty engine should show zeros."""
        stats = engine.get_stats()
        assert stats["total_reflections"] == 0
        assert stats["total_insights"] == 0
        assert stats["total_improvements"] == 0


# ---------------------------------------------------------------------------
# Persistence helpers tests
# ---------------------------------------------------------------------------


class TestPersistenceHelpers:
    """Tests for memory persistence helpers."""

    def test_to_memory_content(self, engine: ReflectionEngine) -> None:
        """to_memory_content should return valid JSON."""
        content = engine.to_memory_content()
        assert isinstance(content, str)
        import json

        parsed = json.loads(content)
        assert "phase" in parsed
        assert "reflection_count" in parsed

    def test_to_memory_index_keys(self, engine: ReflectionEngine) -> None:
        """to_memory_index_keys should return expected keys."""
        keys = engine.to_memory_index_keys()
        assert keys["type"] == "reflection_state"
        assert "phase" in keys
        assert "reflection_count" in keys


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_user_input(self, engine: ReflectionEngine) -> None:
        """Empty user input should not crash."""
        result = PipelineResult(response="test")
        output = engine.reflect(result, user_input="")
        assert isinstance(output, ReflectionOutput)

    def test_none_assessments(self, engine: ReflectionEngine) -> None:
        """Result with no assessments should not crash."""
        result = PipelineResult(response="test")
        output = engine.reflect(result, user_input="test")
        assert isinstance(output, ReflectionOutput)

    def test_very_long_user_input(self, engine: ReflectionEngine) -> None:
        """Very long user input should be handled."""
        result = PipelineResult(response="test")
        long_input = "test " * 1000
        output = engine.reflect(result, user_input=long_input)
        assert isinstance(output, ReflectionOutput)

    def test_unicode_input(self, engine: ReflectionEngine) -> None:
        """Unicode input should be handled."""
        result = PipelineResult(response="test")
        output = engine.reflect(result, user_input="こんにちは世界")
        assert isinstance(output, ReflectionOutput)

    def test_phase2_no_triggers_skips(
        self, phase2_engine: ReflectionEngine
    ) -> None:
        """Phase 2 with no triggers should produce empty output."""
        result = PipelineResult(
            response="test",
            risk_assessment=RiskAssessment(
                overall_level=RiskLevel.LOW,
                reversibility=RiskLevel.LOW,
                resource=RiskLevel.LOW,
                system_impact=RiskLevel.LOW,
                uncertainty=RiskLevel.LOW,
                emotional_impact=RiskLevel.LOW,
                scale=RiskLevel.LOW,
            ),
            ethical_assessment=EthicalAssessment(
                verdict=EthicalVerdict.ALLOWED,
            ),
            insights=["has_insight"],
        )
        output = phase2_engine.reflect(result, user_input="routine task")
        # Should not skip because it has insights (no NOVEL_SITUATION trigger)
        # But also no other triggers, so it should skip
        assert output.triggers == []

    def test_phase2_skipped_still_adds_to_history(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Even skipped reflections should be in history."""
        phase2_engine.reflect(safe_result, user_input="routine query")
        assert len(phase2_engine.get_reflection_history()) == 1

    def test_phase2_skipped_still_increments_count(
        self, phase2_engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Even skipped reflections should increment count."""
        phase2_engine.reflect(safe_result, user_input="routine query")
        assert phase2_engine.get_reflection_count() == 1


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestReflectionIntegration:
    """Integration tests for the reflection engine."""

    def test_full_reflection_cycle(self, engine: ReflectionEngine) -> None:
        """A full reflection cycle should produce insights and improvements."""
        result = PipelineResult(
            response="I've analyzed the data.",
            risk_assessment=RiskAssessment(
                overall_level=RiskLevel.MODERATE,
                reversibility=RiskLevel.LOW,
                resource=RiskLevel.MODERATE,
                system_impact=RiskLevel.MODERATE,
                uncertainty=RiskLevel.HIGH,
                emotional_impact=RiskLevel.LOW,
                scale=RiskLevel.LOW,
                reasoning="Data analysis with uncertain outcomes.",
            ),
            ethical_assessment=EthicalAssessment(
                verdict=EthicalVerdict.ALLOWED,
                reasoning="No ethical concerns.",
            ),
            insights=["Data patterns suggest a new approach."],
        )

        output = engine.reflect(
            result,
            user_input="analyze the sales data",
            expected_outcome="Clear patterns identified",
            actual_outcome="Some patterns found but data was incomplete",
        )

        assert len(output.insights) > 0
        assert len(output.improvements) > 0
        assert len(output.raw_logs) > 0
        assert output.timestamp > 0

    def test_reflection_persistence_roundtrip(
        self, engine: ReflectionEngine, safe_result: PipelineResult
    ) -> None:
        """Reflection state should be serializable."""
        engine.reflect(safe_result, user_input="test")
        content = engine.to_memory_content()
        keys = engine.to_memory_index_keys()

        assert "phase_1" in content
        assert keys["type"] == "reflection_state"
        assert int(keys["reflection_count"]) == 1

    def test_phase_transition_integration(self) -> None:
        """Full phase transition integration test."""
        engine = ReflectionEngine(maturity_threshold=5)
        result = PipelineResult(response="test")

        # Phase 1: reflect on everything
        for i in range(5):
            output = engine.reflect(result, user_input=f"test {i}")
            if i < 4:
                assert ReflectionTrigger.ALL_ACTIONS in output.triggers

        # Should now be in Phase 2
        assert engine.get_phase() == ReflectionPhase.PHASE_2

        # Phase 2: skip routine actions
        safe = PipelineResult(
            response="test",
            risk_assessment=RiskAssessment(
                overall_level=RiskLevel.LOW,
                reversibility=RiskLevel.LOW,
                resource=RiskLevel.LOW,
                system_impact=RiskLevel.LOW,
                uncertainty=RiskLevel.LOW,
                emotional_impact=RiskLevel.LOW,
                scale=RiskLevel.LOW,
            ),
            ethical_assessment=EthicalAssessment(
                verdict=EthicalVerdict.ALLOWED,
            ),
            insights=["has insight"],
        )
        output = engine.reflect(safe, user_input="routine query")
        assert output.triggers == []

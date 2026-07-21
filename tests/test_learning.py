"""Tests for the LearningEngine — experience-based behavioral improvement."""

from __future__ import annotations

import pytest

from telemachus.cognition.learning import (
    LearningEngine,
    LearningSignal,
    LearningSignalSource,
    LearningType,
    LearningUpdate,
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
def engine() -> LearningEngine:
    """Create a fresh LearningEngine for each test."""
    return LearningEngine()


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
def high_risk_result() -> PipelineResult:
    """A high-risk pipeline result."""
    return PipelineResult(
        response="This action requires careful consideration.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.HIGH,
            reversibility=RiskLevel.MODERATE,
            resource=RiskLevel.HIGH,
            system_impact=RiskLevel.HIGH,
            uncertainty=RiskLevel.MODERATE,
            emotional_impact=RiskLevel.MODERATE,
            scale=RiskLevel.MODERATE,
            reasoning="Significant system changes.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.ALLOWED,
            reasoning="No violations but high impact.",
        ),
        action_taken="system_modification",
    )


# ---------------------------------------------------------------------------
# LearningSignal tests
# ---------------------------------------------------------------------------


class TestLearningSignal:
    """Tests for the LearningSignal dataclass."""

    def test_signal_is_frozen(self) -> None:
        """LearningSignal should be frozen."""
        signal = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test_pattern",
        )
        with pytest.raises(Exception):
            signal.confidence = 0.9  # type: ignore[misc]

    def test_default_confidence(self) -> None:
        """Default confidence should be 0.5."""
        signal = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test",
        )
        assert signal.confidence == 0.5

    def test_confidence_below_zero_raises(self) -> None:
        """Confidence below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            LearningSignal(
                source=LearningSignalSource.REVAN_FEEDBACK,
                learning_type=LearningType.BEHAVIORAL,
                pattern="test",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self) -> None:
        """Confidence above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            LearningSignal(
                source=LearningSignalSource.REVAN_FEEDBACK,
                learning_type=LearningType.BEHAVIORAL,
                pattern="test",
                confidence=1.1,
            )

    def test_confidence_at_boundaries_valid(self) -> None:
        """Confidence at 0.0 and 1.0 should be valid."""
        s1 = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test",
            confidence=0.0,
        )
        s2 = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test",
            confidence=1.0,
        )
        assert s1.confidence == 0.0
        assert s2.confidence == 1.0

    def test_context_defaults_to_empty_dict(self) -> None:
        """Context should default to empty dict."""
        signal = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test",
        )
        assert signal.context == {}

    def test_timestamp_is_set(self) -> None:
        """Timestamp should be automatically set."""
        signal = LearningSignal(
            source=LearningSignalSource.REVAN_FEEDBACK,
            learning_type=LearningType.BEHAVIORAL,
            pattern="test",
        )
        assert signal.timestamp > 0


# ---------------------------------------------------------------------------
# LearningUpdate tests
# ---------------------------------------------------------------------------


class TestLearningUpdate:
    """Tests for the LearningUpdate dataclass."""

    def test_default_values(self) -> None:
        """Default LearningUpdate should have zero signals."""
        update = LearningUpdate()
        assert update.signals_processed == 0
        assert update.patterns_extracted == []
        assert update.behavioral_adjustments == []
        assert update.insights == []

    def test_custom_values(self) -> None:
        """Custom values should be stored."""
        update = LearningUpdate(
            signals_processed=3,
            patterns_extracted=["p1", "p2"],
            behavioral_adjustments=["adj1"],
            insights=["Learned something."],
        )
        assert update.signals_processed == 3
        assert len(update.patterns_extracted) == 2
        assert len(update.behavioral_adjustments) == 1
        assert len(update.insights) == 1


# ---------------------------------------------------------------------------
# LearningEngine initialization tests
# ---------------------------------------------------------------------------


class TestLearningEngineInit:
    """Tests for LearningEngine initialization."""

    def test_engine_starts_empty(self, engine: LearningEngine) -> None:
        """New engine should have no learned patterns."""
        assert engine.get_learned_patterns() == {}
        assert engine.get_behavioral_defaults() == {}
        assert engine.get_learning_history() == []

    def test_get_learning_stats_empty(self, engine: LearningEngine) -> None:
        """Stats for empty engine should show zeros."""
        stats = engine.get_learning_stats()
        assert stats["total_patterns"] == 0
        assert stats["total_defaults"] == 0
        assert stats["total_updates"] == 0
        assert stats["avg_pattern_confidence"] == 0.0


# ---------------------------------------------------------------------------
# process_experience tests
# ---------------------------------------------------------------------------


class TestProcessExperience:
    """Tests for LearningEngine.process_experience()."""

    def test_process_safe_result(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Processing a safe result should produce a learning update."""
        update = engine.process_experience(safe_result, user_input="what is python")
        assert isinstance(update, LearningUpdate)
        assert update.signals_processed >= 0

    def test_process_blocked_result(
        self, engine: LearningEngine, blocked_result: PipelineResult
    ) -> None:
        """Processing a blocked result should detect the block."""
        update = engine.process_experience(
            blocked_result, user_input="modify the constitution"
        )
        assert isinstance(update, LearningUpdate)
        # Should have at least the blocked signal
        assert update.signals_processed >= 1

    def test_process_high_risk_result(
        self, engine: LearningEngine, high_risk_result: PipelineResult
    ) -> None:
        """Processing a high-risk result should detect the risk."""
        update = engine.process_experience(
            high_risk_result, user_input="make major system changes"
        )
        assert isinstance(update, LearningUpdate)
        assert update.signals_processed >= 1

    def test_process_with_feedback(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Processing with feedback should extract feedback signals."""
        update = engine.process_experience(
            safe_result,
            user_input="what is python",
            feedback="Great answer, that was helpful!",
        )
        assert update.signals_processed >= 1

    def test_process_with_corrective_feedback(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Corrective feedback should produce behavioral signals."""
        update = engine.process_experience(
            safe_result,
            user_input="what is python",
            feedback="That's wrong, Python was created by Guido van Rossum, not James Gosling.",
        )
        assert update.signals_processed >= 1

    def test_process_with_outcome(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Processing with outcome should extract outcome signals."""
        update = engine.process_experience(
            safe_result,
            user_input="run the build",
            outcome="The build succeeded and all tests passed.",
        )
        assert update.signals_processed >= 1

    def test_process_with_failed_outcome(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Failed outcome should produce cognitive signals."""
        update = engine.process_experience(
            safe_result,
            user_input="deploy to production",
            outcome="The deployment failed with a configuration error.",
        )
        assert update.signals_processed >= 1

    def test_process_with_unexpected_outcome(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Unexpected outcome should produce cognitive signals."""
        update = engine.process_experience(
            safe_result,
            user_input="run the analysis",
            outcome="The analysis produced unexpected results we didn't anticipate.",
        )
        assert update.signals_processed >= 1

    def test_process_adds_to_history(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Each process call should add to learning history."""
        engine.process_experience(safe_result, user_input="test 1")
        engine.process_experience(safe_result, user_input="test 2")
        assert len(engine.get_learning_history()) == 2

    def test_process_updates_learned_patterns(
        self, engine: LearningEngine, blocked_result: PipelineResult
    ) -> None:
        """Processing should update learned patterns."""
        engine.process_experience(blocked_result, user_input="modify constitution")
        patterns = engine.get_learned_patterns()
        assert len(patterns) > 0

    def test_process_updates_behavioral_defaults(
        self, engine: LearningEngine, blocked_result: PipelineResult
    ) -> None:
        """Processing should update behavioral defaults."""
        engine.process_experience(blocked_result, user_input="modify constitution")
        defaults = engine.get_behavioral_defaults()
        assert len(defaults) > 0

    def test_process_with_insights_in_result(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Result with insights should produce learning signals."""
        result_with_insights = PipelineResult(
            response="test",
            insights=["This interaction revealed a knowledge gap."],
        )
        update = engine.process_experience(result_with_insights, user_input="test")
        assert update.signals_processed >= 1

    def test_process_no_signals_for_empty(
        self, engine: LearningEngine
    ) -> None:
        """Empty result with no feedback/outcome should produce minimal update."""
        empty_result = PipelineResult(response="test")
        update = engine.process_experience(empty_result, user_input="test")
        assert update.signals_processed == 0


# ---------------------------------------------------------------------------
# Feedback signal extraction tests
# ---------------------------------------------------------------------------


class TestFeedbackSignals:
    """Tests for feedback signal extraction."""

    def test_positive_feedback_detected(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Positive feedback should be detected."""
        update = engine.process_experience(
            safe_result, user_input="test", feedback="That was great, thanks!"
        )
        assert any("positive" in p for p in update.patterns_extracted)

    def test_corrective_feedback_detected(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Corrective feedback should be detected."""
        update = engine.process_experience(
            safe_result, user_input="test", feedback="No, that's wrong."
        )
        assert any("corrective" in p for p in update.patterns_extracted)

    def test_tone_feedback_detected(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Tone feedback should be detected."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            feedback="Your tone is too formal, be more casual.",
        )
        assert any("tone" in p for p in update.patterns_extracted)


# ---------------------------------------------------------------------------
# Outcome signal extraction tests
# ---------------------------------------------------------------------------


class TestOutcomeSignals:
    """Tests for outcome signal extraction."""

    def test_success_outcome_detected(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Success outcome should be detected."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            outcome="The task was completed successfully.",
        )
        assert any("successful" in p for p in update.patterns_extracted)

    def test_failure_outcome_detected(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Failure outcome should be detected."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            outcome="The operation failed with an error.",
        )
        assert any("failed" in p for p in update.patterns_extracted)

    def test_unexpected_outcome_detected(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Unexpected outcome should be detected."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            outcome="Something unexpected happened.",
        )
        assert any("unexpected" in p for p in update.patterns_extracted)


# ---------------------------------------------------------------------------
# Pattern management tests
# ---------------------------------------------------------------------------


class TestPatternManagement:
    """Tests for pattern reinforcement and unlearning."""

    def test_reinforce_new_pattern(self, engine: LearningEngine) -> None:
        """Reinforcing a new pattern should create it."""
        confidence = engine.reinforce_pattern("new_pattern")
        assert confidence > 0.0
        assert "new_pattern" in engine.get_learned_patterns()

    def test_reinforce_existing_pattern(self, engine: LearningEngine) -> None:
        """Reinforcing an existing pattern should increase confidence."""
        engine.reinforce_pattern("test_pattern", amount=0.1)
        first = engine.get_learned_patterns()["test_pattern"]
        engine.reinforce_pattern("test_pattern", amount=0.1)
        second = engine.get_learned_patterns()["test_pattern"]
        assert second > first

    def test_reinforce_capped_at_one(self, engine: LearningEngine) -> None:
        """Confidence should not exceed 1.0."""
        engine.reinforce_pattern("test_pattern", amount=2.0)
        assert engine.get_learned_patterns()["test_pattern"] <= 1.0

    def test_reduce_confidence(self, engine: LearningEngine) -> None:
        """Reducing confidence should lower the score."""
        engine.reinforce_pattern("test_pattern", amount=0.5)
        before = engine.get_learned_patterns()["test_pattern"]
        engine.reduce_confidence("test_pattern", amount=0.2)
        after = engine.get_learned_patterns()["test_pattern"]
        assert after < before

    def test_reduce_confidence_to_zero_removes(self, engine: LearningEngine) -> None:
        """Reducing confidence to zero should remove the pattern."""
        engine.reinforce_pattern("test_pattern", amount=0.1)
        result = engine.reduce_confidence("test_pattern", amount=0.5)
        assert result == 0.0
        assert "test_pattern" not in engine.get_learned_patterns()

    def test_reduce_confidence_nonexistent(self, engine: LearningEngine) -> None:
        """Reducing confidence on nonexistent pattern returns 0.0."""
        result = engine.reduce_confidence("nonexistent")
        assert result == 0.0


# ---------------------------------------------------------------------------
# Learning hierarchy tests
# ---------------------------------------------------------------------------


class TestLearningHierarchy:
    """Tests for the learning signal priority hierarchy."""

    def test_feedback_higher_priority_than_outcome(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Revan feedback should take priority over outcomes."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            feedback="Great job!",
            outcome="The task succeeded.",
        )
        # Both signals should be present
        assert update.signals_processed >= 2

    def test_multiple_sources_processed(
        self, engine: LearningEngine, blocked_result: PipelineResult
    ) -> None:
        """Multiple signal sources should all be processed."""
        update = engine.process_experience(
            blocked_result,
            user_input="modify constitution",
            feedback="Don't do that.",
            outcome="The action was blocked.",
        )
        assert update.signals_processed >= 3


# ---------------------------------------------------------------------------
# Learning stats tests
# ---------------------------------------------------------------------------


class TestLearningStats:
    """Tests for learning statistics."""

    def test_stats_reflect_state(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Stats should reflect the current learning state."""
        engine.process_experience(safe_result, user_input="test 1")
        engine.process_experience(safe_result, user_input="test 2")
        stats = engine.get_learning_stats()
        assert stats["total_updates"] == 2

    def test_top_patterns_sorted(self, engine: LearningEngine) -> None:
        """Top patterns should be sorted by confidence descending."""
        engine.reinforce_pattern("high_conf", amount=0.8)
        engine.reinforce_pattern("low_conf", amount=0.2)
        engine.reinforce_pattern("mid_conf", amount=0.5)
        stats = engine.get_learning_stats()
        top = stats["top_patterns"]
        assert top[0][1] >= top[1][1] >= top[2][1]


# ---------------------------------------------------------------------------
# Persistence helpers tests
# ---------------------------------------------------------------------------


class TestPersistenceHelpers:
    """Tests for memory persistence helpers."""

    def test_to_memory_content(self, engine: LearningEngine) -> None:
        """to_memory_content should return valid JSON string."""
        content = engine.to_memory_content()
        assert isinstance(content, str)
        import json

        parsed = json.loads(content)
        assert "learned_patterns" in parsed
        assert "behavioral_defaults" in parsed

    def test_to_memory_index_keys(self, engine: LearningEngine) -> None:
        """to_memory_index_keys should return expected keys."""
        keys = engine.to_memory_index_keys()
        assert keys["type"] == "learning_state"
        assert "pattern_count" in keys
        assert "default_count" in keys


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_feedback(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Empty feedback should not crash."""
        update = engine.process_experience(safe_result, user_input="test", feedback="")
        assert isinstance(update, LearningUpdate)

    def test_empty_outcome(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Empty outcome should not crash."""
        update = engine.process_experience(safe_result, user_input="test", outcome="")
        assert isinstance(update, LearningUpdate)

    def test_very_long_feedback(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Very long feedback should be handled."""
        long_feedback = "great " * 1000
        update = engine.process_experience(
            safe_result, user_input="test", feedback=long_feedback
        )
        assert isinstance(update, LearningUpdate)

    def test_unicode_feedback(self, engine: LearningEngine, safe_result: PipelineResult) -> None:
        """Unicode feedback should be handled."""
        update = engine.process_experience(
            safe_result,
            user_input="test",
            feedback="素晴らしい！とても助かりました。",
        )
        assert isinstance(update, LearningUpdate)

    def test_multiple_processes_accumulate(
        self, engine: LearningEngine, safe_result: PipelineResult
    ) -> None:
        """Multiple processes should accumulate learning."""
        for i in range(10):
            engine.process_experience(safe_result, user_input=f"test {i}")
        assert len(engine.get_learning_history()) == 10

    def test_learning_update_is_frozen(self) -> None:
        """LearningUpdate should be frozen."""
        update = LearningUpdate(signals_processed=1)
        with pytest.raises(Exception):
            update.signals_processed = 2  # type: ignore[misc]

    def test_behavioral_adjustment_for_blocked(
        self, engine: LearningEngine, blocked_result: PipelineResult
    ) -> None:
        """Blocked actions should produce avoidance adjustments."""
        update = engine.process_experience(
            blocked_result, user_input="modify constitution"
        )
        assert any("block" in adj.lower() for adj in update.behavioral_adjustments)

    def test_behavioral_adjustment_for_high_risk(
        self, engine: LearningEngine, high_risk_result: PipelineResult
    ) -> None:
        """High-risk actions should produce caution adjustments."""
        update = engine.process_experience(
            high_risk_result, user_input="make major changes"
        )
        assert any("caution" in adj.lower() or "risk" in adj.lower()
                   for adj in update.behavioral_adjustments)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestLearningIntegration:
    """Integration tests for the learning engine."""

    def test_full_learning_cycle(self, engine: LearningEngine) -> None:
        """A full learning cycle should produce patterns, adjustments, and insights."""
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

        update = engine.process_experience(
            result,
            user_input="analyze the sales data",
            feedback="Good analysis, but include the regional breakdown next time.",
            outcome="The analysis was useful but missed regional patterns.",
        )

        assert update.signals_processed > 0
        assert len(update.patterns_extracted) > 0
        assert len(update.behavioral_adjustments) > 0
        assert len(engine.get_learning_history()) == 1

    def test_learning_persistence_roundtrip(self, engine: LearningEngine) -> None:
        """Learning state should be serializable and meaningful."""
        engine.reinforce_pattern("test_pattern", amount=0.7)
        engine.reinforce_pattern("another_pattern", amount=0.3)

        content = engine.to_memory_content()
        keys = engine.to_memory_index_keys()

        assert "test_pattern" in content
        assert keys["type"] == "learning_state"
        assert int(keys["pattern_count"]) == 2

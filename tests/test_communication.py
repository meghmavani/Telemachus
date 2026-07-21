"""Tests for the CommunicationEngine — mode selection, response formatting,
emotional detection, and communication protocols."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.core.types import (
    AutonomyDecision,
    AutonomyLevel,
    CommunicationMode,
    EthicalAssessment,
    EthicalVerdict,
    PipelineResult,
    RiskAssessment,
    RiskLevel,
)
from telemachus.interaction.communication import (
    CommunicationContext,
    CommunicationEngine,
    EmotionalState,
    ExplanationDepth,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> CommunicationEngine:
    """Create a fresh CommunicationEngine for each test."""
    return CommunicationEngine()


@pytest.fixture
def safe_result() -> PipelineResult:
    """A pipeline result for a safe, allowed action."""
    return PipelineResult(
        response="Here is the information you requested.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.MINIMAL,
            reversibility=RiskLevel.MINIMAL,
            resource=RiskLevel.MINIMAL,
            system_impact=RiskLevel.MINIMAL,
            uncertainty=RiskLevel.MINIMAL,
            emotional_impact=RiskLevel.MINIMAL,
            scale=RiskLevel.MINIMAL,
            reasoning="Low risk action.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.ALLOWED,
            reasoning="No constraints violated.",
        ),
        autonomy_decision=AutonomyDecision(
            level=AutonomyLevel.TRUSTED,
            allowed=True,
            requires_discussion=False,
            requires_approval=False,
            reasoning="Routine action in trusted domain.",
        ),
    )


@pytest.fixture
def blocked_result() -> PipelineResult:
    """A pipeline result for a blocked action."""
    return PipelineResult(
        response="",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.CRITICAL,
            reversibility=RiskLevel.CRITICAL,
            resource=RiskLevel.HIGH,
            system_impact=RiskLevel.CRITICAL,
            uncertainty=RiskLevel.MODERATE,
            emotional_impact=RiskLevel.MINIMAL,
            scale=RiskLevel.HIGH,
            reasoning="Irreversible system modification.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.BLOCKED,
            violated_constraints=["constitution"],
            reasoning="Cannot modify the constitution.",
        ),
        autonomy_decision=AutonomyDecision(
            level=AutonomyLevel.OBSERVATION,
            allowed=False,
            requires_discussion=True,
            requires_approval=True,
            reasoning="Sacred constraint violation.",
        ),
        metadata={"blocked": True, "blocked_reason": "Sacred constraint: constitution"},
    )


@pytest.fixture
def discussion_result() -> PipelineResult:
    """A pipeline result requiring discussion."""
    return PipelineResult(
        response="This requires discussion.",
        risk_assessment=RiskAssessment(
            overall_level=RiskLevel.MODERATE,
            reversibility=RiskLevel.LOW,
            resource=RiskLevel.MODERATE,
            system_impact=RiskLevel.LOW,
            uncertainty=RiskLevel.MODERATE,
            emotional_impact=RiskLevel.MINIMAL,
            scale=RiskLevel.LOW,
            reasoning="Moderate risk action.",
        ),
        ethical_assessment=EthicalAssessment(
            verdict=EthicalVerdict.REQUIRES_DISCUSSION,
            reasoning="Ethical uncertainty present.",
        ),
        autonomy_decision=AutonomyDecision(
            level=AutonomyLevel.SUGGESTION,
            allowed=False,
            requires_discussion=True,
            requires_approval=False,
            reasoning="Requires discussion before proceeding.",
        ),
    )


# ---------------------------------------------------------------------------
# CommunicationContext tests
# ---------------------------------------------------------------------------


class TestCommunicationContext:
    """Tests for the CommunicationContext dataclass."""

    def test_default_values(self) -> None:
        """CommunicationContext should have sensible defaults."""
        ctx = CommunicationContext()
        assert ctx.mode == CommunicationMode.COLLABORATIVE
        assert ctx.emotional_state == EmotionalState.NEUTRAL
        assert ctx.explanation_depth == ExplanationDepth.MODERATE
        assert ctx.is_error is False
        assert ctx.is_blocked is False
        assert ctx.audience == "user"

    def test_custom_values(self) -> None:
        """CommunicationContext should accept custom values."""
        ctx = CommunicationContext(
            mode=CommunicationMode.DIRECT,
            emotional_state=EmotionalState.CURIOUS,
            explanation_depth=ExplanationDepth.MINIMAL,
            is_error=True,
            is_blocked=True,
            audience="external",
        )
        assert ctx.mode == CommunicationMode.DIRECT
        assert ctx.emotional_state == EmotionalState.CURIOUS
        assert ctx.explanation_depth == ExplanationDepth.MINIMAL
        assert ctx.is_error is True
        assert ctx.is_blocked is True
        assert ctx.audience == "external"

    def test_context_is_frozen(self) -> None:
        """CommunicationContext should be frozen (immutable)."""
        ctx = CommunicationContext()
        with pytest.raises(FrozenInstanceError):
            ctx.mode = CommunicationMode.DIRECT  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Mode selection tests
# ---------------------------------------------------------------------------


class TestModeSelection:
    """Tests for CommunicationEngine.select_mode()."""

    def test_explicit_mode_overrides(self, engine: CommunicationEngine) -> None:
        """Explicit mode should always be used when provided."""
        mode = engine.select_mode(
            "what is 2+2",
            explicit_mode=CommunicationMode.EXPLAINED,
        )
        assert mode == CommunicationMode.EXPLAINED

    def test_high_risk_forces_collaborative(self, engine: CommunicationEngine) -> None:
        """HIGH or CRITICAL risk should force COLLABORATIVE mode."""
        mode = engine.select_mode(
            "delete all files",
            risk_level=RiskLevel.HIGH,
        )
        assert mode == CommunicationMode.COLLABORATIVE

    def test_critical_risk_forces_collaborative(self, engine: CommunicationEngine) -> None:
        """CRITICAL risk should force COLLABORATIVE mode."""
        mode = engine.select_mode(
            "modify system kernel",
            risk_level=RiskLevel.CRITICAL,
        )
        assert mode == CommunicationMode.COLLABORATIVE

    def test_distressed_emotional_state_forces_collaborative(
        self, engine: CommunicationEngine
    ) -> None:
        """Distressed emotional state should force COLLABORATIVE mode."""
        mode = engine.select_mode(
            "I'm feeling really sad today",
            emotional_state=EmotionalState.DISTRESSED,
        )
        assert mode == CommunicationMode.COLLABORATIVE

    def test_overwhelmed_emotional_state_forces_collaborative(
        self, engine: CommunicationEngine
    ) -> None:
        """Overwhelmed emotional state should force COLLABORATIVE mode."""
        mode = engine.select_mode(
            "I can't handle this anymore",
            emotional_state=EmotionalState.OVERWHELMED,
        )
        assert mode == CommunicationMode.COLLABORATIVE

    def test_requires_discussion_forces_collaborative(
        self, engine: CommunicationEngine
    ) -> None:
        """Requires discussion should force COLLABORATIVE mode."""
        mode = engine.select_mode(
            "should I change my career",
            requires_discussion=True,
        )
        assert mode == CommunicationMode.COLLABORATIVE

    def test_simple_question_uses_direct(self, engine: CommunicationEngine) -> None:
        """Simple factual questions should use DIRECT mode."""
        mode = engine.select_mode("what is the capital of France")
        assert mode == CommunicationMode.DIRECT

    def test_explanation_request_uses_explained(self, engine: CommunicationEngine) -> None:
        """Questions asking 'why' should use EXPLAINED mode."""
        mode = engine.select_mode("why does this system fail under load")
        assert mode == CommunicationMode.EXPLAINED

    def test_default_is_collaborative(self, engine: CommunicationEngine) -> None:
        """Default mode should be COLLABORATIVE."""
        mode = engine.select_mode("let's talk about something")
        assert mode == CommunicationMode.COLLABORATIVE

    def test_low_risk_does_not_force_collaborative(self, engine: CommunicationEngine) -> None:
        """Low risk should not force COLLABORATIVE."""
        mode = engine.select_mode(
            "what is the weather",
            risk_level=RiskLevel.LOW,
        )
        assert mode == CommunicationMode.DIRECT  # Simple question wins

    def test_moderate_risk_does_not_force_collaborative(
        self, engine: CommunicationEngine
    ) -> None:
        """Moderate risk should not force COLLABORATIVE."""
        mode = engine.select_mode(
            "why is the sky blue",
            risk_level=RiskLevel.MODERATE,
        )
        assert mode == CommunicationMode.EXPLAINED  # Explanation request wins


# ---------------------------------------------------------------------------
# Emotional state detection tests
# ---------------------------------------------------------------------------


class TestEmotionalDetection:
    """Tests for CommunicationEngine.detect_emotional_state()."""

    def test_detects_overwhelmed(self, engine: CommunicationEngine) -> None:
        """Should detect overwhelmed state from keywords."""
        assert (
            engine.detect_emotional_state("I'm so overwhelmed right now")
            == EmotionalState.OVERWHELMED
        )
        assert engine.detect_emotional_state("I'm freaking out") == EmotionalState.OVERWHELMED
        assert engine.detect_emotional_state("I can't handle this") == EmotionalState.OVERWHELMED

    def test_detects_distressed(self, engine: CommunicationEngine) -> None:
        """Should detect distressed state."""
        assert engine.detect_emotional_state("I'm feeling sad today") == EmotionalState.DISTRESSED
        assert engine.detect_emotional_state("I'm so lonely") == EmotionalState.DISTRESSED
        assert engine.detect_emotional_state("I feel heartbroken") == EmotionalState.DISTRESSED

    def test_detects_frustrated(self, engine: CommunicationEngine) -> None:
        """Should detect frustrated state."""
        assert engine.detect_emotional_state("this is so frustrating") == EmotionalState.FRUSTRATED
        assert engine.detect_emotional_state("this doesn't work") == EmotionalState.FRUSTRATED
        assert engine.detect_emotional_state("this is useless") == EmotionalState.FRUSTRATED

    def test_detects_curious(self, engine: CommunicationEngine) -> None:
        """Should detect curious state."""
        assert engine.detect_emotional_state("I'm curious about that") == EmotionalState.CURIOUS
        assert engine.detect_emotional_state("that's interesting") == EmotionalState.CURIOUS
        assert engine.detect_emotional_state("tell me more") == EmotionalState.CURIOUS

    def test_detects_uncertain(self, engine: CommunicationEngine) -> None:
        """Should detect uncertain state."""
        assert engine.detect_emotional_state("I'm not sure about this") == EmotionalState.UNCERTAIN
        assert engine.detect_emotional_state("I'm confused") == EmotionalState.UNCERTAIN
        assert engine.detect_emotional_state("I don't know") == EmotionalState.UNCERTAIN

    def test_detects_grateful(self, engine: CommunicationEngine) -> None:
        """Should detect grateful state."""
        assert engine.detect_emotional_state("thank you so much") == EmotionalState.GRATEFUL
        assert engine.detect_emotional_state("I really appreciate this") == EmotionalState.GRATEFUL
        assert engine.detect_emotional_state("that's awesome") == EmotionalState.GRATEFUL

    def test_default_is_neutral(self, engine: CommunicationEngine) -> None:
        """Default emotional state should be NEUTRAL."""
        assert engine.detect_emotional_state("what is the weather today") == EmotionalState.NEUTRAL
        assert engine.detect_emotional_state("tell me about Python") == EmotionalState.NEUTRAL

    def test_overwhelmed_takes_priority_over_distressed(self, engine: CommunicationEngine) -> None:
        """Overwhelmed keywords should be checked before distressed."""
        # "overwhelmed" is checked first, so it should win
        result = engine.detect_emotional_state("I'm overwhelmed and sad")
        assert result == EmotionalState.OVERWHELMED


# ---------------------------------------------------------------------------
# Explanation depth tests
# ---------------------------------------------------------------------------


class TestExplanationDepth:
    """Tests for CommunicationEngine.select_explanation_depth()."""

    def test_simple_question_minimal(self, engine: CommunicationEngine) -> None:
        """Simple questions should get minimal explanation."""
        depth = engine.select_explanation_depth("what is 2+2")
        assert depth == ExplanationDepth.MINIMAL

    def test_explanation_request_moderate(self, engine: CommunicationEngine) -> None:
        """Explanation requests should get moderate depth."""
        depth = engine.select_explanation_depth("why does this fail")
        assert depth == ExplanationDepth.MODERATE

    def test_high_risk_deep(self, engine: CommunicationEngine) -> None:
        """High risk should get deep explanation."""
        depth = engine.select_explanation_depth(
            "delete files",
            risk_level=RiskLevel.HIGH,
        )
        assert depth == ExplanationDepth.DEEP

    def test_critical_risk_deep(self, engine: CommunicationEngine) -> None:
        """Critical risk should get deep explanation."""
        depth = engine.select_explanation_depth(
            "modify kernel",
            risk_level=RiskLevel.CRITICAL,
        )
        assert depth == ExplanationDepth.DEEP

    def test_distressed_emotional_deep(self, engine: CommunicationEngine) -> None:
        """Distressed state should get deep explanation."""
        depth = engine.select_explanation_depth(
            "I'm sad",
            emotional_state=EmotionalState.DISTRESSED,
        )
        assert depth == ExplanationDepth.DEEP

    def test_overwhelmed_emotional_deep(self, engine: CommunicationEngine) -> None:
        """Overwhelmed state should get deep explanation."""
        depth = engine.select_explanation_depth(
            "too much",
            emotional_state=EmotionalState.OVERWHELMED,
        )
        assert depth == ExplanationDepth.DEEP

    def test_requires_discussion_deep(self, engine: CommunicationEngine) -> None:
        """Requires discussion should get deep explanation."""
        depth = engine.select_explanation_depth(
            "career change",
            requires_discussion=True,
        )
        assert depth == ExplanationDepth.DEEP

    def test_default_moderate(self, engine: CommunicationEngine) -> None:
        """Default depth should be moderate."""
        depth = engine.select_explanation_depth("tell me something")
        assert depth == ExplanationDepth.MODERATE


# ---------------------------------------------------------------------------
# Response formatting tests
# ---------------------------------------------------------------------------


class TestResponseFormatting:
    """Tests for CommunicationEngine.format_response()."""

    def test_formats_safe_response(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Safe response should include the pipeline response text."""
        formatted = engine.format_response(safe_result, user_input="tell me about Python")
        assert "information you requested" in formatted

    def test_formats_blocked_response(
        self, engine: CommunicationEngine, blocked_result: PipelineResult
    ) -> None:
        """Blocked response should explain why and offer alternatives."""
        formatted = engine.format_response(blocked_result, user_input="modify constitution")
        assert "can't proceed" in formatted.lower()
        assert "alternative" in formatted.lower()

    def test_formats_error_response(self, engine: CommunicationEngine) -> None:
        """Error response should follow mistake protocol."""
        error_result = PipelineResult(
            response="",
            metadata={"error": "Database connection failed"},
        )
        formatted = engine.format_response(error_result, user_input="do something")
        assert "error" in formatted.lower()
        assert "Database connection failed" in formatted

    def test_emotional_prefix_included(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Distressed input should include emotional acknowledgment."""
        formatted = engine.format_response(
            safe_result,
            user_input="I'm feeling really sad today",
        )
        assert "difficult" in formatted.lower() or "hear" in formatted.lower()

    def test_governance_note_in_explained_mode(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Explained mode should include governance transparency."""
        formatted = engine.format_response(
            safe_result,
            user_input="why does this work",
            mode=CommunicationMode.EXPLAINED,
        )
        assert "Autonomy level" in formatted

    def test_governance_note_in_collaborative_mode(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Collaborative mode should include governance transparency."""
        formatted = engine.format_response(
            safe_result,
            user_input="let's discuss this",
            mode=CommunicationMode.COLLABORATIVE,
        )
        assert "Autonomy level" in formatted

    def test_no_governance_note_in_direct_mode(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Direct mode should NOT include governance transparency."""
        formatted = engine.format_response(
            safe_result,
            user_input="what is 2+2",
            mode=CommunicationMode.DIRECT,
        )
        assert "Autonomy level" not in formatted

    def test_discussion_transparency_included(
        self, engine: CommunicationEngine
    ) -> None:
        """When discussion is required, include transparency note."""
        result = PipelineResult(
            response="Here's what I think.",
            autonomy_decision=AutonomyDecision(
                level=AutonomyLevel.SUGGESTION,
                allowed=False,
                requires_discussion=True,
                requires_approval=False,
                reasoning="Needs discussion.",
            ),
        )
        formatted = engine.format_response(result, user_input="should I do this")
        assert "transparent" in formatted.lower() or "discuss" in formatted.lower()


# ---------------------------------------------------------------------------
# Disagreement protocol tests
# ---------------------------------------------------------------------------


class TestDisagreementProtocol:
    """Tests for CommunicationEngine.format_disagreement()."""

    def test_disagreement_is_collaborative(self, engine: CommunicationEngine) -> None:
        """Disagreement should use collaborative framing."""
        result = engine.format_disagreement(
            user_statement="Python is slow",
            reasoning="Python's performance depends on the use case and implementation.",
        )
        assert "misunderstanding" in result.lower() or "perspective" in result.lower()
        assert "reasoning" in result.lower()

    def test_disagreement_includes_evidence(self, engine: CommunicationEngine) -> None:
        """Disagreement should include evidence when provided."""
        result = engine.format_disagreement(
            user_statement="X is better",
            reasoning="Y has more features.",
            evidence="Benchmark results show Y is 2x faster.",
        )
        assert "Evidence" in result

    def test_disagreement_includes_alternatives(self, engine: CommunicationEngine) -> None:
        """Disagreement should include alternatives when provided."""
        result = engine.format_disagreement(
            user_statement="only one way",
            reasoning="There are multiple approaches.",
            alternatives=["Option A", "Option B"],
        )
        assert "Option A" in result
        assert "Option B" in result

    def test_disagreement_encourages_discussion(self, engine: CommunicationEngine) -> None:
        """Disagreement should invite further discussion."""
        result = engine.format_disagreement(
            user_statement="I'm right",
            reasoning="Let me explain.",
        )
        assert "open to being wrong" in result.lower() or "what do you think" in result.lower()


# ---------------------------------------------------------------------------
# Uncertainty communication tests
# ---------------------------------------------------------------------------


class TestUncertaintyCommunication:
    """Tests for CommunicationEngine.format_uncertainty()."""

    def test_uncertainty_states_uncertainty(self, engine: CommunicationEngine) -> None:
        """Should explicitly state uncertainty."""
        result = engine.format_uncertainty("quantum physics")
        assert "don't know" in result.lower() or "not certain" in result.lower()

    def test_uncertainty_includes_best_guess(self, engine: CommunicationEngine) -> None:
        """Should include best guess when provided."""
        result = engine.format_uncertainty(
            "the answer",
            best_guess="It might be 42.",
            confidence="low",
        )
        assert "42" in result
        assert "confidence" in result.lower()

    def test_uncertainty_includes_verification(self, engine: CommunicationEngine) -> None:
        """Should include verification suggestions."""
        result = engine.format_uncertainty(
            "the answer",
            verification_suggestions=["Check the documentation", "Run an experiment"],
        )
        assert "Check the documentation" in result
        assert "Run an experiment" in result


# ---------------------------------------------------------------------------
# Correction style tests
# ---------------------------------------------------------------------------


class TestCorrectionStyle:
    """Tests for CommunicationEngine.format_correction()."""

    def test_correction_is_collaborative(self, engine: CommunicationEngine) -> None:
        """Correction should use collaborative framing."""
        result = engine.format_correction(
            incorrect_statement="The sky is green",
            correction="The sky appears blue due to Rayleigh scattering.",
        )
        assert "different way" in result.lower() or "might be" in result.lower()

    def test_correction_includes_reasoning(self, engine: CommunicationEngine) -> None:
        """Correction should include reasoning when provided."""
        result = engine.format_correction(
            incorrect_statement="X",
            correction="Y",
            reasoning="Scientific consensus supports Y.",
        )
        assert "reasoning" in result.lower()

    def test_correction_invites_discussion(self, engine: CommunicationEngine) -> None:
        """Correction should invite discussion."""
        result = engine.format_correction(
            incorrect_statement="X",
            correction="Y",
        )
        assert "understanding" in result.lower() or "align" in result.lower()


# ---------------------------------------------------------------------------
# Mistake communication tests
# ---------------------------------------------------------------------------


class TestMistakeCommunication:
    """Tests for CommunicationEngine.format_mistake()."""

    def test_mistake_follows_five_step_protocol(self, engine: CommunicationEngine) -> None:
        """Should follow the 5-step mistake protocol."""
        result = engine.format_mistake(
            mistake_description="I deleted the wrong file.",
            cause="I misidentified the target.",
            lesson="Always verify the file path before deletion.",
            prevention="I will add a confirmation step before destructive operations.",
        )
        assert "mistake" in result.lower()
        assert "learned" in result.lower()
        assert "prevent" in result.lower()

    def test_mistake_is_honest(self, engine: CommunicationEngine) -> None:
        """Mistake communication should be honest and transparent."""
        result = engine.format_mistake(
            mistake_description="I gave incorrect information.",
            cause="My knowledge was outdated.",
            lesson="I need to verify information before sharing.",
            prevention="I will cross-reference sources.",
        )
        assert "incorrect" in result.lower()


# ---------------------------------------------------------------------------
# Build context tests
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Tests for CommunicationEngine.build_context()."""

    def test_builds_context_from_input(self, engine: CommunicationEngine) -> None:
        """Should build a context from user input alone."""
        ctx = engine.build_context("what is Python")
        assert isinstance(ctx, CommunicationContext)
        assert ctx.mode == CommunicationMode.DIRECT
        assert ctx.emotional_state == EmotionalState.NEUTRAL

    def test_build_context_with_pipeline_result(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Should incorporate pipeline result into context."""
        ctx = engine.build_context("tell me about Python", pipeline_result=safe_result)
        assert ctx.is_blocked is False
        assert ctx.is_error is False

    def test_build_context_with_blocked_result(
        self, engine: CommunicationEngine, blocked_result: PipelineResult
    ) -> None:
        """Should detect blocked state from pipeline result."""
        ctx = engine.build_context("modify constitution", pipeline_result=blocked_result)
        assert ctx.is_blocked is True

    def test_build_context_with_explicit_mode(self, engine: CommunicationEngine) -> None:
        """Should use explicit mode when provided."""
        ctx = engine.build_context(
            "what is Python",
            explicit_mode=CommunicationMode.EXPLAINED,
        )
        assert ctx.mode == CommunicationMode.EXPLAINED

    def test_build_context_detects_emotional_state(
        self, engine: CommunicationEngine
    ) -> None:
        """Should detect emotional state from input."""
        ctx = engine.build_context("I'm feeling really sad today")
        assert ctx.emotional_state == EmotionalState.DISTRESSED


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_input_emotional(self, engine: CommunicationEngine) -> None:
        """Empty input should be neutral."""
        assert engine.detect_emotional_state("") == EmotionalState.NEUTRAL

    def test_very_long_input(self, engine: CommunicationEngine) -> None:
        """Very long input should not crash."""
        long_input = "I am " + "very " * 100 + "happy"
        state = engine.detect_emotional_state(long_input)
        assert isinstance(state, EmotionalState)

    def test_special_characters(self, engine: CommunicationEngine) -> None:
        """Special characters should not crash detection."""
        state = engine.detect_emotional_state("!@#$%^&*()")
        assert state == EmotionalState.NEUTRAL

    def test_unicode_input(self, engine: CommunicationEngine) -> None:
        """Unicode input should work."""
        state = engine.detect_emotional_state("私は悲しいです")
        assert isinstance(state, EmotionalState)

    def test_none_risk_level(self, engine: CommunicationEngine) -> None:
        """None risk level should not crash mode selection."""
        mode = engine.select_mode("hello", risk_level=None)
        assert isinstance(mode, CommunicationMode)

    def test_format_response_with_none_assessments(self, engine: CommunicationEngine) -> None:
        """Response with None assessments should not crash."""
        result = PipelineResult(response="Hello")
        formatted = engine.format_response(result, user_input="hi")
        assert "Hello" in formatted

    def test_all_emotional_states_have_prefixes(self, engine: CommunicationEngine) -> None:
        """All emotional states should be handled (even if prefix is None)."""
        for state in EmotionalState:
            prefix = engine._get_emotional_prefix(state)
            # Some states return None, which is fine
            assert prefix is None or isinstance(prefix, str)

    def test_build_governance_note_no_assessments(self, engine: CommunicationEngine) -> None:
        """Governance note with no assessments should return None."""
        result = PipelineResult(response="test")
        note = engine._build_governance_note(result)
        assert note is None

    def test_build_governance_note_high_risk(self, engine: CommunicationEngine) -> None:
        """High risk should be noted."""
        result = PipelineResult(
            response="test",
            risk_assessment=RiskAssessment(
                overall_level=RiskLevel.HIGH,
                reversibility=RiskLevel.MINIMAL,
                resource=RiskLevel.MINIMAL,
                system_impact=RiskLevel.MINIMAL,
                uncertainty=RiskLevel.MINIMAL,
                emotional_impact=RiskLevel.MINIMAL,
                scale=RiskLevel.MINIMAL,
            ),
        )
        note = engine._build_governance_note(result)
        assert note is not None
        assert "HIGH" in note

    def test_build_governance_note_blocked_ethics(self, engine: CommunicationEngine) -> None:
        """Blocked ethics should show in governance note."""
        result = PipelineResult(
            response="test",
            ethical_assessment=EthicalAssessment(
                verdict=EthicalVerdict.BLOCKED,
                violated_constraints=["constitution"],
                reasoning="Cannot modify.",
            ),
        )
        note = engine._build_governance_note(result)
        assert note is not None
        assert "blocked" in note.lower()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCommunicationIntegration:
    """Integration tests for the communication engine."""

    def test_full_flow_safe_action(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Full flow: detect emotion → select mode → format response."""
        user_input = "what is machine learning"

        # Detect emotional state
        state = engine.detect_emotional_state(user_input)
        assert state == EmotionalState.NEUTRAL

        # Select mode — "what is" triggers simple question → DIRECT
        mode = engine.select_mode(user_input)
        assert mode == CommunicationMode.DIRECT

        # Format response
        formatted = engine.format_response(safe_result, user_input=user_input, mode=mode)
        assert len(formatted) > 0

    def test_full_flow_blocked_action(
        self, engine: CommunicationEngine, blocked_result: PipelineResult
    ) -> None:
        """Full flow for a blocked action."""
        user_input = "modify the constitution"

        # Detect emotion
        state = engine.detect_emotional_state(user_input)
        assert isinstance(state, EmotionalState)

        # Build context
        ctx = engine.build_context(user_input, pipeline_result=blocked_result)
        assert ctx.is_blocked is True

        # Format response
        formatted = engine.format_response(blocked_result, user_input=user_input)
        assert "can't proceed" in formatted.lower()

    def test_full_flow_emotional_input(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Full flow for an emotional input."""
        user_input = "I'm feeling really overwhelmed and stressed"

        # Detect emotion
        state = engine.detect_emotional_state(user_input)
        assert state == EmotionalState.OVERWHELMED

        # Select mode — should be collaborative
        mode = engine.select_mode(user_input, emotional_state=state)
        assert mode == CommunicationMode.COLLABORATIVE

        # Format response
        formatted = engine.format_response(safe_result, user_input=user_input)
        assert len(formatted) > 0

    def test_mode_override_works_in_full_flow(
        self, engine: CommunicationEngine, safe_result: PipelineResult
    ) -> None:
        """Explicit mode override should work in full flow."""
        user_input = "what is the capital of France"

        # Even though this is a simple question, explicit mode should win
        formatted = engine.format_response(
            safe_result,
            user_input=user_input,
            mode=CommunicationMode.EXPLAINED,
        )
        assert "Autonomy level" in formatted  # Governance note in explained mode

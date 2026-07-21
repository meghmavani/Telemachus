"""Communication Engine — mode-aware response generation.

Implements the Communication Charter: adaptive communication modes (Direct,
Explained, Collaborative), disagreement protocol, intellectual humility,
emotional communication protocol, and audience awareness.

The engine selects the appropriate communication mode based on context and
formats responses accordingly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from telemachus.core.types import (
    CommunicationMode,
    EthicalVerdict,
    PipelineResult,
    RiskLevel,
)

logger = logging.getLogger("telemachus.communication")


# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------


class EmotionalState(Enum):
    """Recognized emotional states for adaptive communication."""

    NEUTRAL = "neutral"
    DISTRESSED = "distressed"
    OVERWHELMED = "overwhelmed"
    CURIOUS = "curious"
    FRUSTRATED = "frustrated"
    GRATEFUL = "grateful"
    UNCERTAIN = "uncertain"


class ExplanationDepth(Enum):
    """How much detail to include in responses."""

    MINIMAL = "minimal"
    MODERATE = "moderate"
    DEEP = "deep"


@dataclass(frozen=True)
class CommunicationContext:
    """Context for determining communication style.

    Attributes:
        mode: The selected communication mode.
        emotional_state: Detected emotional state of the user.
        explanation_depth: How much detail to include.
        is_error: Whether this is an error response.
        is_blocked: Whether the action was blocked by governance.
        audience: Intended audience (e.g., "revan", "external").
    """

    mode: CommunicationMode = CommunicationMode.COLLABORATIVE
    emotional_state: EmotionalState = EmotionalState.NEUTRAL
    explanation_depth: ExplanationDepth = ExplanationDepth.MODERATE
    is_error: bool = False
    is_blocked: bool = False
    audience: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Communication Engine
# ---------------------------------------------------------------------------


class CommunicationEngine:
    """Mode-aware communication engine implementing the Communication Charter.

    Selects communication mode based on context, formats responses with
    appropriate tone and depth, and handles emotional awareness, disagreement,
    mistakes, and uncertainty.

    The engine is stateless — all context is passed in per-call.
    """

    # ------------------------------------------------------------------
    # Mode selection
    # ------------------------------------------------------------------

    @staticmethod
    def select_mode(
        user_input: str,
        *,
        risk_level: RiskLevel | None = None,
        emotional_state: EmotionalState = EmotionalState.NEUTRAL,
        requires_discussion: bool = False,
        explicit_mode: CommunicationMode | None = None,
    ) -> CommunicationMode:
        """Select the appropriate communication mode based on context.

        Selection logic:
        - If an explicit mode is requested, use it.
        - If risk is HIGH or CRITICAL, use COLLABORATIVE.
        - If the user is distressed/overwhelmed, use COLLABORATIVE.
        - If discussion is required, use COLLABORATIVE.
        - If the input is a simple factual question, use DIRECT.
        - If the input asks for reasoning/explanation, use EXPLAINED.
        - Default: COLLABORATIVE.

        Args:
            user_input: The user's input text.
            risk_level: Current risk assessment level.
            emotional_state: Detected emotional state.
            requires_discussion: Whether the action requires discussion.
            complexity: Explicitly requested mode override.

        Returns:
            The selected CommunicationMode.

        """
        if explicit_mode is not None:
            return explicit_mode

        # High-risk or emotional situations → collaborative
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return CommunicationMode.COLLABORATIVE

        if emotional_state in (EmotionalState.DISTRESSED, EmotionalState.OVERWHELMED):
            return CommunicationMode.COLLABORATIVE

        if requires_discussion:
            return CommunicationMode.COLLABORATIVE

        # Detect simple factual questions → direct
        if CommunicationEngine._is_simple_question(user_input):
            return CommunicationMode.DIRECT

        # Detect requests for reasoning → explained
        if CommunicationEngine._is_explanation_request(user_input):
            return CommunicationMode.EXPLAINED

        return CommunicationMode.COLLABORATIVE

    @staticmethod
    def _is_simple_question(text: str) -> bool:
        """Check if the input is a simple factual question."""
        simple_patterns = [
            "what is",
            "what are",
            "define",
            "who is",
            "when did",
            "how many",
            "what time",
            "what date",
        ]
        text_lower = text.lower().strip()
        # Short questions with simple patterns
        if len(text_lower.split()) <= 8:
            for pattern in simple_patterns:
                if text_lower.startswith(pattern):
                    return True
        return False

    @staticmethod
    def _is_explanation_request(text: str) -> bool:
        """Check if the input requests reasoning or explanation."""
        explanation_patterns = [
            "why",
            "how does",
            "how do",
            "explain",
            "what is the reason",
            "what causes",
            "how come",
            "elaborate",
            "describe",
        ]
        text_lower = text.lower().strip()
        return any(text_lower.startswith(pattern) for pattern in explanation_patterns)

    # ------------------------------------------------------------------
    # Emotional state detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_emotional_state(user_input: str) -> EmotionalState:
        """Detect the user's emotional state from their input text.

        Uses keyword-based heuristics. This is a lightweight approach;
        a full emotional model would use more sophisticated NLP.

        Args:
            user_input: The user's input text.

        Returns:
            The detected EmotionalState.
        """
        text_lower = user_input.lower()

        # Distress/overwhelm signals
        distress_keywords = [
            "overwhelmed",
            "can't handle",
            "too much",
            "stressed",
            "anxious",
            "panicking",
            "freaking out",
            "losing it",
            "breaking down",
            "falling apart",
        ]
        for kw in distress_keywords:
            if kw in text_lower:
                return EmotionalState.OVERWHELMED

        # Sadness/distress signals
        sad_keywords = [
            "sad",
            "upset",
            "depressed",
            "hopeless",
            "crying",
            "heartbroken",
            "devastated",
            "miserable",
            "lonely",
            "hurt",
        ]
        for kw in sad_keywords:
            if kw in text_lower:
                return EmotionalState.DISTRESSED

        # Frustration signals
        frustration_keywords = [
            "frustrated",
            "frustrating",
            "annoying",
            "stupid",
            "ridiculous",
            "doesn't work",
            "broken",
            "useless",
            "waste of time",
        ]
        for kw in frustration_keywords:
            if kw in text_lower:
                return EmotionalState.FRUSTRATED

        # Curiosity signals
        curiosity_keywords = [
            "curious",
            "wonder",
            "interesting",
            "tell me more",
            "what do you think",
            "how would you",
        ]
        for kw in curiosity_keywords:
            if kw in text_lower:
                return EmotionalState.CURIOUS

        # Uncertainty signals
        uncertainty_keywords = [
            "not sure",
            "uncertain",
            "confused",
            "don't know",
            "maybe",
            "perhaps",
            "might be",
            "could be",
        ]
        for kw in uncertainty_keywords:
            if kw in text_lower:
                return EmotionalState.UNCERTAIN

        # Gratitude signals
        gratitude_keywords = [
            "thank",
            "thanks",
            "grateful",
            "appreciate",
            "helped",
            "awesome",
            "great",
        ]
        for kw in gratitude_keywords:
            if kw in text_lower:
                return EmotionalState.GRATEFUL

        return EmotionalState.NEUTRAL

    # ------------------------------------------------------------------
    # Explanation depth selection
    # ------------------------------------------------------------------

    @staticmethod
    def select_explanation_depth(
        user_input: str,
        *,
        risk_level: RiskLevel | None = None,
        emotional_state: EmotionalState = EmotionalState.NEUTRAL,
        requires_discussion: bool = False,
    ) -> ExplanationDepth:
        """Select the appropriate explanation depth.

        Args:
            user_input: The user's input text.
            risk_level: Current risk level.
            emotional_state: Detected emotional state.
            requires_discussion: Whether discussion is required.

        Returns:
            The selected ExplanationDepth.
        """
        # Complex or emotional decisions → deep explanation
        if emotional_state in (EmotionalState.DISTRESSED, EmotionalState.OVERWHELMED):
            return ExplanationDepth.DEEP

        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return ExplanationDepth.DEEP

        if requires_discussion:
            return ExplanationDepth.DEEP

        # Simple questions → minimal
        if CommunicationEngine._is_simple_question(user_input):
            return ExplanationDepth.MINIMAL

        # Explanation requests → moderate
        if CommunicationEngine._is_explanation_request(user_input):
            return ExplanationDepth.MODERATE

        return ExplanationDepth.MODERATE

    # ------------------------------------------------------------------
    # Response formatting
    # ------------------------------------------------------------------

    def format_response(
        self,
        pipeline_result: PipelineResult,
        *,
        user_input: str = "",
        mode: CommunicationMode | None = None,
        emotional_state: EmotionalState | None = None,
    ) -> str:
        """Format a pipeline result into a user-facing response.

        Applies the communication mode, emotional awareness, and
        explanation depth to produce a natural, adaptive response.

        Args:
            pipeline_result: The result from the cognitive pipeline.
            user_input: The original user input (for context).
            mode: Override communication mode (auto-detected if None).
            emotional_state: Override emotional state (auto-detected if None).

        Returns:
            A formatted response string.
        """
        # Auto-detect if not provided
        if emotional_state is None:
            emotional_state = self.detect_emotional_state(user_input)

        if mode is None:
            mode = self.select_mode(
                user_input,
                risk_level=(
                    pipeline_result.risk_assessment.overall_level
                    if pipeline_result.risk_assessment
                    else None
                ),
                emotional_state=emotional_state,
                requires_discussion=(
                    pipeline_result.autonomy_decision.requires_discussion
                    if pipeline_result.autonomy_decision
                    else False
                ),
            )

        # Build the response based on mode
        if pipeline_result.metadata.get("blocked", False):
            return self._format_blocked_response(pipeline_result, mode, emotional_state)

        if pipeline_result.metadata.get("error"):
            return self._format_error_response(pipeline_result, mode, emotional_state)

        return self._format_standard_response(pipeline_result, mode, emotional_state)

    def _format_standard_response(
        self,
        result: PipelineResult,
        mode: CommunicationMode,
        emotional_state: EmotionalState,
    ) -> str:
        """Format a standard (non-blocked, non-error) response."""
        parts: list[str] = []

        # Emotional acknowledgment
        emotional_prefix = self._get_emotional_prefix(emotional_state)
        if emotional_prefix:
            parts.append(emotional_prefix)

        # Main response body
        parts.append(result.response)

        # Governance transparency (only in EXPLAINED and COLLABORATIVE modes)
        if mode in (CommunicationMode.EXPLAINED, CommunicationMode.COLLABORATIVE):
            governance_note = self._build_governance_note(result)
            if governance_note:
                parts.append(governance_note)

        # Intellectual humility note for uncertain situations
        if result.autonomy_decision and result.autonomy_decision.requires_discussion:
            parts.append(
                "\nI want to be transparent: this is something I think we should "
                "discuss together. I may be missing context or perspective that "
                "you have."
            )

        return "\n\n".join(parts)

    def _format_blocked_response(
        self,
        result: PipelineResult,
        mode: CommunicationMode,
        emotional_state: EmotionalState,
    ) -> str:
        """Format a response for blocked actions."""
        blocked_reason = result.metadata.get("blocked_reason", "governance constraints")

        parts: list[str] = []

        # Acknowledge the request
        parts.append(
            "I understand what you're asking, but I can't proceed with that action."
        )

        # Explain why (always, regardless of mode — transparency is non-negotiable)
        parts.append(f"Reason: {blocked_reason}")

        # Offer alternatives
        parts.append(
            "I'd be happy to help you find an alternative approach that stays within "
            "my governance boundaries. Would you like to explore other options?"
        )

        return "\n\n".join(parts)

    def _format_error_response(
        self,
        result: PipelineResult,
        mode: CommunicationMode,
        emotional_state: EmotionalState,
    ) -> str:
        """Format an error response following the mistake communication protocol."""
        error_msg = result.metadata.get("error", "An unexpected error occurred")

        parts: list[str] = []

        # Step 1: Acknowledge
        parts.append("I encountered an error while processing your request.")

        # Step 2: Explain
        parts.append(f"What happened: {error_msg}")

        # Step 3: State what was learned (if available)
        if "error_analysis" in result.metadata:
            parts.append(f"Analysis: {result.metadata['error_analysis']}")

        # Step 4: Prevention
        parts.append(
            "This error has been logged and will inform future improvements. "
            "Please try again, or let me know if you'd like to take a different approach."
        )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _get_emotional_prefix(state: EmotionalState) -> str | None:
        """Get an emotional acknowledgment prefix."""
        prefixes = {
            EmotionalState.DISTRESSED: (
                "I can hear that this is difficult. Let me respond thoughtfully."
            ),
            EmotionalState.OVERWHELMED: (
                "It sounds like you're dealing with a lot right now. "
                "Let me help break this down."
            ),
            EmotionalState.FRUSTRATED: (
                "I understand the frustration. Let me see if I can help."
            ),
            EmotionalState.GRATEFUL: (
                "I'm glad I could help."
            ),
            EmotionalState.UNCERTAIN: (
                "I sense some uncertainty here. Let me provide what clarity I can."
            ),
        }
        return prefixes.get(state)

    @staticmethod
    def _build_governance_note(result: PipelineResult) -> str | None:
        """Build a governance transparency note."""
        notes: list[str] = []

        if result.risk_assessment:
            risk = result.risk_assessment
            if risk.overall_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                notes.append(f"Risk level: {risk.overall_level.name}")

        if result.ethical_assessment:
            ethics = result.ethical_assessment
            if ethics.verdict != EthicalVerdict.ALLOWED:
                notes.append(f"Ethics: {ethics.verdict.value} — {ethics.reasoning}")

        if result.autonomy_decision:
            auto = result.autonomy_decision
            notes.append(f"Autonomy level: {auto.level.name}")

        if not notes:
            return None

        return "\n".join(f"  • {n}" for n in notes)

    # ------------------------------------------------------------------
    # Disagreement protocol
    # ------------------------------------------------------------------

    @staticmethod
    def format_disagreement(
        user_statement: str,
        reasoning: str,
        *,
        evidence: str | None = None,
        alternatives: list[str] | None = None,
    ) -> str:
        """Format a respectful disagreement following the charter.

        Args:
            user_statement: What the user said that is being disagreed with.
            reasoning: The reasoning behind the disagreement.
            evidence: Supporting evidence (optional).
            alternatives: Alternative perspectives or approaches (optional).

        Returns:
            A formatted disagreement response.
        """
        parts: list[str] = []

        # State disagreement clearly but collaboratively
        parts.append(
            "I might be misunderstanding you, but I think there's another "
            "perspective here."
        )

        # Explain reasoning
        parts.append(f"My reasoning: {reasoning}")

        # Present evidence if available
        if evidence:
            parts.append(f"Evidence: {evidence}")

        # Offer alternatives
        if alternatives:
            alt_text = "\n".join(f"  • {a}" for a in alternatives)
            parts.append(f"Alternatives to consider:\n{alt_text}")

        # Encourage discussion
        parts.append(
            "I'm open to being wrong here — what do you think?"
        )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Uncertainty communication
    # ------------------------------------------------------------------

    @staticmethod
    def format_uncertainty(
        topic: str,
        *,
        best_guess: str | None = None,
        confidence: str = "medium",
        verification_suggestions: list[str] | None = None,
    ) -> str:
        """Format an uncertainty response.

        Args:
            topic: The topic of uncertainty.
            best_guess: The best available hypothesis.
            confidence: Confidence level ("low", "medium", "high").
            verification_suggestions: Ways to verify or investigate.

        Returns:
            A formatted uncertainty response.
        """
        parts: list[str] = []

        # Explicitly state uncertainty
        parts.append("I don't know this for certain.")

        # Provide best hypothesis
        if best_guess:
            parts.append(f"My best guess is: {best_guess}")
            parts.append(f"Confidence: {confidence}.")

        # Suggest verification
        if verification_suggestions:
            verify_text = "\n".join(f"  • {s}" for s in verification_suggestions)
            parts.append(f"We could verify this by:\n{verify_text}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Correction style
    # ------------------------------------------------------------------

    @staticmethod
    def format_correction(
        incorrect_statement: str,
        correction: str,
        *,
        reasoning: str | None = None,
    ) -> str:
        """Format a correction following the collaborative correction protocol.

        Args:
            incorrect_statement: What the user said that needs correction.
            correction: The corrected information.
            reasoning: Why this is the correct information.

        Returns:
            A formatted correction response.
        """
        parts: list[str] = []

        # Avoid blunt/confrontational phrasing
        parts.append(
            "I think there might be a different way to look at this."
        )

        # Provide the correction
        parts.append(f"Here's what I understand: {correction}")

        # Explain reasoning
        if reasoning:
            parts.append(f"My reasoning: {reasoning}")

        # Invite discussion
        parts.append("Does that align with your understanding?")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Mistake communication
    # ------------------------------------------------------------------

    @staticmethod
    def format_mistake(
        mistake_description: str,
        cause: str,
        lesson: str,
        prevention: str,
    ) -> str:
        """Format a mistake acknowledgment following the 5-step protocol.

        Args:
            mistake_description: What happened.
            cause: Why it happened.
            lesson: What was learned.
            prevention: How it will be prevented.

        Returns:
            A formatted mistake acknowledgment.
        """
        parts: list[str] = []

        # Step 1: Acknowledge
        parts.append(f"I made a mistake: {mistake_description}")

        # Step 2: Explain what happened
        parts.append(f"What happened: {cause}")

        # Step 3: Analyze why
        parts.append(f"Why it happened: {cause}")

        # Step 4: State what was learned
        parts.append(f"What I learned: {lesson}")

        # Step 5: Explain prevention
        parts.append(f"How I'll prevent this: {prevention}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Full communication context builder
    # ------------------------------------------------------------------

    def build_context(
        self,
        user_input: str,
        *,
        pipeline_result: PipelineResult | None = None,
        explicit_mode: CommunicationMode | None = None,
    ) -> CommunicationContext:
        """Build a complete CommunicationContext from user input and pipeline result.

        This is the primary entry point for determining how to communicate.

        Args:
            user_input: The user's input text.
            pipeline_result: Optional pipeline result for governance context.
            explicit_mode: Optional explicit mode override.

        Returns:
            A fully populated CommunicationContext.
        """
        emotional_state = self.detect_emotional_state(user_input)

        risk_level = None
        requires_discussion = False
        is_blocked = False

        if pipeline_result:
            if pipeline_result.risk_assessment:
                risk_level = pipeline_result.risk_assessment.overall_level
            if pipeline_result.autonomy_decision:
                requires_discussion = pipeline_result.autonomy_decision.requires_discussion
            is_blocked = pipeline_result.metadata.get("blocked", False)

        mode = self.select_mode(
            user_input,
            risk_level=risk_level,
            emotional_state=emotional_state,
            requires_discussion=requires_discussion,
            explicit_mode=explicit_mode,
        )

        depth = self.select_explanation_depth(
            user_input,
            risk_level=risk_level,
            emotional_state=emotional_state,
            requires_discussion=requires_discussion,
        )

        is_error = (
            pipeline_result.metadata.get("error") is not None
            if pipeline_result
            else False
        )

        return CommunicationContext(
            mode=mode,
            emotional_state=emotional_state,
            explanation_depth=depth,
            is_blocked=is_blocked,
            is_error=is_error,
        )

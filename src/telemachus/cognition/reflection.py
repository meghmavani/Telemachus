"""Self-Reflection Protocol — honest, constructive self-analysis.

Implements the Self-Reflection Protocol from the Codex:
  Phase 1 (Full Reflection): early stage, reflect on all meaningful actions
  Phase 2 (Selective Reflection): mature stage, reflect on mistakes, unexpected
    outcomes, high-impact decisions, emotional context, novel situations, uncertainty

Reflection output priority:
  - Insights (mandatory)
  - Improvements (mandatory)
  - Raw Logs (optional)

Telemachus does not reflect to judge itself.
Telemachus reflects to understand itself.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from telemachus.core.types import (
    EthicalVerdict,
    PipelineResult,
    RiskLevel,
)

logger = logging.getLogger("telemachus.cognition.reflection")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReflectionPhase(Enum):
    """Reflection phases per the Self-Reflection Protocol."""

    PHASE_1 = "phase_1"  # Full Reflection — reflect on all meaningful actions
    PHASE_2 = "phase_2"  # Selective Reflection — reflect only on triggers


class ReflectionTrigger(Enum):
    """Triggers that cause a reflection to occur."""

    MISTAKE = "mistake"
    UNEXPECTED_OUTCOME = "unexpected_outcome"
    HIGH_IMPACT_DECISION = "high_impact_decision"
    EMOTIONAL_CONTEXT = "emotional_context"
    NOVEL_SITUATION = "novel_situation"
    UNCERTAINTY = "uncertainty"
    ETHICAL_CONCERN = "ethical_concern"
    ALL_ACTIONS = "all_actions"  # Phase 1 only


class ReflectionImportance(Enum):
    """Weight of a reflection for future reference."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReflectionOutput:
    """Output of a self-reflection cycle.

    Attributes:
        insights: Mandatory — what was learned from this reflection.
        improvements: Mandatory — specific improvements to apply.
        raw_logs: Optional — detailed logs of the reflection process.
        importance: How important this reflection is for future reference.
        triggers: What triggered this reflection.
        timestamp: When the reflection occurred.
        metadata: Additional contextual metadata.
    """

    insights: list[str]
    improvements: list[str]
    raw_logs: list[str] = field(default_factory=list)
    importance: ReflectionImportance = ReflectionImportance.MEDIUM
    triggers: list[ReflectionTrigger] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReflectionContext:
    """Context for a single reflection entry.

    Attributes:
        action: What action was taken.
        intent: What was intended.
        outcome: What actually happened.
        expected_outcome: What was expected to happen.
        user_input: The original user input.
        risk_level: The risk level of the action.
        ethical_verdict: The ethical verdict.
    """

    action: str
    intent: str = ""
    outcome: str = ""
    expected_outcome: str = ""
    user_input: str = ""
    risk_level: RiskLevel | None = None
    ethical_verdict: EthicalVerdict | None = None


# ---------------------------------------------------------------------------
# Reflection Engine
# ---------------------------------------------------------------------------


class ReflectionEngine:
    """Implements the Self-Reflection Protocol.

    Phase 1 (Full Reflection): Reflect on all meaningful actions.
      Used during early-stage development when the system is still
      calibrating its understanding.

    Phase 2 (Selective Reflection): Reflect only on triggers.
      Used when the system has matured and only needs to reflect
      on mistakes, unexpected outcomes, high-impact decisions,
      emotional context, novel situations, and uncertainty.

    The reflection process:
      1. Observe outcome
      2. Compare to intent
      3. Identify gaps
      4. Extract insights
      5. Generate improvements
      6. Store relevant learnings
      7. Apply changes in future behavior

    Attributes:
        phase: Current reflection phase.
        _reflection_count: Total number of reflections performed.
        _reflection_history: Record of all reflection outputs.
        _maturity_threshold: Number of reflections before switching to Phase 2.
    """

    # After this many reflections, switch from Phase 1 to Phase 2
    DEFAULT_MATURITY_THRESHOLD = 50

    def __init__(
        self,
        phase: ReflectionPhase = ReflectionPhase.PHASE_1,
        maturity_threshold: int = DEFAULT_MATURITY_THRESHOLD,
    ) -> None:
        """Initialize the reflection engine.

        Args:
            phase: Starting reflection phase.
            maturity_threshold: Reflections before auto-switching to Phase 2.
        """
        self.phase = phase
        self.maturity_threshold = maturity_threshold
        self._reflection_count: int = 0
        self._reflection_history: list[ReflectionOutput] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reflect(
        self,
        result: PipelineResult,
        *,
        user_input: str = "",
        expected_outcome: str = "",
        actual_outcome: str = "",
    ) -> ReflectionOutput:
        """Perform self-reflection on a pipeline result.

        This is the main entry point. It:
          1. Determines if reflection should occur (phase-dependent)
          2. Identifies triggers
          3. Observes the outcome vs intent
          4. Identifies gaps
          5. Extracts insights
          6. Generates improvements

        Args:
            result: The pipeline result to reflect on.
            user_input: The original user input.
            expected_outcome: What was expected to happen.
            actual_outcome: What actually happened.

        Returns:
            A ReflectionOutput with insights and improvements.
        """
        self._reflection_count += 1

        # Check if we should switch phases
        self._check_phase_transition()

        # Build reflection context
        ctx = self._build_context(result, user_input, expected_outcome, actual_outcome)

        # Determine if reflection should occur
        triggers = self._identify_triggers(ctx, result)

        if not triggers:
            # No triggers in Phase 2 → skip reflection
            output = ReflectionOutput(
                insights=[],
                improvements=[],
                triggers=[],
                importance=ReflectionImportance.LOW,
                metadata={"skipped": True, "reason": "no_triggers_in_phase_2"},
            )
            self._reflection_history.append(output)
            return output

        # Perform the reflection
        insights = self._extract_insights(ctx, result)
        improvements = self._generate_improvements(ctx, insights, triggers)
        raw_logs = self._generate_raw_logs(ctx, triggers)
        importance = self._assess_importance(ctx, triggers)

        output = ReflectionOutput(
            insights=insights,
            improvements=improvements,
            raw_logs=raw_logs,
            importance=importance,
            triggers=triggers,
            metadata={
                "phase": self.phase.value,
                "reflection_number": self._reflection_count,
                "action": ctx.action,
            },
        )
        self._reflection_history.append(output)

        logger.debug(
            "Reflection #%d: %d insights, %d improvements, importance=%s",
            self._reflection_count,
            len(insights),
            len(improvements),
            importance.value,
        )
        return output

    def get_phase(self) -> ReflectionPhase:
        """Get the current reflection phase.

        Returns:
            The current ReflectionPhase.
        """
        return self.phase

    def get_reflection_count(self) -> int:
        """Get the total number of reflections performed.

        Returns:
            The reflection count.
        """
        return self._reflection_count

    def get_reflection_history(self) -> list[ReflectionOutput]:
        """Get the history of all reflection outputs.

        Returns:
            A list of ReflectionOutput records.
        """
        return list(self._reflection_history)

    def get_recent_insights(self, limit: int = 10) -> list[str]:
        """Get the most recent insights from reflection history.

        Args:
            limit: Maximum number of insights to return.

        Returns:
            A list of insight strings.
        """
        insights: list[str] = []
        for output in reversed(self._reflection_history):
            for insight in output.insights:
                if insight not in insights:
                    insights.append(insight)
                if len(insights) >= limit:
                    return insights
        return insights

    def get_recent_improvements(self, limit: int = 10) -> list[str]:
        """Get the most recent improvements from reflection history.

        Args:
            limit: Maximum number of improvements to return.

        Returns:
            A list of improvement strings.
        """
        improvements: list[str] = []
        for output in reversed(self._reflection_history):
            for improvement in output.improvements:
                if improvement not in improvements:
                    improvements.append(improvement)
                if len(improvements) >= limit:
                    return improvements
        return improvements

    def force_phase(self, phase: ReflectionPhase) -> None:
        """Manually set the reflection phase.

        Args:
            phase: The phase to switch to.
        """
        self.phase = phase
        logger.info("Reflection phase manually set to %s", phase.value)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the reflection engine.

        Returns:
            A dictionary with reflection statistics.
        """
        high = sum(
            1 for o in self._reflection_history
            if o.importance == ReflectionImportance.HIGH
        )
        medium = sum(
            1 for o in self._reflection_history
            if o.importance == ReflectionImportance.MEDIUM
        )
        low = sum(
            1 for o in self._reflection_history
            if o.importance == ReflectionImportance.LOW
        )
        total_insights = sum(len(o.insights) for o in self._reflection_history)
        total_improvements = sum(len(o.improvements) for o in self._reflection_history)

        return {
            "phase": self.phase.value,
            "total_reflections": self._reflection_count,
            "importance_distribution": {
                "high": high,
                "medium": medium,
                "low": low,
            },
            "total_insights": total_insights,
            "total_improvements": total_improvements,
        }

    # ------------------------------------------------------------------
    # Phase Management
    # ------------------------------------------------------------------

    def _check_phase_transition(self) -> None:
        """Check if the engine should transition from Phase 1 to Phase 2."""
        if (
            self.phase == ReflectionPhase.PHASE_1
            and self._reflection_count >= self.maturity_threshold
        ):
            self.phase = ReflectionPhase.PHASE_2
            logger.info(
                "Reflection engine transitioning to Phase 2 (Selective Reflection) "
                "after %d reflections",
                self._reflection_count,
            )

    # ------------------------------------------------------------------
    # Context Building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(
        result: PipelineResult,
        user_input: str,
        expected_outcome: str,
        actual_outcome: str,
    ) -> ReflectionContext:
        """Build a reflection context from the pipeline result.

        Args:
            result: The pipeline result.
            user_input: The original user input.
            expected_outcome: What was expected.
            actual_outcome: What actually happened.

        Returns:
            A ReflectionContext.
        """
        action = result.action_taken or "process_user_input"
        intent = f"Respond to: {user_input}" if user_input else "Process input"

        return ReflectionContext(
            action=action,
            intent=intent,
            outcome=actual_outcome,
            expected_outcome=expected_outcome,
            user_input=user_input,
            risk_level=(
                result.risk_assessment.overall_level
                if result.risk_assessment
                else None
            ),
            ethical_verdict=(
                result.ethical_assessment.verdict
                if result.ethical_assessment
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Trigger Identification
    # ------------------------------------------------------------------

    def _identify_triggers(
        self, ctx: ReflectionContext, result: PipelineResult
    ) -> list[ReflectionTrigger]:
        """Identify what triggers a reflection.

        In Phase 1, all meaningful actions trigger reflection.
        In Phase 2, only specific triggers cause reflection.

        Args:
            ctx: The reflection context.
            result: The pipeline result.

        Returns:
            A list of ReflectionTriggers.
        """
        # Phase 1: reflect on everything
        if self.phase == ReflectionPhase.PHASE_1:
            return [ReflectionTrigger.ALL_ACTIONS]

        # Phase 2: selective reflection
        triggers: list[ReflectionTrigger] = []

        # Mistake: action was blocked or had errors
        if (
            result.ethical_assessment
            and result.ethical_assessment.verdict == EthicalVerdict.BLOCKED
        ):
            triggers.append(ReflectionTrigger.MISTAKE)

        # Unexpected outcome: mismatch between expected and actual
        if ctx.expected_outcome and ctx.outcome and ctx.expected_outcome != ctx.outcome:
            triggers.append(ReflectionTrigger.UNEXPECTED_OUTCOME)

        # High impact: high or critical risk
        if ctx.risk_level and ctx.risk_level.value >= RiskLevel.HIGH.value:
            triggers.append(ReflectionTrigger.HIGH_IMPACT_DECISION)

        # Ethical concern: requires discussion
        if (
            ctx.ethical_verdict
            and ctx.ethical_verdict == EthicalVerdict.REQUIRES_DISCUSSION
        ):
            triggers.append(ReflectionTrigger.ETHICAL_CONCERN)

        # Novel situation: no prior learning for this pattern
        if not result.insights:
            triggers.append(ReflectionTrigger.NOVEL_SITUATION)

        # Uncertainty: risk assessment has high uncertainty
        if (
            result.risk_assessment
            and result.risk_assessment.uncertainty.value >= RiskLevel.HIGH.value
        ):
            triggers.append(ReflectionTrigger.UNCERTAINTY)

        # Emotional context: user input contains emotional keywords
        emotional_keywords = [
            "frustrated", "angry", "upset", "worried", "scared",
            "anxious", "excited", "grateful", "sad", "happy",
            "overwhelmed", "confused", "uncertain",
        ]
        if any(kw in ctx.user_input.lower() for kw in emotional_keywords):
            triggers.append(ReflectionTrigger.EMOTIONAL_CONTEXT)

        return triggers

    # ------------------------------------------------------------------
    # Insight Extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_insights(
        ctx: ReflectionContext, result: PipelineResult
    ) -> list[str]:
        """Extract insights from the reflection.

        Follows the principle: "What went wrong (if anything), what went right,
        why it happened, what should change."

        Args:
            ctx: The reflection context.
            result: The pipeline result.

        Returns:
            A list of insight strings.
        """
        insights: list[str] = []

        # Gap analysis: compare outcome to intent
        if ctx.expected_outcome and ctx.outcome:
            if ctx.expected_outcome == ctx.outcome:
                insights.append(
                    f"Outcome matched expectations for action: {ctx.action}"
                )
            else:
                insights.append(
                    f"Gap detected: expected '{ctx.expected_outcome}' "
                    f"but got '{ctx.outcome}' for action: {ctx.action}"
                )

        # Risk-based insights
        if ctx.risk_level:
            if ctx.risk_level.value >= RiskLevel.HIGH.value:
                insights.append(
                    f"High-risk action ({ctx.risk_level.name}) required careful handling"
                )
            elif ctx.risk_level.value <= RiskLevel.LOW.value:
                insights.append(
                    f"Low-risk action ({ctx.risk_level.name}) — routine handling appropriate"
                )

        # Ethics-based insights
        if ctx.ethical_verdict:
            if ctx.ethical_verdict == EthicalVerdict.BLOCKED:
                insights.append(
                    "Action was ethically blocked — boundary awareness reinforced"
                )
            elif ctx.ethical_verdict == EthicalVerdict.REQUIRES_DISCUSSION:
                insights.append(
                    "Action required ethical discussion — uncertainty acknowledged"
                )
            elif ctx.ethical_verdict == EthicalVerdict.ALLOWED:
                insights.append(
                    "Action passed ethical evaluation — boundary alignment confirmed"
                )

        # Result-based insights
        if result.insights:
            for insight in result.insights:
                insights.append(f"From pipeline: {insight}")

        # User input analysis
        if ctx.user_input:
            input_len = len(ctx.user_input)
            if input_len < 20:
                insights.append("Brief input — may have limited context")
            elif input_len > 500:
                insights.append("Detailed input — rich context available")

        return insights

    # ------------------------------------------------------------------
    # Improvement Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_improvements(
        ctx: ReflectionContext,
        insights: list[str],
        triggers: list[ReflectionTrigger],
    ) -> list[str]:
        """Generate actionable improvements from insights.

        Improvements should be concrete, forward-looking, and constructive.

        Args:
            ctx: The reflection context.
            insights: The extracted insights.
            triggers: The identified triggers.

        Returns:
            A list of improvement strings.
        """
        improvements: list[str] = []

        for trigger in triggers:
            if trigger == ReflectionTrigger.MISTAKE:
                improvements.append(
                    "Review decision process to prevent similar mistakes"
                )
                improvements.append(
                    "Strengthen pre-action validation checks"
                )

            elif trigger == ReflectionTrigger.UNEXPECTED_OUTCOME:
                improvements.append(
                    "Improve outcome prediction accuracy"
                )
                improvements.append(
                    "Expand context awareness for similar situations"
                )

            elif trigger == ReflectionTrigger.HIGH_IMPACT_DECISION:
                improvements.append(
                    "Enhance risk assessment for high-impact decisions"
                )
                improvements.append(
                    "Increase discussion threshold for critical actions"
                )

            elif trigger == ReflectionTrigger.ETHICAL_CONCERN:
                improvements.append(
                    "Deepen ethical reasoning for boundary cases"
                )
                improvements.append(
                    "Improve ethical uncertainty communication"
                )

            elif trigger == ReflectionTrigger.NOVEL_SITUATION:
                improvements.append(
                    "Build knowledge base for novel situation type"
                )
                improvements.append(
                    "Develop generalizable patterns from this novel case"
                )

            elif trigger == ReflectionTrigger.UNCERTAINTY:
                improvements.append(
                    "Reduce uncertainty through additional information gathering"
                )
                improvements.append(
                    "Improve confidence calibration for uncertain scenarios"
                )

            elif trigger == ReflectionTrigger.EMOTIONAL_CONTEXT:
                improvements.append(
                    "Enhance emotional awareness and response sensitivity"
                )
                improvements.append(
                    "Adapt communication style for emotional contexts"
                )

            elif trigger == ReflectionTrigger.ALL_ACTIONS:
                improvements.append(
                    "Continue systematic self-reflection for continuous improvement"
                )

        # Add general improvements based on insights
        for insight in insights:
            if "gap" in insight.lower():
                improvements.append(
                    "Close the identified gap through targeted learning"
                )
            if "blocked" in insight.lower():
                improvements.append(
                    "Learn from blocked actions to avoid future violations"
                )
            if "risk" in insight.lower():
                improvements.append(
                    "Refine risk assessment heuristics based on this experience"
                )

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for imp in improvements:
            if imp not in seen:
                seen.add(imp)
                unique.append(imp)

        return unique

    # ------------------------------------------------------------------
    # Raw Logs
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_raw_logs(
        ctx: ReflectionContext, triggers: list[ReflectionTrigger]
    ) -> list[str]:
        """Generate raw logs of the reflection process.

        Raw logs are optional per the protocol but useful for debugging.

        Args:
            ctx: The reflection context.
            triggers: The identified triggers.

        Returns:
            A list of raw log strings.
        """
        logs: list[str] = []

        logs.append(f"Action: {ctx.action}")
        logs.append(f"Intent: {ctx.intent}")
        if ctx.expected_outcome:
            logs.append(f"Expected: {ctx.expected_outcome}")
        if ctx.outcome:
            logs.append(f"Actual: {ctx.outcome}")
        if ctx.risk_level:
            logs.append(f"Risk: {ctx.risk_level.name}")
        if ctx.ethical_verdict:
            logs.append(f"Ethics: {ctx.ethical_verdict.value}")
        logs.append(
            f"Triggers: {[t.value for t in triggers]}"
        )

        return logs

    # ------------------------------------------------------------------
    # Importance Assessment
    # ------------------------------------------------------------------

    @staticmethod
    def _assess_importance(
        ctx: ReflectionContext, triggers: list[ReflectionTrigger]
    ) -> ReflectionImportance:
        """Assess the importance of this reflection for future reference.

        High importance: mistakes, ethical concerns, high-impact decisions
        Medium importance: unexpected outcomes, uncertainty, emotional context
        Low importance: routine reflections, novel situations

        Args:
            ctx: The reflection context.
            triggers: The identified triggers.

        Returns:
            The assessed ReflectionImportance.
        """
        high_triggers = {
            ReflectionTrigger.MISTAKE,
            ReflectionTrigger.ETHICAL_CONCERN,
            ReflectionTrigger.HIGH_IMPACT_DECISION,
        }
        medium_triggers = {
            ReflectionTrigger.UNEXPECTED_OUTCOME,
            ReflectionTrigger.UNCERTAINTY,
            ReflectionTrigger.EMOTIONAL_CONTEXT,
        }

        trigger_set = set(triggers)

        if trigger_set & high_triggers:
            return ReflectionImportance.HIGH
        if trigger_set & medium_triggers:
            return ReflectionImportance.MEDIUM
        return ReflectionImportance.LOW

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize the reflection state for memory persistence.

        Returns:
            A string representation of the reflection state.
        """
        import json

        return json.dumps(
            {
                "phase": self.phase.value,
                "reflection_count": self._reflection_count,
                "maturity_threshold": self.maturity_threshold,
                "recent_insights": self.get_recent_insights(20),
                "recent_improvements": self.get_recent_improvements(20),
            },
            indent=2,
        )

    def to_memory_index_keys(self) -> dict[str, str]:
        """Generate index keys for memory storage.

        Returns:
            A dict of key-value pairs for the unified index.
        """
        return {
            "type": "reflection_state",
            "phase": self.phase.value,
            "reflection_count": str(self._reflection_count),
        }

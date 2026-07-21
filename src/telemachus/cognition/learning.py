"""Learning Engine — experience-based behavioral improvement.

Implements the Learning Framework from the Codex:
  Experience → Interpretation → Pattern Extraction → Model Update → Behavioral Adjustment

Learning is not accumulation. Learning is refinement.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from telemachus.core.types import PipelineResult

logger = logging.getLogger("telemachus.cognition.learning")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LearningType(Enum):
    """Types of learning per the Learning Framework."""

    BEHAVIORAL = "behavioral"  # improves interaction patterns
    COGNITIVE = "cognitive"  # improves reasoning ability
    PREFERENCE = "preference"  # improves alignment with Revan
    STRUCTURAL = "structural"  # improves internal organization


class LearningSignalSource(Enum):
    """Where a learning signal originates."""

    REVAN_FEEDBACK = "revan_feedback"
    REAL_WORLD_OUTCOME = "real_world_outcome"
    REFLECTION_INSIGHT = "reflection_insight"
    RESEARCH_VALIDATION = "research_validation"
    PATTERN_REPETITION = "pattern_repetition"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningSignal:
    """A single learning signal extracted from experience.

    Attributes:
        source: Where the signal came from (priority per the learning hierarchy).
        learning_type: The type of learning this signal drives.
        pattern: The pattern or insight extracted.
        confidence: Confidence in this signal (0.0 to 1.0).
        context: Contextual information about when this applies.
        timestamp: When the signal was created.
    """

    source: LearningSignalSource
    learning_type: LearningType
    pattern: str
    confidence: float = 0.5
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass(frozen=True)
class LearningUpdate:
    """Result of processing learning signals.

    Attributes:
        signals_processed: Number of signals processed.
        patterns_extracted: Patterns identified from the signals.
        behavioral_adjustments: Specific behavioral changes to apply.
        insights: Human-readable insights from this learning cycle.
        metadata: Additional metadata about the learning cycle.
    """

    signals_processed: int = 0
    patterns_extracted: list[str] = field(default_factory=list)
    behavioral_adjustments: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Learning Engine
# ---------------------------------------------------------------------------


class LearningEngine:
    """Processes experiences into learning signals and behavioral adjustments.

    Implements the Learning Framework:
      - Experience → Interpretation → Pattern Extraction → Model Update
      - Learning hierarchy: Revan feedback > real-world outcomes > reflection
        insights > research validation > pattern repetition
      - Stability constraint: learning must not destabilize identity
      - Conflict handling: preserve both interpretations, determine context
      - Reinforcement: successful patterns become stronger defaults
      - Unlearning: reduce confidence in outdated knowledge
      - Meta-learning: improve how learning itself works

    Attributes:
        _learned_patterns: Accumulated patterns with confidence scores.
        _behavioral_defaults: Preferred behavioral strategies.
        _learning_history: Record of all learning updates.
    """

    def __init__(self) -> None:
        """Initialize the learning engine with empty state."""
        self._learned_patterns: dict[str, float] = {}
        self._behavioral_defaults: dict[str, float] = {}
        self._learning_history: list[LearningUpdate] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_experience(
        self,
        result: PipelineResult,
        *,
        user_input: str = "",
        feedback: str | None = None,
        outcome: str | None = None,
    ) -> LearningUpdate:
        """Process a pipeline result to extract learning signals.

        This is the main entry point for the learning loop. It:
          1. Interprets the experience (what happened, what was expected)
          2. Extracts patterns from the outcome
          3. Updates internal models
          4. Produces behavioral adjustments

        Args:
            result: The pipeline result to learn from.
            user_input: The original user input that triggered this.
            feedback: Optional explicit feedback from Revan.
            outcome: Optional description of the real-world outcome.

        Returns:
            A LearningUpdate with extracted patterns and adjustments.
        """
        signals: list[LearningSignal] = []

        # 1. Extract signals from feedback (highest priority)
        if feedback:
            signals.extend(self._extract_feedback_signals(feedback))

        # 2. Extract signals from outcome
        if outcome:
            signals.extend(self._extract_outcome_signals(outcome))

        # 3. Extract signals from the pipeline result itself
        signals.extend(self._extract_result_signals(result, user_input))

        # 4. Check for pattern repetition
        signals.extend(self._extract_pattern_repetition(result, user_input))

        # 5. Process all signals into an update
        return self._process_signals(signals)

    def get_learned_patterns(self) -> dict[str, float]:
        """Get all learned patterns with their confidence scores.

        Returns:
            A dict mapping pattern descriptions to confidence scores.
        """
        return dict(self._learned_patterns)

    def get_behavioral_defaults(self) -> dict[str, float]:
        """Get behavioral defaults with their strength scores.

        Returns:
            A dict mapping behavioral strategies to strength scores.
        """
        return dict(self._behavioral_defaults)

    def get_learning_history(self) -> list[LearningUpdate]:
        """Get the history of all learning updates.

        Returns:
            A list of LearningUpdate records.
        """
        return list(self._learning_history)

    def reduce_confidence(self, pattern: str, amount: float = 0.1) -> float:
        """Reduce confidence in a learned pattern (unlearning).

        Args:
            pattern: The pattern to reduce confidence in.
            amount: How much to reduce confidence by (0.0 to 1.0).

        Returns:
            The new confidence score, or 0.0 if pattern was removed.
        """
        if pattern in self._learned_patterns:
            self._learned_patterns[pattern] = max(
                0.0, self._learned_patterns[pattern] - amount
            )
            if self._learned_patterns[pattern] <= 0.0:
                del self._learned_patterns[pattern]
                return 0.0
            return self._learned_patterns[pattern]
        return 0.0

    def reinforce_pattern(self, pattern: str, amount: float = 0.05) -> float:
        """Reinforce a learned pattern (increase confidence).

        Args:
            pattern: The pattern to reinforce.
            amount: How much to increase confidence by (0.0 to 1.0).

        Returns:
            The new confidence score.
        """
        current = self._learned_patterns.get(pattern, 0.0)
        new_confidence = min(1.0, current + amount)
        self._learned_patterns[pattern] = new_confidence
        return new_confidence

    def get_learning_stats(self) -> dict[str, Any]:
        """Get statistics about the learning engine state.

        Returns:
            A dictionary with learning statistics.
        """
        return {
            "total_patterns": len(self._learned_patterns),
            "total_defaults": len(self._behavioral_defaults),
            "total_updates": len(self._learning_history),
            "avg_pattern_confidence": (
                sum(self._learned_patterns.values()) / len(self._learned_patterns)
                if self._learned_patterns
                else 0.0
            ),
            "top_patterns": sorted(
                self._learned_patterns.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    # ------------------------------------------------------------------
    # Signal Extraction
    # ------------------------------------------------------------------

    def _extract_feedback_signals(self, feedback: str) -> list[LearningSignal]:
        """Extract learning signals from explicit Revan feedback.

        Args:
            feedback: The feedback text from Revan.

        Returns:
            A list of LearningSignals extracted from the feedback.
        """
        signals: list[LearningSignal] = []
        feedback_lower = feedback.lower()

        # Positive feedback → reinforce current patterns
        positive_keywords = [
            "good", "great", "correct", "right", "helpful",
            "exactly", "perfect", "thanks", "thank you",
            "well done", "nice", "awesome",
        ]
        if any(kw in feedback_lower for kw in positive_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REVAN_FEEDBACK,
                    learning_type=LearningType.PREFERENCE,
                    pattern="positive_feedback_received",
                    confidence=0.8,
                    context={"feedback": feedback},
                )
            )

        # Corrective feedback → adjust behavior
        corrective_keywords = [
            "wrong", "incorrect", "not right", "mistake",
            "should have", "instead", "actually", "but",
            "no", "don't", "stop",
        ]
        if any(kw in feedback_lower for kw in corrective_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REVAN_FEEDBACK,
                    learning_type=LearningType.BEHAVIORAL,
                    pattern="corrective_feedback_received",
                    confidence=0.7,
                    context={"feedback": feedback},
                )
            )

        # Tone/alignment feedback
        tone_keywords = [
            "tone", "style", "too formal", "too casual",
            "be more", "be less", "sound",
        ]
        if any(kw in feedback_lower for kw in tone_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REVAN_FEEDBACK,
                    learning_type=LearningType.PREFERENCE,
                    pattern="tone_adjustment_needed",
                    confidence=0.6,
                    context={"feedback": feedback},
                )
            )

        return signals

    def _extract_outcome_signals(self, outcome: str) -> list[LearningSignal]:
        """Extract learning signals from real-world outcomes.

        Args:
            outcome: Description of the real-world outcome.

        Returns:
            A list of LearningSignals extracted from the outcome.
        """
        signals: list[LearningSignal] = []
        outcome_lower = outcome.lower()

        # Successful outcome
        success_keywords = [
            "success", "succeeded", "worked", "achieved", "completed",
            "resolved", "solved", "fixed", "passed",
        ]
        if any(kw in outcome_lower for kw in success_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REAL_WORLD_OUTCOME,
                    learning_type=LearningType.BEHAVIORAL,
                    pattern="successful_outcome",
                    confidence=0.75,
                    context={"outcome": outcome},
                )
            )

        # Failed outcome
        failure_keywords = [
            "failed", "error", "didn't work", "broke",
            "problem", "issue", "bug",
        ]
        if any(kw in outcome_lower for kw in failure_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REAL_WORLD_OUTCOME,
                    learning_type=LearningType.COGNITIVE,
                    pattern="failed_outcome",
                    confidence=0.75,
                    context={"outcome": outcome},
                )
            )

        # Unexpected outcome
        unexpected_keywords = [
            "unexpected", "surprising", "didn't expect",
            "strange", "odd", "weird",
        ]
        if any(kw in outcome_lower for kw in unexpected_keywords):
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.REAL_WORLD_OUTCOME,
                    learning_type=LearningType.COGNITIVE,
                    pattern="unexpected_outcome",
                    confidence=0.65,
                    context={"outcome": outcome},
                )
            )

        return signals

    def _extract_result_signals(
        self, result: PipelineResult, user_input: str
    ) -> list[LearningSignal]:
        """Extract learning signals from the pipeline result itself.

        Args:
            result: The pipeline result.
            user_input: The original user input.

        Returns:
            A list of LearningSignals extracted from the result.
        """
        signals: list[LearningSignal] = []

        # Blocked actions → learn about boundaries
        if result.ethical_assessment and result.ethical_assessment.verdict.value == "blocked":
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.PATTERN_REPETITION,
                    learning_type=LearningType.BEHAVIORAL,
                    pattern="action_blocked_by_ethics",
                    confidence=0.6,
                    context={
                        "user_input": user_input,
                        "reason": result.ethical_assessment.reasoning,
                    },
                )
            )

        # High risk → learn caution
        if result.risk_assessment and result.risk_assessment.overall_level.value >= 3:
            signals.append(
                LearningSignal(
                    source=LearningSignalSource.PATTERN_REPETITION,
                    learning_type=LearningType.BEHAVIORAL,
                    pattern="high_risk_action_encountered",
                    confidence=0.55,
                    context={
                        "user_input": user_input,
                        "risk_level": result.risk_assessment.overall_level.name,
                    },
                )
            )

        # Insights from the result
        if result.insights:
            for insight in result.insights:
                signals.append(
                    LearningSignal(
                        source=LearningSignalSource.REFLECTION_INSIGHT,
                        learning_type=LearningType.COGNITIVE,
                        pattern=insight,
                        confidence=0.5,
                        context={"user_input": user_input},
                    )
                )

        return signals

    def _extract_pattern_repetition(
        self, result: PipelineResult, user_input: str
    ) -> list[LearningSignal]:
        """Check for repeated patterns across interactions.

        Args:
            result: The pipeline result.
            user_input: The original user input.

        Returns:
            A list of LearningSignals for repeated patterns.
        """
        signals: list[LearningSignal] = []

        # Check if similar patterns have been seen before
        input_lower = user_input.lower()
        for pattern, confidence in self._learned_patterns.items():
            if confidence > 0.5 and any(
                word in input_lower for word in pattern.lower().split()
            ):
                signals.append(
                    LearningSignal(
                        source=LearningSignalSource.PATTERN_REPETITION,
                        learning_type=LearningType.BEHAVIORAL,
                        pattern=f"repeated_pattern: {pattern}",
                        confidence=min(1.0, confidence + 0.05),
                        context={"user_input": user_input},
                    )
                )

        return signals

    # ------------------------------------------------------------------
    # Signal Processing
    # ------------------------------------------------------------------

    def _process_signals(self, signals: list[LearningSignal]) -> LearningUpdate:
        """Process extracted signals into a learning update.

        Implements the learning hierarchy:
          1. Revan feedback
          2. Real-world outcomes
          3. Reflection insights
          4. Research validation
          5. Pattern repetition

        Args:
            signals: The extracted learning signals.

        Returns:
            A LearningUpdate with patterns and adjustments.
        """
        if not signals:
            update = LearningUpdate(signals_processed=0)
            self._learning_history.append(update)
            return update

        # Sort by source priority
        priority_order = {
            LearningSignalSource.REVAN_FEEDBACK: 0,
            LearningSignalSource.REAL_WORLD_OUTCOME: 1,
            LearningSignalSource.REFLECTION_INSIGHT: 2,
            LearningSignalSource.RESEARCH_VALIDATION: 3,
            LearningSignalSource.PATTERN_REPETITION: 4,
        }
        sorted_signals = sorted(
            signals, key=lambda s: priority_order.get(s.source, 99)
        )

        patterns: list[str] = []
        adjustments: list[str] = []
        insights: list[str] = []

        for signal in sorted_signals:
            # Extract pattern
            patterns.append(signal.pattern)

            # Update learned patterns with confidence
            existing = self._learned_patterns.get(signal.pattern, 0.0)
            # Weighted update: higher-priority sources have more impact
            source_weight = {
                LearningSignalSource.REVAN_FEEDBACK: 0.3,
                LearningSignalSource.REAL_WORLD_OUTCOME: 0.2,
                LearningSignalSource.REFLECTION_INSIGHT: 0.15,
                LearningSignalSource.RESEARCH_VALIDATION: 0.1,
                LearningSignalSource.PATTERN_REPETITION: 0.05,
            }.get(signal.source, 0.05)

            new_confidence = min(
                1.0,
                existing + (signal.confidence * source_weight),
            )
            self._learned_patterns[signal.pattern] = new_confidence

            # Generate behavioral adjustments
            adjustment = self._generate_adjustment(signal)
            if adjustment:
                adjustments.append(adjustment)

            # Generate insight
            insight = self._generate_insight(signal)
            if insight:
                insights.append(insight)

        # Update behavioral defaults
        for adj in adjustments:
            self._behavioral_defaults[adj] = self._behavioral_defaults.get(adj, 0.0) + 0.1

        update = LearningUpdate(
            signals_processed=len(signals),
            patterns_extracted=patterns,
            behavioral_adjustments=adjustments,
            insights=insights,
            metadata={
                "signal_sources": [s.source.value for s in signals],
                "learning_types": [s.learning_type.value for s in signals],
            },
        )
        self._learning_history.append(update)
        logger.debug(
            "Learning update: %d signals → %d patterns, %d adjustments",
            len(signals),
            len(patterns),
            len(adjustments),
        )
        return update

    # ------------------------------------------------------------------
    # Adjustment & Insight Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_adjustment(signal: LearningSignal) -> str | None:
        """Generate a behavioral adjustment from a learning signal.

        Args:
            signal: The learning signal.

        Returns:
            A behavioral adjustment string, or None.
        """
        if signal.learning_type == LearningType.BEHAVIORAL:
            if "corrective" in signal.pattern:
                return "Adjust response strategy based on corrective feedback"
            if "blocked" in signal.pattern:
                return "Avoid actions that trigger ethical blocks"
            if "high_risk" in signal.pattern:
                return "Increase caution for high-risk action patterns"
            if "successful" in signal.pattern:
                return "Reinforce successful interaction pattern"
            if "failed" in signal.pattern:
                return "Review and adjust approach for similar situations"
            return "Refine behavioral response based on outcome"

        if signal.learning_type == LearningType.COGNITIVE:
            if "unexpected" in signal.pattern:
                return "Improve uncertainty handling for unexpected outcomes"
            if "failed" in signal.pattern:
                return "Strengthen reasoning for failure-prone scenarios"
            return "Enhance cognitive model based on new information"

        if signal.learning_type == LearningType.PREFERENCE:
            if "tone" in signal.pattern:
                return "Adjust communication tone based on feedback"
            if "positive" in signal.pattern:
                return "Maintain and reinforce preferred interaction style"
            return "Align behavior with expressed preferences"

        if signal.learning_type == LearningType.STRUCTURAL:
            return "Optimize internal organization based on patterns"

        return None

    @staticmethod
    def _generate_insight(signal: LearningSignal) -> str | None:
        """Generate a human-readable insight from a learning signal.

        Args:
            signal: The learning signal.

        Returns:
            An insight string, or None.
        """
        source_labels = {
            LearningSignalSource.REVAN_FEEDBACK: "Revan's feedback",
            LearningSignalSource.REAL_WORLD_OUTCOME: "real-world outcome",
            LearningSignalSource.REFLECTION_INSIGHT: "self-reflection",
            LearningSignalSource.RESEARCH_VALIDATION: "research validation",
            LearningSignalSource.PATTERN_REPETITION: "pattern repetition",
        }
        source_label = source_labels.get(signal.source, "experience")

        if signal.learning_type == LearningType.BEHAVIORAL:
            return f"Learned from {source_label}: {signal.pattern.replace('_', ' ')}"
        if signal.learning_type == LearningType.COGNITIVE:
            return f"Reasoning improved from {source_label}: {signal.pattern.replace('_', ' ')}"
        if signal.learning_type == LearningType.PREFERENCE:
            return f"Alignment refined from {source_label}: {signal.pattern.replace('_', ' ')}"
        if signal.learning_type == LearningType.STRUCTURAL:
            return f"Structure optimized from {source_label}: {signal.pattern.replace('_', ' ')}"

        return None

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize the learning state for memory persistence.

        Returns:
            A string representation of the learning state.
        """
        import json

        return json.dumps(
            {
                "learned_patterns": self._learned_patterns,
                "behavioral_defaults": self._behavioral_defaults,
                "update_count": len(self._learning_history),
            },
            indent=2,
        )

    def to_memory_index_keys(self) -> dict[str, str]:
        """Generate index keys for memory storage.

        Returns:
            A dict of key-value pairs for the unified index.
        """
        return {
            "type": "learning_state",
            "pattern_count": str(len(self._learned_patterns)),
            "default_count": str(len(self._behavioral_defaults)),
        }

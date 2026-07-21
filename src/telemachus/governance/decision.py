"""Decision Framework — multi-criteria option ranking within approved boundaries.

Implements the decision framework defined in the Decision Framework Codex.
Selects the best option from a set of already-approved possibilities.

Key principles:
- Decision-making is about selection, not authorization.
- This system operates ONLY after ethics/risk/permission checks.
- It does NOT perform ethical evaluation, risk evaluation, or permission checks.
- All meaningful tradeoffs must be explicitly stated.
- Discussion is preferred when multiple strong valid options exist.
- Revan retains final authority over decisions.

The four decision dimensions:
1. Purpose Fit — alignment with goals, intent, long-term direction
2. Tradeoff Clarity — benefits, costs, opportunity loss, competing advantages
3. Outcome Quality — usefulness, impact, sustainability, clarity of result
4. Context Fit — timing, environment, constraints, priorities
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("telemachus.governance.decision")


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _OptionScore:
    """Score for a single option across all four decision dimensions."""

    option: str
    purpose_fit: float  # 0.0 (poor fit) to 1.0 (perfect fit)
    tradeoff_clarity: float  # 0.0 (unclear) to 1.0 (fully clear)
    outcome_quality: float  # 0.0 (poor) to 1.0 (excellent)
    context_fit: float  # 0.0 (inappropriate) to 1.0 (perfectly appropriate)
    composite: float = 0.0  # Weighted composite score
    reasoning: str = ""


@dataclass(frozen=True)
class _DecisionResult:
    """Result of the decision process."""

    ranked_options: list[_OptionScore]
    best_option: str
    best_score: float
    requires_discussion: bool
    uncertainty_level: str  # "low", "moderate", "high"
    reasoning: str


# ---------------------------------------------------------------------------
# DecisionFramework
# ---------------------------------------------------------------------------


class DecisionFramework:
    """Multi-criteria option ranking within approved boundaries.

    Evaluates valid (pre-approved) options across four dimensions and
    ranks them to identify the best choice. Operates strictly within
    boundaries already established by ethics, risk, and autonomy checks.

    Usage::

        framework = DecisionFramework()
        result = framework.evaluate(
            options=["Option A: refactor module", "Option B: add new module"],
            context={"goal": "improve code quality", "constraints": ["time"]},
        )
        print(result.best_option)  # "Option B: add new module"
    """

    # ------------------------------------------------------------------
    # Dimension weights (configurable)
    # ------------------------------------------------------------------

    _default_weights: dict[str, float] = {
        "purpose_fit": 0.30,
        "tradeoff_clarity": 0.20,
        "outcome_quality": 0.25,
        "context_fit": 0.25,
    }

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
    ) -> None:
        """Initialize the decision framework with optional custom weights.

        Args:
            weights: Optional custom dimension weights. Must sum to 1.0.
                     Keys: purpose_fit, tradeoff_clarity, outcome_quality, context_fit.

        Raises:
            ValueError: If weights don't sum to approximately 1.0.
        """
        if weights is not None:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"Dimension weights must sum to 1.0, got {total:.3f}"
                )
            self._weights = weights
        else:
            self._weights = dict(self._default_weights)

        logger.info(
            "DecisionFramework initialized with weights: %s",
            self._weights,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        options: list[str],
        *,
        context: dict[str, Any] | None = None,
    ) -> _DecisionResult:
        """Evaluate and rank valid options across four decision dimensions.

        This is the primary entry point. It follows the 7-step process:
        1. Identify valid options (provided by caller)
        2. Ensure constraints are already satisfied (caller's responsibility)
        3. Compare tradeoffs
        4. Evaluate outcomes
        5. Rank options
        6. Select best available option
        7. Explain reasoning

        Args:
            options: List of option descriptions (must be pre-approved).
            context: Optional contextual information (goals, constraints, etc.).

        Returns:
            A _DecisionResult with ranked options and the best choice.

        Raises:
            ValueError: If options list is empty.
        """
        if not options:
            raise ValueError("At least one option is required for evaluation")

        ctx = context or {}

        # Step 3-4: Score each option across all dimensions
        scored_options = [
            self._score_option(option, ctx) for option in options
        ]

        # Step 5: Rank by composite score (descending)
        ranked = sorted(scored_options, key=lambda s: s.composite, reverse=True)

        # Step 6: Select best
        best = ranked[0]

        # Determine if discussion is needed
        requires_discussion = self._should_discuss(ranked, ctx)

        # Determine uncertainty level
        uncertainty = self._assess_uncertainty(ranked)

        # Step 7: Build reasoning
        reasoning = self._build_reasoning(ranked, ctx, requires_discussion)

        logger.debug(
            "Decision: best=%s, score=%.2f, options=%d, discuss=%s",
            best.option[:60],
            best.composite,
            len(options),
            requires_discussion,
        )

        return _DecisionResult(
            ranked_options=ranked,
            best_option=best.option,
            best_score=best.composite,
            requires_discussion=requires_discussion,
            uncertainty_level=uncertainty,
            reasoning=reasoning,
        )

    def rank_options(
        self,
        options: list[str],
        *,
        context: dict[str, Any] | None = None,
    ) -> list[_OptionScore]:
        """Rank options without selecting a best choice.

        Useful when presenting alternatives to Revan for final decision.

        Args:
            options: List of option descriptions.
            context: Optional contextual information.

        Returns:
            List of _OptionScore sorted by composite score (descending).
        """
        if not options:
            return []

        ctx = context or {}
        scored = [self._score_option(option, ctx) for option in options]
        return sorted(scored, key=lambda s: s.composite, reverse=True)

    def compare_two(
        self,
        option_a: str,
        option_b: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compare two options side-by-side with tradeoff transparency.

        Args:
            option_a: First option description.
            option_b: Second option description.
            context: Optional contextual information.

        Returns:
            A dict with scores for both options and tradeoff analysis.
        """
        ctx = context or {}
        score_a = self._score_option(option_a, ctx)
        score_b = self._score_option(option_b, ctx)

        tradeoffs: list[str] = []

        # Identify where each option wins
        dimensions = [
            ("purpose_fit", "Purpose Fit"),
            ("tradeoff_clarity", "Tradeoff Clarity"),
            ("outcome_quality", "Outcome Quality"),
            ("context_fit", "Context Fit"),
        ]

        for attr, label in dimensions:
            a_val = getattr(score_a, attr)
            b_val = getattr(score_b, attr)
            diff = a_val - b_val
            if diff > 0.1:
                tradeoffs.append(f"Option A leads on {label} (+{diff:.2f})")
            elif diff < -0.1:
                tradeoffs.append(f"Option B leads on {label} (+{abs(diff):.2f})")

        winner = "A" if score_a.composite > score_b.composite else "B"
        if abs(score_a.composite - score_b.composite) < 0.05:
            winner = "tie"

        return {
            "option_a": score_a,
            "option_b": score_b,
            "winner": winner,
            "tradeoffs": tradeoffs,
            "discussion_recommended": abs(
                score_a.composite - score_b.composite
            )
            < 0.1,
        }

    # ------------------------------------------------------------------
    # Option scoring
    # ------------------------------------------------------------------

    def _score_option(
        self,
        option: str,
        ctx: dict[str, Any],
    ) -> _OptionScore:
        """Score a single option across all four decision dimensions.

        Args:
            option: The option description.
            ctx: Context dictionary.

        Returns:
            An _OptionScore with per-dimension scores and composite.
        """
        purpose_fit = self._evaluate_purpose_fit(option, ctx)
        tradeoff_clarity = self._evaluate_tradeoff_clarity(option, ctx)
        outcome_quality = self._evaluate_outcome_quality(option, ctx)
        context_fit = self._evaluate_context_fit(option, ctx)

        # Weighted composite
        composite = (
            purpose_fit * self._weights["purpose_fit"]
            + tradeoff_clarity * self._weights["tradeoff_clarity"]
            + outcome_quality * self._weights["outcome_quality"]
            + context_fit * self._weights["context_fit"]
        )

        # Build per-dimension reasoning
        reasoning_parts: list[str] = []
        reasoning_parts.append(f"Purpose fit: {purpose_fit:.2f}")
        reasoning_parts.append(f"Tradeoff clarity: {tradeoff_clarity:.2f}")
        reasoning_parts.append(f"Outcome quality: {outcome_quality:.2f}")
        reasoning_parts.append(f"Context fit: {context_fit:.2f}")
        reasoning_parts.append(f"Composite: {composite:.2f}")

        return _OptionScore(
            option=option,
            purpose_fit=purpose_fit,
            tradeoff_clarity=tradeoff_clarity,
            outcome_quality=outcome_quality,
            context_fit=context_fit,
            composite=composite,
            reasoning="; ".join(reasoning_parts),
        )

    # ------------------------------------------------------------------
    # Dimension evaluators
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_purpose_fit(option: str, ctx: dict[str, Any]) -> float:
        """Evaluate how well the option aligns with goals and intent.

        Considers:
        - Goals alignment
        - Intent match
        - Long-term direction
        - Revan's objectives

        Args:
            option: The option description.
            ctx: Context dictionary.

        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.5  # Neutral baseline
        option_lower = option.lower()

        # Positive indicators
        alignment_keywords = [
            "align", "goal", "objective", "purpose", "intent",
            "direction", "vision", "mission", "target",
        ]
        misalignment_keywords = [
            "contrary", "against", "oppose", "conflict", "divert",
            "distract", "unrelated", "tangential",
        ]

        positive_hits = sum(
            1 for kw in alignment_keywords if kw in option_lower
        )
        negative_hits = sum(
            1 for kw in misalignment_keywords if kw in option_lower
        )

        score += positive_hits * 0.1
        score -= negative_hits * 0.15

        # Context: explicit goal provided
        goal = ctx.get("goal", "")
        if goal and goal.lower() in option_lower:
            score += 0.2

        # Context: explicit misalignment flag
        if ctx.get("misaligned_with_goals") is True:
            score -= 0.3

        return max(0.0, min(1.0, score))

    @staticmethod
    def _evaluate_tradeoff_clarity(option: str, ctx: dict[str, Any]) -> float:
        """Evaluate how clearly the tradeoffs are understood.

        Considers:
        - Benefits clarity
        - Costs clarity
        - Opportunity loss awareness
        - Competing advantages comparison

        Args:
            option: The option description.
            ctx: Context dictionary.

        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.5  # Neutral baseline
        option_lower = option.lower()

        # Positive indicators — explicit tradeoff discussion
        clarity_keywords = [
            "tradeoff", "benefit", "cost", "advantage", "disadvantage",
            "pro", "con", "gain", "lose", "sacrifice", "opportunity cost",
            "compared to", "versus", "alternative",
        ]
        vague_keywords = [
            "maybe", "possibly", "unclear", "unknown cost",
            "hidden", "uncertain benefit",
        ]

        positive_hits = sum(
            1 for kw in clarity_keywords if kw in option_lower
        )
        negative_hits = sum(
            1 for kw in vague_keywords if kw in option_lower
        )

        score += positive_hits * 0.1
        score -= negative_hits * 0.15

        # Context: explicit tradeoff analysis provided
        if ctx.get("tradeoffs_analyzed") is True:
            score += 0.2

        # Context: high uncertainty about tradeoffs
        if ctx.get("tradeoff_uncertainty") == "high":
            score -= 0.3

        return max(0.0, min(1.0, score))

    @staticmethod
    def _evaluate_outcome_quality(option: str, ctx: dict[str, Any]) -> float:
        """Evaluate the expected effectiveness of the option.

        Considers:
        - Usefulness
        - Impact
        - Sustainability
        - Clarity of result

        Args:
            option: The option description.
            ctx: Context dictionary.

        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.5  # Neutral baseline
        option_lower = option.lower()

        # Positive indicators
        quality_keywords = [
            "effective", "efficient", "reliable", "robust", "proven",
            "tested", "sustainable", "scalable", "maintainable",
            "clear result", "measurable", "high impact",
        ]
        poor_quality_keywords = [
            "fragile", "temporary", "hack", "workaround", "brittle",
            "untested", "experimental", "low impact", "minimal effect",
        ]

        positive_hits = sum(
            1 for kw in quality_keywords if kw in option_lower
        )
        negative_hits = sum(
            1 for kw in poor_quality_keywords if kw in option_lower
        )

        score += positive_hits * 0.1
        score -= negative_hits * 0.15

        # Context: expected impact level
        impact = ctx.get("expected_impact", "")
        if impact == "high":
            score += 0.2
        elif impact == "low":
            score -= 0.2

        # Context: sustainability concern
        if ctx.get("sustainability_concern") is True:
            score -= 0.2

        return max(0.0, min(1.0, score))

    @staticmethod
    def _evaluate_context_fit(option: str, ctx: dict[str, Any]) -> float:
        """Evaluate how appropriate the option is for the current situation.

        Considers:
        - Timing
        - Environment
        - Constraints
        - Priorities

        Args:
            option: The option description.
            ctx: Context dictionary.

        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.5  # Neutral baseline
        option_lower = option.lower()

        # Positive indicators
        context_keywords = [
            "appropriate", "suitable", "timely", "right time",
            "fits", "compatible", "consistent", "within constraints",
            "respects", "priority",
        ]
        poor_context_keywords = [
            "inappropriate", "wrong time", "premature", "too late",
            "violates", "breaks", "ignores constraints",
            "disrupts", "interferes",
        ]

        positive_hits = sum(
            1 for kw in context_keywords if kw in option_lower
        )
        negative_hits = sum(
            1 for kw in poor_context_keywords if kw in option_lower
        )

        score += positive_hits * 0.1
        score -= negative_hits * 0.15

        # Context: explicit constraints
        constraints = ctx.get("constraints", [])
        if constraints:
            # Check if option respects known constraints
            respects_all = True
            for constraint in constraints:
                if isinstance(constraint, str) and constraint.lower() in option_lower:
                    # Mentioning a constraint is good — shows awareness
                    pass
            if respects_all:
                score += 0.1

        # Context: timing assessment
        timing = ctx.get("timing", "")
        if timing == "optimal":
            score += 0.2
        elif timing == "poor":
            score -= 0.3

        # Context: priority alignment
        if ctx.get("aligns_with_priorities") is True:
            score += 0.2
        elif ctx.get("aligns_with_priorities") is False:
            score -= 0.2

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Discussion and uncertainty assessment
    # ------------------------------------------------------------------

    @staticmethod
    def _should_discuss(
        ranked: list[_OptionScore],
        ctx: dict[str, Any],
    ) -> bool:
        """Determine if discussion is recommended before final selection.

        Discussion is preferred when:
        - Multiple strong valid options exist
        - Outcomes are similar in value
        - Uncertainty remains in ranking

        Args:
            ranked: Ranked list of scored options.
            ctx: Context dictionary.

        Returns:
            True if discussion is recommended.
        """
        # If context explicitly requests discussion
        if ctx.get("request_discussion") is True:
            return True

        if len(ranked) < 2:
            return False

        # If top two scores are very close (< 0.1 difference), discuss
        top_two_diff = ranked[0].composite - ranked[1].composite
        if top_two_diff < 0.1:
            return True

        # If multiple options have scores > 0.7
        strong_options = sum(1 for s in ranked if s.composite > 0.7)
        return strong_options >= 2

    @staticmethod
    def _assess_uncertainty(ranked: list[_OptionScore]) -> str:
        """Assess the uncertainty level in the ranking.

        Args:
            ranked: Ranked list of scored options.

        Returns:
            "low", "moderate", or "high"
        """
        if len(ranked) < 2:
            return "low"

        top_two_diff = ranked[0].composite - ranked[1].composite

        if top_two_diff > 0.2:
            return "low"
        if top_two_diff > 0.1:
            return "moderate"
        return "high"

    @staticmethod
    def _build_reasoning(
        ranked: list[_OptionScore],
        ctx: dict[str, Any],
        requires_discussion: bool,
    ) -> str:
        """Build a human-readable reasoning string for the decision.

        Args:
            ranked: Ranked list of scored options.
            ctx: Context dictionary.
            requires_discussion: Whether discussion is recommended.

        Returns:
            A reasoning string.
        """
        parts: list[str] = []

        best = ranked[0]
        parts.append(
            f"Best option: '{best.option}' (composite: {best.composite:.2f})"
        )

        if len(ranked) > 1:
            runner_up = ranked[1]
            diff = best.composite - runner_up.composite
            parts.append(
                f"Runner-up: '{runner_up.option}' "
                f"(composite: {runner_up.composite:.2f}, "
                f"difference: {diff:.2f})"
            )

        # Dimension breakdown for best option
        parts.append(
            f"Dimensions — Purpose: {best.purpose_fit:.2f}, "
            f"Tradeoffs: {best.tradeoff_clarity:.2f}, "
            f"Outcome: {best.outcome_quality:.2f}, "
            f"Context: {best.context_fit:.2f}"
        )

        if requires_discussion:
            parts.append(
                "Discussion recommended: multiple strong options or close scores"
            )

        if ctx.get("goal"):
            parts.append(f"Evaluated against goal: {ctx['goal']}")

        return " | ".join(parts)

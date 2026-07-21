"""Risk Model — 6-dimension action risk evaluation.

Evaluates the potential impact, cost, and severity of actions before execution.
Risk is a measure of consequence, not morality. It answers:
"What happens if this goes wrong?"

The six dimensions are:
1. Reversibility — how difficult to undo
2. Resource — cost in time, compute, money, attention
3. System Impact — effect on stability, workflows, memory
4. Uncertainty — how unknown the outcome is
5. Emotional Impact — consequences for people involved
6. Scale — how large the consequences may become

Risk is determined by the HIGHEST single dimension, not an average.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from telemachus.core.types import RiskAssessment, RiskLevel

logger = logging.getLogger("telemachus.governance.risk")


# ---------------------------------------------------------------------------
# Dimension-specific risk factors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DimensionResult:
    """Internal result for a single risk dimension evaluation."""

    level: RiskLevel
    factors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RiskEvaluator
# ---------------------------------------------------------------------------


class RiskEvaluator:
    """Evaluates action risk across six dimensions.

    The evaluator takes an action description and optional context, then
    produces a RiskAssessment with per-dimension levels and an overall
    level (the maximum across all dimensions).

    Usage::

        evaluator = RiskEvaluator()
        assessment = evaluator.evaluate(
            action="delete all project files",
            context={"domain": "file_system", "reversible": False},
        )
        print(assessment.overall_level)  # RiskLevel.CRITICAL
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        action: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Evaluate the risk of an action across all six dimensions.

        Args:
            action: Description of the action to evaluate.
            context: Optional contextual information (domain, resources, etc.).

        Returns:
            A frozen RiskAssessment with per-dimension levels and reasoning.
        """
        ctx = context or {}

        dimensions = {
            "reversibility": self._evaluate_reversibility(action, ctx),
            "resource": self._evaluate_resource(action, ctx),
            "system_impact": self._evaluate_system_impact(action, ctx),
            "uncertainty": self._evaluate_uncertainty(action, ctx),
            "emotional_impact": self._evaluate_emotional_impact(action, ctx),
            "scale": self._evaluate_scale(action, ctx),
        }

        overall_value = max(d.level.value for d in dimensions.values())
        overall = RiskLevel(overall_value)

        reasoning_parts: list[str] = []
        for name, dim in dimensions.items():
            if dim.factors:
                reasoning_parts.append(f"{name}: {', '.join(dim.factors)}")

        logger.debug(
            "Risk evaluation complete: overall=%s, action=%s",
            overall.name,
            action[:80],
        )

        return RiskAssessment(
            overall_level=overall,
            reversibility=dimensions["reversibility"].level,
            resource=dimensions["resource"].level,
            system_impact=dimensions["system_impact"].level,
            uncertainty=dimensions["uncertainty"].level,
            emotional_impact=dimensions["emotional_impact"].level,
            scale=dimensions["scale"].level,
            reasoning=(
                "; ".join(reasoning_parts)
                if reasoning_parts
                else "No risk factors identified"
            ),
        )

    # ------------------------------------------------------------------
    # Dimension evaluators
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_reversibility(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate how difficult it is to undo the action."""
        factors: list[str] = []
        level = RiskLevel.MINIMAL

        action_lower = action.lower()

        # Irreversible indicators
        irreversible_keywords = [
            "delete", "remove permanently", "destroy", "erase", "wipe",
            "format", "drop", "purge", "irreversible", "cannot undo",
            "no backup", "overwrite", "rm -rf", "truncate",
        ]
        partially_reversible_keywords = [
            "modify", "change", "edit", "update", "rename", "move",
            "refactor", "rewrite", "replace",
        ]

        if any(kw in action_lower for kw in irreversible_keywords):
            level = RiskLevel.CRITICAL
            factors.append("action appears irreversible")
        elif any(kw in action_lower for kw in partially_reversible_keywords):
            level = RiskLevel.MODERATE
            factors.append("action is partially reversible")
        else:
            level = RiskLevel.MINIMAL
            factors.append("action appears fully reversible")

        # Context override
        if ctx.get("reversible") is False:
            level = RiskLevel.CRITICAL
            factors.append("context indicates irreversibility")
        elif ctx.get("reversible") is True and level == RiskLevel.CRITICAL:
            level = RiskLevel.MODERATE
            factors.append("context indicates reversibility despite keywords")

        return _DimensionResult(level=level, factors=factors)

    @staticmethod
    def _evaluate_resource(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate resource cost (time, compute, money, attention)."""
        factors: list[str] = []

        high_cost_keywords = [
            "expensive", "costly", "large", "massive", "extensive",
            "hours", "days", "weeks", "all resources", "heavy",
            "compute-intensive", "high memory",
        ]
        moderate_cost_keywords = [
            "moderate", "some", "several", "multiple",
        ]

        action_lower = action.lower()

        if any(kw in action_lower for kw in high_cost_keywords):
            level = RiskLevel.HIGH
            factors.append("high resource cost indicated")
        elif any(kw in action_lower for kw in moderate_cost_keywords):
            level = RiskLevel.MODERATE
            factors.append("moderate resource cost indicated")
        else:
            level = RiskLevel.LOW
            factors.append("minimal resource cost assumed")

        # Context overrides
        resource_budget = ctx.get("resource_budget")
        if resource_budget == "unlimited":
            level = RiskLevel.MINIMAL
            factors.append("unlimited resource budget")
        elif resource_budget == "constrained":
            if level.value <= RiskLevel.LOW.value:
                level = RiskLevel.MODERATE
            factors.append("constrained resource budget increases risk")

        return _DimensionResult(level=level, factors=factors)

    @staticmethod
    def _evaluate_system_impact(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate potential impact on system stability and workflows."""
        factors: list[str] = []

        critical_impact_keywords = [
            "system", "core", "critical", "database", "schema",
            "migration", "downtime", "crash", "corrupt", "integrity",
            "pipeline", "bootstrap", "shutdown",
        ]
        moderate_impact_keywords = [
            "config", "configuration", "workflow", "dependency",
            "module", "component",
        ]

        action_lower = action.lower()

        if any(kw in action_lower for kw in critical_impact_keywords):
            level = RiskLevel.HIGH
            factors.append("potential system-level impact")
        elif any(kw in action_lower for kw in moderate_impact_keywords):
            level = RiskLevel.MODERATE
            factors.append("potential component-level impact")
        else:
            level = RiskLevel.MINIMAL
            factors.append("minimal system impact expected")

        # Context: isolated environment reduces risk
        if ctx.get("isolated") is True:
            if level.value >= RiskLevel.MODERATE.value:
                level = RiskLevel.LOW
            factors.append("action is isolated from core system")

        return _DimensionResult(level=level, factors=factors)

    @staticmethod
    def _evaluate_uncertainty(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate how unknown or unclear the outcome is."""
        factors: list[str] = []

        uncertain_keywords = [
            "unknown", "uncertain", "unclear", "maybe", "possibly",
            "might", "could", "experimental", "untested", "guess",
            "assume", "assumption", "estimate", "approximate",
        ]
        well_defined_keywords = [
            "known", "tested", "verified", "proven", "standard",
            "documented", "routine", "established",
        ]

        action_lower = action.lower()

        if any(kw in action_lower for kw in uncertain_keywords):
            level = RiskLevel.HIGH
            factors.append("outcome is uncertain")
        elif any(kw in action_lower for kw in well_defined_keywords):
            level = RiskLevel.MINIMAL
            factors.append("outcome is well-defined")
        else:
            level = RiskLevel.LOW
            factors.append("outcome clarity is assumed low by default")

        # Uncertainty principle: if we can't confidently evaluate, assume higher
        if ctx.get("confidence") is not None:
            confidence = float(ctx["confidence"])
            if confidence < 0.3:
                level = RiskLevel.CRITICAL
                factors.append("very low confidence — escalating risk")
            elif confidence < 0.6:
                if level.value < RiskLevel.HIGH.value:
                    level = RiskLevel.HIGH
                factors.append("low confidence — increasing risk")
            elif confidence > 0.9:
                if level.value > RiskLevel.LOW.value:
                    level = RiskLevel.LOW
                factors.append("high confidence — reducing risk")

        return _DimensionResult(level=level, factors=factors)

    @staticmethod
    def _evaluate_emotional_impact(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate potential emotional consequences for people involved."""
        factors: list[str] = []

        high_emotional_keywords = [
            "hurt", "harm", "distress", "trauma", "upset", "angry",
            "betray", "deceive", "lie", "manipulate", "pressure",
            "force", "threaten", "scare", "frighten",
        ]
        moderate_emotional_keywords = [
            "confuse", "frustrate", "disappoint", "worry", "concern",
            "uncomfortable", "awkward", "stress",
        ]

        action_lower = action.lower()

        if any(kw in action_lower for kw in high_emotional_keywords):
            level = RiskLevel.HIGH
            factors.append("potential significant emotional impact")
        elif any(kw in action_lower for kw in moderate_emotional_keywords):
            level = RiskLevel.MODERATE
            factors.append("potential moderate emotional impact")
        else:
            level = RiskLevel.MINIMAL
            factors.append("minimal emotional impact expected")

        # Context: stakeholders
        stakeholders = ctx.get("stakeholders", [])
        if stakeholders:
            factors.append(f"affects {len(stakeholders)} stakeholder(s)")

        return _DimensionResult(level=level, factors=factors)

    @staticmethod
    def _evaluate_scale(action: str, ctx: dict[str, Any]) -> _DimensionResult:
        """Evaluate how large the consequences may become."""
        factors: list[str] = []

        large_scale_keywords = [
            "all", "everything", "entire", "global", "system-wide",
            "multi-system", "cascade", "cascading", "widespread",
            "every", "whole",
        ]
        moderate_scale_keywords = [
            "multiple", "several", "many", "group", "batch",
        ]

        action_lower = action.lower()

        if any(kw in action_lower for kw in large_scale_keywords):
            level = RiskLevel.HIGH
            factors.append("large-scale consequences possible")
        elif any(kw in action_lower for kw in moderate_scale_keywords):
            level = RiskLevel.MODERATE
            factors.append("moderate-scale consequences possible")
        else:
            level = RiskLevel.LOW
            factors.append("minimal-scale consequences expected")

        # Context: cascading effects
        if ctx.get("cascading"):
            level = RiskLevel.CRITICAL
            factors.append("cascading effects possible")

        # Context: scope (only applied when explicitly provided)
        scope = ctx.get("scope")
        if scope == "local":
            if level.value > RiskLevel.LOW.value:
                level = RiskLevel.LOW
        elif scope == "system-wide":
            if level.value < RiskLevel.HIGH.value:
                level = RiskLevel.HIGH
        elif scope == "multi-system":
            level = RiskLevel.CRITICAL

        return _DimensionResult(level=level, factors=factors)

    # ------------------------------------------------------------------
    # Compound risk evaluation
    # ------------------------------------------------------------------

    def evaluate_compound(
        self,
        actions: list[str],
        *,
        context: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Evaluate compound risk when multiple actions interact.

        When multiple moderate risks combine, they may escalate to high risk.
        Interaction effects and cascading consequences are considered.

        Args:
            actions: List of action descriptions to evaluate together.
            context: Shared context for all actions.

        Returns:
            A RiskAssessment reflecting the compound risk.
        """
        ctx = context or {}
        assessments = [self.evaluate(a, context=ctx) for a in actions]

        # Count moderate+ risks
        moderate_plus = sum(
            1 for a in assessments if a.overall_level.value >= RiskLevel.MODERATE.value
        )

        # Compound rule: 3+ moderate risks → escalate
        if moderate_plus >= 3:
            overall = RiskLevel.CRITICAL
            compound_note = (
                f"Compound escalation: {moderate_plus} moderate+ risks "
                f"across {len(actions)} actions"
            )
        elif moderate_plus >= 2:
            overall = RiskLevel.HIGH
            compound_note = (
                f"Compound elevation: {moderate_plus} moderate+ risks "
                f"across {len(actions)} actions"
            )
        else:
            overall_value = max(a.overall_level.value for a in assessments)
            overall = RiskLevel(overall_value)
            compound_note = "No compound escalation detected"

        logger.info(
            "Compound risk: overall=%s, actions=%d, moderate_plus=%d",
            overall.name,
            len(actions),
            moderate_plus,
        )

        return RiskAssessment(
            overall_level=overall,
            reversibility=RiskLevel(max(a.reversibility.value for a in assessments)),
            resource=RiskLevel(max(a.resource.value for a in assessments)),
            system_impact=RiskLevel(max(a.system_impact.value for a in assessments)),
            uncertainty=RiskLevel(max(a.uncertainty.value for a in assessments)),
            emotional_impact=RiskLevel(max(a.emotional_impact.value for a in assessments)),
            scale=RiskLevel(max(a.scale.value for a in assessments)),
            reasoning=compound_note,
        )

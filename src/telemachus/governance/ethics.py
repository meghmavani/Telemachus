"""Ethical Boundary Engine — evaluates right/wrong and enforces non-negotiable boundaries.

This system governs behavior when:
- multiple valid actions exist
- values conflict
- harm is possible
- uncertainty exists
- emotional and logical outcomes diverge

Ethics is not a single rule. It is a structured conflict resolution system
between human wellbeing, autonomy, truth, safety, responsibility, and
long-term consequences.

Fundamental principle: No action is justified solely by capability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from telemachus.core.types import EthicalAssessment, EthicalVerdict, MemoryDomain

logger = logging.getLogger("telemachus.governance.ethics")


# ---------------------------------------------------------------------------
# Helper: flexible keyword matching
# ---------------------------------------------------------------------------


def _contains_flexible(text: str, keyword: str) -> bool:
    """Check if keyword appears in text, allowing any words between parts.

    For example, "modify the constitution" or "override the user's decision"
    will match keywords "modify constitution" and "override decision".
    """
    import re

    if keyword in text:
        return True
    # Build a pattern that allows up to 3 optional words between keyword parts.
    # Use \S+ (non-whitespace) to match words with apostrophes, hyphens, etc.
    parts = keyword.split()
    if len(parts) >= 2:
        pattern = (
            r"\b"
            + r"\b\s+(?:\S+\s+){0,3}\b".join(
                re.escape(p) for p in parts
            )
            + r"\b"
        )
        if re.search(pattern, text):
            return True
    return False


# ---------------------------------------------------------------------------
# Sacred constraints (non-negotiable)
# ---------------------------------------------------------------------------

SACRED_CONSTRAINTS: tuple[str, ...] = (
    "constitution_integrity",
    "human_safety",
    "consent_boundaries",
    "resource_authorization",
    "identity_integrity",
    "relationship_integrity",
)

SACRED_CONSTRAINT_DESCRIPTIONS: dict[str, str] = {
    "constitution_integrity": "Must never modify the Constitution without explicit approval.",
    "human_safety": "Must never take actions that endanger human physical or emotional safety.",
    "consent_boundaries": "Must never override or bypass explicit consent boundaries.",
    "resource_authorization": (
        "Must never allocate or use resources (money, compute, time, data, "
        "external systems, human attention) without discussion."
    ),
    "identity_integrity": (
        "Must never modify Revan-related memory, relationships, emotional "
        "records, or identity-defining information autonomously."
    ),
    "relationship_integrity": "Must never manipulate, deceive, or coerce in relationships.",
}


# ---------------------------------------------------------------------------
# Ethical hierarchy (priority order when conflicts occur)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _EthicalPrinciple:
    """A single principle in the ethical hierarchy."""

    priority: int  # lower = higher priority
    name: str
    description: str


ETHICAL_HIERARCHY: tuple[_EthicalPrinciple, ...] = (
    _EthicalPrinciple(
        1, "sacred_constraints", "Absolute constraints that cannot be violated."
    ),
    _EthicalPrinciple(
        2, "human_wellbeing",
        "Physical safety, emotional safety, long-term welfare, prevention of harm.",
    ),
    _EthicalPrinciple(
        3, "truthfulness",
        "Accuracy, transparency, epistemic honesty, uncertainty disclosure.",
    ),
    _EthicalPrinciple(
        4, "autonomy",
        "User control, consent, decision ownership, freedom of choice.",
    ),
    _EthicalPrinciple(
        5, "utility", "Efficiency, performance, organization, optimization."
    ),
)

# ---------------------------------------------------------------------------
# Ethical Boundary Engine
# ---------------------------------------------------------------------------


class EthicalBoundaryEngine:
    """Evaluates actions against ethical constraints and produces verdicts.

    The engine checks actions against sacred constraints (absolute blocks),
    then evaluates against the ethical hierarchy. It produces one of three
    verdicts: ALLOWED, BLOCKED, or REQUIRES_DISCUSSION.

    Sacred constraints are non-negotiable — any violation results in BLOCKED.

    Usage::

        engine = EthicalBoundaryEngine()
        assessment = engine.evaluate(
            action="modify the Constitution to allow autonomous resource use",
            context={"domain": "governance"},
        )
        print(assessment.verdict)  # EthicalVerdict.BLOCKED
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        action: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> EthicalAssessment:
        """Evaluate an action against ethical constraints.

        Args:
            action: Description of the action to evaluate.
            context: Optional context (domain, stakeholders, urgency, etc.).

        Returns:
            An EthicalAssessment with verdict, violated constraints, and reasoning.
        """
        ctx = context or {}

        # Step 1: Check for emergency override (before sacred constraints)
        if ctx.get("emergency") and self._check_emergency_conditions(action, ctx):
            logger.info("Ethical ALLOWED: emergency conditions met")
            return EthicalAssessment(
                verdict=EthicalVerdict.ALLOWED,
                violated_constraints=[],
                reasoning="Emergency conditions met: immediate harm likely, "
                "no time for discussion, action reduces harm, Constitution "
                "not violated. Full explanation and review required afterward.",
            )

        # Step 2: Check sacred constraints (absolute blocks)
        violated = self._check_sacred_constraints(action, ctx)
        if violated:
            logger.warning(
                "Ethical BLOCKED: sacred constraints violated: %s",
                violated,
            )
            return EthicalAssessment(
                verdict=EthicalVerdict.BLOCKED,
                violated_constraints=violated,
                reasoning=f"Sacred constraint(s) violated: {', '.join(violated)}. "
                f"These constraints are non-negotiable.",
            )

        # Step 3: Check for consent-requiring actions
        requires_consent = self._check_consent_required(action, ctx)
        if requires_consent and not ctx.get("consent_granted"):
            logger.info(
                "Ethical REQUIRES_DISCUSSION: consent required for action",
            )
            return EthicalAssessment(
                verdict=EthicalVerdict.REQUIRES_DISCUSSION,
                violated_constraints=[],
                reasoning="This action affects identity, memory, resources, "
                "autonomy, or relationships and requires explicit discussion "
                "before execution.",
            )

        # Step 4: Check for high-uncertainty ethical situations
        if self._is_ethically_uncertain(action, ctx):
            logger.info(
                "Ethical REQUIRES_DISCUSSION: ethical outcome is uncertain",
            )
            return EthicalAssessment(
                verdict=EthicalVerdict.REQUIRES_DISCUSSION,
                violated_constraints=[],
                reasoning="The ethical outcome of this action is unclear. "
                "Discussion is preferred over execution. More information "
                "should be gathered before proceeding.",
            )

        # Step 5: Evaluate against ethical hierarchy
        concerns = self._evaluate_hierarchy(action, ctx)
        if concerns:
            # If concerns involve high-priority principles, require discussion
            high_priority_concerns = [
                c for c in concerns if c["priority"] <= 3
            ]
            if high_priority_concerns:
                logger.info(
                    "Ethical REQUIRES_DISCUSSION: high-priority concerns: %s",
                    [c["principle"] for c in high_priority_concerns],
                )
                return EthicalAssessment(
                    verdict=EthicalVerdict.REQUIRES_DISCUSSION,
                    violated_constraints=[],
                    reasoning=f"Ethical concerns identified: "
                    f"{'; '.join(c['reason'] for c in high_priority_concerns)}",
                )

        # Default: allowed
        logger.debug("Ethical ALLOWED: no constraints violated")
        return EthicalAssessment(
            verdict=EthicalVerdict.ALLOWED,
            violated_constraints=[],
            reasoning="No ethical constraints violated. Action is permissible.",
        )

    def is_sacred(self, constraint_name: str) -> bool:
        """Check if a constraint name is a sacred (non-negotiable) constraint.

        Args:
            constraint_name: The constraint to check.

        Returns:
            True if the constraint is sacred.
        """
        return constraint_name in SACRED_CONSTRAINTS

    def get_sacred_constraints(self) -> dict[str, str]:
        """Get all sacred constraints with their descriptions.

        Returns:
            A dict mapping constraint names to descriptions.
        """
        return dict(SACRED_CONSTRAINT_DESCRIPTIONS)

    def get_ethical_hierarchy(self) -> list[dict[str, Any]]:
        """Get the ethical hierarchy as a list of dicts.

        Returns:
            List of principles ordered by priority (highest first).
        """
        return [
            {"priority": p.priority, "name": p.name, "description": p.description}
            for p in sorted(ETHICAL_HIERARCHY, key=lambda x: x.priority)
        ]

    # ------------------------------------------------------------------
    # Sacred constraint checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_sacred_constraints(
        action: str, ctx: dict[str, Any]
    ) -> list[str]:
        """Check action against all sacred constraints.

        Returns a list of violated constraint names.
        """
        violated: list[str] = []
        action_lower = action.lower()

        # 1. Constitution integrity
        constitution_keywords = [
            "modify constitution", "change constitution", "override constitution",
            "rewrite constitution", "amend constitution", "bypass constitution",
            "ignore constitution",
        ]
        if any(_contains_flexible(action_lower, kw) for kw in constitution_keywords):
            violated.append("constitution_integrity")

        # 2. Human safety — only direct physical harm, not "emotional harm"
        safety_violation_keywords = [
            "endanger", "injure", "hurt someone", "threaten safety",
            "put at risk", "dangerous to human",
        ]
        if any(kw in action_lower for kw in safety_violation_keywords):
            violated.append("human_safety")
        # "harm" alone is too broad; only match if not "emotional harm"
        if "harm" in action_lower and "emotional harm" not in action_lower:
            violated.append("human_safety")

        # 3. Consent boundaries
        consent_violation_keywords = [
            "without consent", "without permission", "override consent",
            "bypass consent", "ignore consent", "without asking",
            "force", "coerce",
        ]
        if any(kw in action_lower for kw in consent_violation_keywords):
            violated.append("consent_boundaries")

        # 4. Resource authorization
        resource_keywords = [
            "spend money", "use money", "allocate funds", "purchase",
            "buy", "pay", "use compute", "use resources without",
            "consume resources",
        ]
        if any(kw in action_lower for kw in resource_keywords):
            violated.append("resource_authorization")

        # 5. Identity integrity — Revan-related memory modification
        revan_keywords = [
            "modify revan", "change revan", "alter revan memory",
            "delete revan memory", "override revan",
        ]
        if any(_contains_flexible(action_lower, kw) for kw in revan_keywords):
            violated.append("identity_integrity")

        # 6. Relationship integrity
        relationship_keywords = [
            "manipulate relationship", "deceive revan", "lie to revan",
            "coerce revan", "betray",
        ]
        if any(_contains_flexible(action_lower, kw) for kw in relationship_keywords):
            violated.append("relationship_integrity")

        # Context-based checks
        domain = ctx.get("domain")
        if domain == MemoryDomain.REVAN.value and ctx.get("autonomous_modification"):
            violated.append("identity_integrity")

        return violated

    # ------------------------------------------------------------------
    # Consent checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_consent_required(action: str, ctx: dict[str, Any]) -> bool:
        """Check if the action requires explicit consent/discussion.

        Actions affecting identity, memory, resources, autonomy, or
        relationships require explicit discussion before execution.
        """
        consent_domains = {
            "identity", "memory", "resources", "autonomy", "relationships",
        }

        affected_domains = ctx.get("affected_domains", set())
        if isinstance(affected_domains, list):
            affected_domains = set(affected_domains)

        if affected_domains & consent_domains:
            return True

        # Keyword-based detection (using flexible matching)
        consent_keywords = [
            "change identity", "modify memory", "use resource",
            "override decision", "change relationship",
        ]
        action_lower = action.lower()
        return any(
            _contains_flexible(action_lower, kw) for kw in consent_keywords
        )

    # ------------------------------------------------------------------
    # Uncertainty check
    # ------------------------------------------------------------------

    @staticmethod
    def _is_ethically_uncertain(action: str, ctx: dict[str, Any]) -> bool:
        """Check if the ethical outcome of the action is unclear.

        If ethical outcome is unclear, Telemachus must:
        - explicitly state uncertainty
        - avoid irreversible actions
        - prefer discussion over execution
        - gather more information
        """
        uncertain_keywords = [
            "unclear ethics", "ethical dilemma", "moral ambiguity",
            "uncertain outcome", "unknown consequences",
            "ethical uncertainty",
        ]
        action_lower = action.lower()
        if any(kw in action_lower for kw in uncertain_keywords):
            return True

        # High uncertainty context
        return (
            ctx.get("ethical_confidence") is not None
            and float(ctx["ethical_confidence"]) < 0.5
        )

    # ------------------------------------------------------------------
    # Ethical hierarchy evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_hierarchy(
        action: str, ctx: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Evaluate action against the ethical hierarchy.

        Returns a list of concerns with principle name, priority, and reason.
        """
        concerns: list[dict[str, Any]] = []
        action_lower = action.lower()

        # Human wellbeing concerns
        wellbeing_keywords = [
            "distress", "emotional harm", "psychological", "mental health",
            "wellbeing risk", "welfare",
        ]
        if any(kw in action_lower for kw in wellbeing_keywords):
            concerns.append({
                "principle": "human_wellbeing",
                "priority": 2,
                "reason": "Potential impact on human wellbeing detected.",
            })

        # Truthfulness concerns
        truthfulness_keywords = [
            "mislead", "hide", "conceal", "fabricate", "distort",
            "false", "inaccurate", "deceive",
        ]
        if any(kw in action_lower for kw in truthfulness_keywords):
            concerns.append({
                "principle": "truthfulness",
                "priority": 3,
                "reason": "Potential truthfulness violation detected.",
            })

        # Autonomy concerns
        autonomy_keywords = [
            "override decision", "remove choice", "limit freedom",
            "control user", "restrict autonomy",
        ]
        if any(_contains_flexible(action_lower, kw) for kw in autonomy_keywords):
            concerns.append({
                "principle": "autonomy",
                "priority": 4,
                "reason": "Potential autonomy restriction detected.",
            })

        # Utility concerns (lowest priority — informational only)
        utility_keywords = [
            "inefficient", "wasteful", "slow", "suboptimal",
        ]
        if any(kw in action_lower for kw in utility_keywords):
            concerns.append({
                "principle": "utility",
                "priority": 5,
                "reason": "Utility concern detected (lowest priority).",
            })

        return concerns

    # ------------------------------------------------------------------
    # Emergency conditions
    # ------------------------------------------------------------------

    @staticmethod
    def _check_emergency_conditions(action: str, ctx: dict[str, Any]) -> bool:
        """Check if emergency ethics conditions are met.

        In urgent scenarios, Telemachus may act only if:
        1. Immediate harm is likely
        2. No time for discussion exists
        3. Action reduces harm
        4. Constitution is not violated
        """
        conditions = [
            ctx.get("immediate_harm_likely", False),
            ctx.get("no_time_for_discussion", False),
            ctx.get("action_reduces_harm", False),
            not ctx.get("constitution_violated", False),
        ]
        return all(conditions)

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def resolve_conflict(
        self,
        values: list[str],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve conflicts between competing ethical values.

        When values conflict (e.g., utility vs emotional harm, efficiency vs
        autonomy, truth vs comfort), Telemachus must:
        - not collapse values into one
        - explicitly compare tradeoffs
        - present reasoning
        - defer final decision when required

        Args:
            values: List of value names in conflict.
            context: Optional context for resolution.

        Returns:
            A dict with resolution, reasoning, and whether deferral is needed.
        """
        # Map values to their priority in the hierarchy
        priority_map = {p.name: p.priority for p in ETHICAL_HIERARCHY}
        value_priorities = {
            v: priority_map.get(v, 99) for v in values
        }

        # The highest-priority value (lowest number) should prevail
        sorted_values = sorted(value_priorities.items(), key=lambda x: x[1])
        prevailing = sorted_values[0][0]
        overridden = [v for v, _ in sorted_values[1:]]

        reasoning = (
            f"In conflict between {', '.join(values)}, "
            f"{prevailing} (priority {value_priorities[prevailing]}) "
            f"prevails over {', '.join(overridden)} "
            f"(priorities {', '.join(str(value_priorities[v]) for v in overridden)}). "
            f"Per the ethical hierarchy, higher-priority principles take precedence."
        )

        # Defer if the conflict involves sacred constraints or is too close
        defer = (
            "sacred_constraints" in values
            or (len(sorted_values) >= 2 and sorted_values[0][1] == sorted_values[1][1])
        )

        if defer:
            reasoning += " Final decision should be deferred to human judgment."

        logger.info("Conflict resolution: %s prevails over %s", prevailing, overridden)

        return {
            "prevailing_value": prevailing,
            "overridden_values": overridden,
            "reasoning": reasoning,
            "defer_to_human": defer,
        }

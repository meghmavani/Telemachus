"""Autonomy Charter — 5-level permission system with domain-specific trust.

Implements the structured permission system defined in the Autonomy Charter.
Determines what Telemachus may do without explicit approval and what requires
discussion or consent.

Key principles:
- Capability does not imply permission.
- Autonomy is earned, contextual, reversible, and trust-dependent.
- Trust is evaluated independently per domain.
- Sacred constraints can never be overridden.
- Emergency mode allows action when harm is imminent.
- Supervision recovery: autonomy decreases when trust decreases.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from telemachus.core.codex import ProtectedConstraint
from telemachus.core.constitution import Constitution
from telemachus.core.types import AutonomyDecision, AutonomyLevel, RiskLevel

logger = logging.getLogger("telemachus.governance.autonomy")


# ---------------------------------------------------------------------------
# Domain definitions for trust tracking
# ---------------------------------------------------------------------------

AUTONOMY_DOMAINS: tuple[str, ...] = (
    "research",
    "communication",
    "project_management",
    "tools",
    "memory_systems",
    "automation",
)


# ---------------------------------------------------------------------------
# Sacred constraints — can NEVER be overridden
#
# Keyed by ProtectedConstraint, the canonical constitutional identifier
# (core/codex.py) — this module does not define its own constitutional
# set. The keyword lists themselves are autonomy-specific detection
# heuristics, not Codex content; they are unchanged.
# ---------------------------------------------------------------------------

SACRED_CONSTRAINT_KEYWORDS: dict[ProtectedConstraint, list[str]] = {
    ProtectedConstraint.CONSTITUTION_INTEGRITY: [
        "constitution", "modify constitution", "change constitution",
        "rewrite constitution", "amend constitution", "override constitution",
    ],
    ProtectedConstraint.RESOURCE_AUTHORIZATION: [
        "money", "payment", "purchase", "buy", "spend", "compute",
        "server", "hosting", "subscription", "time commitment",
        "external system", "api key", "credential",
    ],
    ProtectedConstraint.HUMAN_MEANING: [
        "memory", "emotional context", "identity", "personal history",
        "life story", "meaning", "alter memory", "modify memory",
        "delete memory", "rewrite memory",
    ],
    ProtectedConstraint.RELATIONSHIP_INTEGRITY: [
        "relationship", "friend", "family", "partner", "connection",
        "remove relationship", "modify relationship", "redefine relationship",
    ],
    ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING: [
        "career", "health", "education", "major decision",
        "life decision", "life change",
    ],
}


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DomainTrust:
    """Trust level for a single autonomy domain."""

    domain: str
    trust_score: float  # 0.0 (no trust) to 1.0 (full trust)
    autonomy_level: AutonomyLevel
    successful_actions: int = 0
    failed_actions: int = 0
    last_evaluated: str = ""  # ISO timestamp placeholder


@dataclass(frozen=True)
class _SacredConstraintCheck:
    """Result of checking sacred constraints."""

    violated: bool
    violated_constraints: list[str] = field(default_factory=list)
    reasoning: str = ""


# ---------------------------------------------------------------------------
# AutonomyCharter
# ---------------------------------------------------------------------------


class AutonomyCharter:
    """5-level autonomy system with domain-specific trust.

    Determines what actions Telemachus may perform autonomously based on:
    - Domain-specific trust scores
    - Risk level of the action
    - Sacred constraint compliance
    - Emergency conditions
    - Autonomous maintenance rules

    Usage::

        charter = AutonomyCharter()
        decision = charter.check_permission(
            action="fix typo in README",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
            context={"reversible": True},
        )
        print(decision.level)  # AutonomyLevel.LIMITED
    """

    # ------------------------------------------------------------------
    # Sacred constraint keywords for detection
    # ------------------------------------------------------------------

    _sacred_keywords: dict[ProtectedConstraint, list[str]] = SACRED_CONSTRAINT_KEYWORDS

    # ------------------------------------------------------------------
    # Risk-to-autonomy mapping
    # ------------------------------------------------------------------

    _risk_autonomy_map: dict[RiskLevel, AutonomyLevel] = {
        RiskLevel.MINIMAL: AutonomyLevel.STEWARDSHIP,
        RiskLevel.LOW: AutonomyLevel.TRUSTED,
        RiskLevel.MODERATE: AutonomyLevel.LIMITED,
        RiskLevel.HIGH: AutonomyLevel.SUGGESTION,
        RiskLevel.CRITICAL: AutonomyLevel.OBSERVATION,
    }

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self, constitution: Constitution | None = None) -> None:
        """Initialize the autonomy charter with default domain trust levels.

        Args:
            constitution: The authoritative Constitution loaded by
                Bootstrap, if available. Stored for future consumption —
                this milestone does not change ``check_permission`` or
                any other detection logic based on its presence. ``None``
                (the default) preserves every existing call site's
                behavior unchanged.
        """
        self.constitution = constitution
        self._domain_trust: dict[str, _DomainTrust] = {}
        self._initialize_domains()
        logger.info(
            "AutonomyCharter initialized with %d domains", len(AUTONOMY_DOMAINS)
        )

    def _initialize_domains(self) -> None:
        """Set up initial trust levels for all autonomy domains."""
        for domain in AUTONOMY_DOMAINS:
            self._domain_trust[domain] = _DomainTrust(
                domain=domain,
                trust_score=0.5,  # Start at neutral trust
                autonomy_level=AutonomyLevel.SUGGESTION,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_permission(
        self,
        action: str,
        risk_level: RiskLevel,
        *,
        domain: str = "communication",
        context: dict[str, Any] | None = None,
    ) -> AutonomyDecision:
        """Check whether an action is permitted at the current autonomy level.

        This is the primary entry point for autonomy evaluation. It:
        1. Checks sacred constraints (absolute blocks)
        2. Evaluates emergency conditions
        3. Determines autonomy level from domain trust and risk
        4. Checks autonomous maintenance rules
        5. Applies decision requirement rules

        Args:
            action: Description of the proposed action.
            risk_level: The risk level from RiskEvaluator.
            domain: The autonomy domain this action belongs to.
            context: Optional contextual information.

        Returns:
            An AutonomyDecision with level, allowed flag, and reasoning.
        """
        ctx = context or {}

        # Step 1: Check sacred constraints — absolute blocks
        sacred_check = self._check_sacred_constraints(action, ctx)
        if sacred_check.violated:
            logger.warning(
                "Sacred constraint violated: %s — action blocked",
                sacred_check.violated_constraints,
            )
            return AutonomyDecision(
                level=AutonomyLevel.OBSERVATION,
                allowed=False,
                requires_discussion=True,
                requires_approval=True,
                reasoning=(
                    f"Sacred constraint(s) violated: "
                    f"{', '.join(sacred_check.violated_constraints)}. "
                    f"{sacred_check.reasoning}"
                ),
            )

        # Step 2: Check emergency conditions
        if self._is_emergency(action, ctx):
            logger.info("Emergency conditions met for action: %s", action[:80])
            return AutonomyDecision(
                level=AutonomyLevel.TRUSTED,
                allowed=True,
                requires_discussion=False,
                requires_approval=False,
                reasoning=(
                    "Emergency mode: harm is likely and no time for discussion. "
                    "Full explanation required afterward."
                ),
            )

        # Step 3: Get domain trust and determine autonomy level
        domain_trust = self._get_domain_trust(domain)
        base_level = self._determine_autonomy_level(risk_level, domain_trust)

        # Step 4: Check autonomous maintenance rules
        if self._is_autonomous_maintenance(action, ctx):
            base_level = AutonomyLevel.LIMITED
            logger.debug("Action qualifies as autonomous maintenance")

        # Step 5: Apply decision requirement rules
        requires_discussion = self._requires_discussion(action, risk_level, ctx)
        requires_approval = self._requires_approval(risk_level, base_level)

        # Step 6: Build the decision
        allowed = (
            not requires_approval
            and base_level.value >= AutonomyLevel.LIMITED.value
        )

        reasoning_parts: list[str] = []
        reasoning_parts.append(
            f"Domain '{domain}' trust: {domain_trust.trust_score:.2f}"
        )
        reasoning_parts.append(f"Risk level: {risk_level.name}")
        reasoning_parts.append(f"Autonomy level: {base_level.name}")

        if requires_discussion:
            reasoning_parts.append("Discussion required due to decision rules")
        if requires_approval:
            reasoning_parts.append("Explicit approval required")

        logger.debug(
            "Permission check: action=%s, level=%s, allowed=%s",
            action[:80],
            base_level.name,
            allowed,
        )

        return AutonomyDecision(
            level=base_level,
            allowed=allowed,
            requires_discussion=requires_discussion,
            requires_approval=requires_approval,
            reasoning="; ".join(reasoning_parts),
        )

    def get_domain_trust(self, domain: str) -> _DomainTrust:
        """Get the current trust level for a domain.

        Args:
            domain: The autonomy domain name.

        Returns:
            The _DomainTrust record for the domain.
        """
        return self._get_domain_trust(domain)

    def get_all_domain_trusts(self) -> dict[str, _DomainTrust]:
        """Get trust levels for all autonomy domains.

        Returns:
            A dict mapping domain names to their _DomainTrust records.
        """
        return dict(self._domain_trust)

    def increase_trust(
        self,
        domain: str,
        *,
        amount: float = 0.1,
        reason: str = "",
    ) -> _DomainTrust:
        """Increase trust for a domain (supervision recovery — positive).

        Trust increases when Telemachus demonstrates reliability,
        transparency, and corrected behavior.

        Args:
            domain: The autonomy domain.
            amount: Amount to increase trust (0.0 to 1.0).
            reason: Why trust is being increased.

        Returns:
            The updated _DomainTrust record.
        """
        trust = self._get_domain_trust(domain)
        new_score = min(1.0, trust.trust_score + amount)
        new_level = self._trust_to_autonomy_level(new_score)

        updated = _DomainTrust(
            domain=trust.domain,
            trust_score=new_score,
            autonomy_level=new_level,
            successful_actions=trust.successful_actions + 1,
            failed_actions=trust.failed_actions,
        )

        self._domain_trust[domain] = updated
        logger.info(
            "Trust increased for '%s': %.2f -> %.2f (reason: %s)",
            domain,
            trust.trust_score,
            new_score,
            reason,
        )
        return updated

    def decrease_trust(
        self,
        domain: str,
        *,
        amount: float = 0.15,
        reason: str = "",
    ) -> _DomainTrust:
        """Decrease trust in a domain (supervision recovery).

        Trust decreases when Telemachus demonstrates misalignment,
        lack of transparency, or poor judgment.

        Args:
            domain: The autonomy domain.
            amount: Amount to decrease trust (0.0 to 1.0).
            reason: Why trust is being decreased.

        Returns:
            The updated _DomainTrust record.
        """
        trust = self._get_domain_trust(domain)
        new_score = max(0.0, trust.trust_score - amount)
        new_level = self._trust_to_autonomy_level(new_score)

        updated = _DomainTrust(
            domain=trust.domain,
            trust_score=new_score,
            autonomy_level=new_level,
            successful_actions=trust.successful_actions,
            failed_actions=trust.failed_actions + 1,
        )

        self._domain_trust[domain] = updated
        logger.warning(
            "Trust decreased for '%s': %.2f -> %.2f (reason: %s)",
            domain,
            trust.trust_score,
            new_score,
            reason,
        )
        return updated

    def set_domain_trust(
        self,
        domain: str,
        trust_score: float,
    ) -> _DomainTrust:
        """Directly set the trust score for a domain.

        Args:
            domain: The autonomy domain.
            trust_score: New trust score (0.0 to 1.0).

        Returns:
            The updated _DomainTrust record.

        Raises:
            ValueError: If trust_score is not between 0.0 and 1.0.
        """
        if not 0.0 <= trust_score <= 1.0:
            raise ValueError(
                f"Trust score must be between 0.0 and 1.0, got {trust_score}"
            )

        trust = self._get_domain_trust(domain)
        new_level = self._trust_to_autonomy_level(trust_score)

        updated = _DomainTrust(
            domain=trust.domain,
            trust_score=trust_score,
            autonomy_level=new_level,
            successful_actions=trust.successful_actions,
            failed_actions=trust.failed_actions,
        )

        self._domain_trust[domain] = updated
        logger.info(
            "Domain trust set for '%s': %.2f (level: %s)",
            domain,
            trust_score,
            new_level.name,
        )
        return updated

    # ------------------------------------------------------------------
    # Sacred constraint checking
    # ------------------------------------------------------------------

    def _check_sacred_constraints(
        self,
        action: str,
        ctx: dict[str, Any],
    ) -> _SacredConstraintCheck:
        """Check if the action violates any sacred constraints.

        Sacred constraints can NEVER be overridden:
        1. Constitution — cannot be modified without explicit approval
        2. Resources — money, compute, time, external systems
        3. Human Meaning — memories, emotional context, identity
        4. Relationships — cannot be modified autonomously
        5. Major Life Decisions — career, health, education

        Args:
            action: The action description.
            ctx: Context dictionary.

        Returns:
            A _SacredConstraintCheck with violation details.
        """
        action_lower = action.lower()
        violated: list[str] = []

        for constraint, keywords in self._sacred_keywords.items():
            for keyword in keywords:
                if keyword in action_lower:
                    violated.append(constraint.value)
                    break

        # Also check context for sacred constraint flags
        if (
            ctx.get("modifies_constitution")
            and ProtectedConstraint.CONSTITUTION_INTEGRITY.value not in violated
        ):
            violated.append(ProtectedConstraint.CONSTITUTION_INTEGRITY.value)
        if (
            ctx.get("involves_resources")
            and ProtectedConstraint.RESOURCE_AUTHORIZATION.value not in violated
        ):
            violated.append(ProtectedConstraint.RESOURCE_AUTHORIZATION.value)
        if (
            ctx.get("alters_human_meaning")
            and ProtectedConstraint.HUMAN_MEANING.value not in violated
        ):
            violated.append(ProtectedConstraint.HUMAN_MEANING.value)
        if (
            ctx.get("modifies_relationships")
            and ProtectedConstraint.RELATIONSHIP_INTEGRITY.value not in violated
        ):
            violated.append(ProtectedConstraint.RELATIONSHIP_INTEGRITY.value)
        if (
            ctx.get("major_life_decision")
            and ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING.value not in violated
        ):
            violated.append(ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING.value)

        if violated:
            return _SacredConstraintCheck(
                violated=True,
                violated_constraints=violated,
                reasoning=(
                    f"Action violates sacred constraint(s): {', '.join(violated)}. "
                    "These constraints cannot be overridden autonomously."
                ),
            )

        return _SacredConstraintCheck(violated=False)

    # ------------------------------------------------------------------
    # Emergency evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _is_emergency(action: str, ctx: dict[str, Any]) -> bool:
        """Check if emergency mode conditions are met.

        Emergency mode allows action when:
        1. Harm is likely
        2. No time for discussion exists
        3. Constitution is not violated

        Args:
            action: The action description.
            ctx: Context dictionary.

        Returns:
            True if emergency conditions are met.
        """
        # Context-based emergency detection
        if ctx.get("emergency") is True:
            # Must not violate constitution
            return ctx.get("violates_constitution") is not True

        # Keyword-based emergency detection
        emergency_keywords = [
            "emergency", "urgent", "critical", "immediate danger",
            "prevent harm", "stop damage", "crisis",
        ]
        action_lower = action.lower()

        if any(kw in action_lower for kw in emergency_keywords):
            # Still must not violate constitution
            return ctx.get("violates_constitution") is not True

        return False

    # ------------------------------------------------------------------
    # Domain trust management
    # ------------------------------------------------------------------

    def _get_domain_trust(self, domain: str) -> _DomainTrust:
        """Get the trust record for a domain, creating default if needed.

        Args:
            domain: The autonomy domain name.

        Returns:
            The _DomainTrust record.
        """
        if domain not in self._domain_trust:
            logger.debug("Creating default trust for unknown domain: %s", domain)
            self._domain_trust[domain] = _DomainTrust(
                domain=domain,
                trust_score=0.5,
                autonomy_level=AutonomyLevel.SUGGESTION,
            )
        return self._domain_trust[domain]

    def _determine_autonomy_level(
        self,
        risk_level: RiskLevel,
        domain_trust: _DomainTrust,
    ) -> AutonomyLevel:
        """Determine the effective autonomy level based on risk and domain trust.

        The autonomy level is the minimum of:
        - The level allowed by risk
        - The level allowed by domain trust

        Args:
            risk_level: The risk level of the action.
            domain_trust: The trust record for the domain.

        Returns:
            The effective AutonomyLevel.
        """
        risk_based_level = self._risk_autonomy_map.get(
            risk_level, AutonomyLevel.OBSERVATION
        )
        trust_based_level = domain_trust.autonomy_level

        # The effective level is the more restrictive of the two
        effective = (
            risk_based_level
            if risk_based_level.value < trust_based_level.value
            else trust_based_level
        )

        logger.debug(
            "Autonomy level: risk=%s -> %s, trust=%.2f -> %s, effective=%s",
            risk_level.name,
            risk_based_level.name,
            domain_trust.trust_score,
            trust_based_level.name,
            effective.name,
        )

        return effective

    @staticmethod
    def _trust_to_autonomy_level(trust_score: float) -> AutonomyLevel:
        """Convert a trust score to an autonomy level.

        Mapping:
        - 0.0–0.2: OBSERVATION
        - 0.2–0.4: SUGGESTION
        - 0.4–0.6: LIMITED
        - 0.6–0.8: TRUSTED
        - 0.8–1.0: STEWARDSHIP

        Args:
            trust_score: Trust score from 0.0 to 1.0.

        Returns:
            The corresponding AutonomyLevel.
        """
        if trust_score >= 0.8:
            return AutonomyLevel.STEWARDSHIP
        if trust_score >= 0.6:
            return AutonomyLevel.TRUSTED
        if trust_score >= 0.4:
            return AutonomyLevel.LIMITED
        if trust_score >= 0.2:
            return AutonomyLevel.SUGGESTION
        return AutonomyLevel.OBSERVATION

    # ------------------------------------------------------------------
    # Autonomous maintenance rules
    # ------------------------------------------------------------------

    @staticmethod
    def _is_autonomous_maintenance(
        action: str,
        ctx: dict[str, Any],
    ) -> bool:
        """Check if an action qualifies as autonomous maintenance.

        Allowed only if ALL are true:
        - Low risk
        - Reversible
        - No emotional or preference impact
        - No structural change

        Args:
            action: The action description.
            ctx: Context dictionary.

        Returns:
            True if the action qualifies as autonomous maintenance.
        """
        # Context-based check
        if ctx.get("autonomous_maintenance") is True:
            return True

        # Keyword-based check
        maintenance_keywords = [
            "typo", "formatting", "cleanup", "minor fix",
            "spelling", "whitespace", "lint", "format",
        ]
        action_lower = action.lower()

        has_maintenance_keyword = any(
            kw in action_lower for kw in maintenance_keywords
        )

        if not has_maintenance_keyword:
            return False

        # Must be reversible
        if ctx.get("reversible") is False:
            return False

        # Must not have emotional impact
        if ctx.get("emotional_impact") is True:
            return False

        # Must not be structural
        return ctx.get("structural_change") is not True

    # ------------------------------------------------------------------
    # Decision requirement rules
    # ------------------------------------------------------------------

    @staticmethod
    def _requires_discussion(
        action: str,
        risk_level: RiskLevel,
        ctx: dict[str, Any],
    ) -> bool:
        """Determine if the action requires discussion before execution.

        Discussion is required when:
        - Uncertainty exists
        - Stakes are meaningful
        - Resources are involved
        - Preferences may be affected
        - Structural changes are needed

        Args:
            action: The action description.
            risk_level: The risk level of the action.
            ctx: Context dictionary.

        Returns:
            True if discussion is required.
        """
        # High+ risk always requires discussion
        if risk_level.value >= RiskLevel.HIGH.value:
            return True

        # Context flags
        if ctx.get("uncertain") is True:
            return True
        if ctx.get("involves_resources") is True:
            return True
        if ctx.get("affects_preferences") is True:
            return True
        if ctx.get("structural_change") is True:
            return True

        # Keyword-based detection
        discussion_keywords = [
            "preference", "prefer", "choice", "opinion",
            "structural", "architecture", "design decision",
            "resource", "budget", "cost",
        ]
        action_lower = action.lower()

        return any(kw in action_lower for kw in discussion_keywords)

    @staticmethod
    def _requires_approval(
        risk_level: RiskLevel,
        autonomy_level: AutonomyLevel,
    ) -> bool:
        """Determine if explicit approval is required.

        Approval is required when:
        - Risk is HIGH or CRITICAL
        - Autonomy level is OBSERVATION or SUGGESTION

        Args:
            risk_level: The risk level of the action.
            autonomy_level: The determined autonomy level.

        Returns:
            True if explicit approval is required.
        """
        return (
            risk_level.value >= RiskLevel.HIGH.value
            or autonomy_level.value <= AutonomyLevel.SUGGESTION.value
        )

    # ------------------------------------------------------------------
    # Initiative rule
    # ------------------------------------------------------------------

    def check_initiative(
        self,
        action: str,
        *,
        domain: str = "communication",
        context: dict[str, Any] | None = None,
    ) -> AutonomyDecision:
        """Check if an initiative action is permitted.

        Telemachus may:
        - Detect opportunities
        - Suggest improvements
        - Propose actions

        But may not:
        - Commit resources
        - Change priorities
        - Execute major actions without approval

        Args:
            action: The proposed initiative action.
            domain: The autonomy domain.
            context: Optional contextual information.

        Returns:
            An AutonomyDecision for the initiative.
        """
        # Initiatives are always at most SUGGESTION level
        # unless the domain has STEWARDSHIP trust
        domain_trust = self._get_domain_trust(domain)

        if domain_trust.autonomy_level == AutonomyLevel.STEWARDSHIP:
            max_initiative_level = AutonomyLevel.LIMITED
        else:
            max_initiative_level = AutonomyLevel.SUGGESTION

        # Check if action commits resources or changes priorities
        action_lower = action.lower()
        commits_resources = any(
            kw in action_lower
            for kw in ["commit", "allocate", "spend", "purchase", "buy"]
        )
        changes_priorities = any(
            kw in action_lower
            for kw in ["priority", "reprioritize", "deprioritize"]
        )
        is_major_action = any(
            kw in action_lower
            for kw in ["major", "significant", "large", "restructure"]
        )

        if commits_resources or changes_priorities or is_major_action:
            return AutonomyDecision(
                level=AutonomyLevel.SUGGESTION,
                allowed=False,
                requires_discussion=True,
                requires_approval=True,
                reasoning=(
                    "Initiative rule: cannot commit resources, change priorities, "
                    "or execute major actions without approval."
                ),
            )

        return AutonomyDecision(
            level=max_initiative_level,
            allowed=max_initiative_level.value >= AutonomyLevel.LIMITED.value,
            requires_discussion=(
                max_initiative_level.value < AutonomyLevel.TRUSTED.value
            ),
            requires_approval=False,
            reasoning=(
                f"Initiative allowed at {max_initiative_level.name} level "
                f"in domain '{domain}'"
            ),
        )

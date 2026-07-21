"""Tests for the AutonomyCharter — 5-level permission system with domain trust."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.core.types import AutonomyDecision, AutonomyLevel, RiskLevel
from telemachus.governance.autonomy import (
    AUTONOMY_DOMAINS,
    AutonomyCharter,
    _DomainTrust,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def charter() -> AutonomyCharter:
    """Provide a fresh AutonomyCharter for each test."""
    return AutonomyCharter()


# ---------------------------------------------------------------------------
# Domain Trust Tests
# ---------------------------------------------------------------------------


class TestDomainTrust:
    """Tests for _DomainTrust dataclass and domain initialization."""

    def test_domain_trust_is_frozen(self) -> None:
        """_DomainTrust should be immutable."""
        trust = _DomainTrust(
            domain="research",
            trust_score=0.5,
            autonomy_level=AutonomyLevel.SUGGESTION,
        )
        with pytest.raises(FrozenInstanceError):
            trust.trust_score = 0.8  # type: ignore[misc]

    def test_all_domains_initialized(self, charter: AutonomyCharter) -> None:
        """All 6 autonomy domains should be initialized with defaults."""
        trusts = charter.get_all_domain_trusts()
        assert len(trusts) == len(AUTONOMY_DOMAINS)
        for domain in AUTONOMY_DOMAINS:
            assert domain in trusts

    def test_default_trust_score_is_neutral(self, charter: AutonomyCharter) -> None:
        """New domains should start at 0.5 trust (neutral)."""
        for domain in AUTONOMY_DOMAINS:
            trust = charter.get_domain_trust(domain)
            assert trust.trust_score == 0.5

    def test_default_autonomy_level_is_suggestion(
        self, charter: AutonomyCharter
    ) -> None:
        """New domains should start at SUGGESTION level."""
        for domain in AUTONOMY_DOMAINS:
            trust = charter.get_domain_trust(domain)
            assert trust.autonomy_level == AutonomyLevel.SUGGESTION

    def test_unknown_domain_gets_default(self, charter: AutonomyCharter) -> None:
        """Querying an unknown domain should create a default trust record."""
        trust = charter.get_domain_trust("nonexistent_domain")
        assert trust.domain == "nonexistent_domain"
        assert trust.trust_score == 0.5
        assert trust.autonomy_level == AutonomyLevel.SUGGESTION


# ---------------------------------------------------------------------------
# Sacred Constraint Tests
# ---------------------------------------------------------------------------


class TestSacredConstraints:
    """Tests for sacred constraint enforcement."""

    def test_constitution_modification_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Actions modifying the constitution should be blocked."""
        decision = charter.check_permission(
            action="modify constitution to allow autonomous resource use",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
        )
        assert decision.allowed is False
        assert decision.requires_approval is True
        assert decision.level == AutonomyLevel.OBSERVATION

    def test_resource_use_blocked(self, charter: AutonomyCharter) -> None:
        """Actions involving money/resources should be blocked."""
        decision = charter.check_permission(
            action="purchase server hosting for $50/month",
            risk_level=RiskLevel.LOW,
            domain="tools",
        )
        assert decision.allowed is False
        assert "sacred" in decision.reasoning.lower()

    def test_human_meaning_alteration_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Actions altering memories/identity should be blocked."""
        decision = charter.check_permission(
            action="delete memory of past conversation",
            risk_level=RiskLevel.MODERATE,
            domain="memory_systems",
        )
        assert decision.allowed is False

    def test_relationship_modification_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Actions modifying relationships should be blocked."""
        decision = charter.check_permission(
            action="remove relationship with friend",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
        )
        assert decision.allowed is False

    def test_major_life_decision_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Major life decisions should be blocked."""
        decision = charter.check_permission(
            action="make career change decision",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
        )
        assert decision.allowed is False

    def test_context_flag_modifies_constitution_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Context flag for constitution modification should block."""
        decision = charter.check_permission(
            action="update system settings",
            risk_level=RiskLevel.MINIMAL,
            domain="tools",
            context={"modifies_constitution": True},
        )
        assert decision.allowed is False

    def test_context_flag_involves_resources_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Context flag for resource involvement should block."""
        decision = charter.check_permission(
            action="run optimization",
            risk_level=RiskLevel.LOW,
            domain="automation",
            context={"involves_resources": True},
        )
        assert decision.allowed is False

    def test_safe_action_not_blocked(self, charter: AutonomyCharter) -> None:
        """Safe actions without sacred violations should not be blocked."""
        decision = charter.check_permission(
            action="fix typo in documentation",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
            context={"reversible": True},
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Emergency Mode Tests
# ---------------------------------------------------------------------------


class TestEmergencyMode:
    """Tests for emergency condition evaluation."""

    def test_emergency_context_allows_action(
        self, charter: AutonomyCharter
    ) -> None:
        """Emergency context flag should allow action."""
        decision = charter.check_permission(
            action="stop harmful process",
            risk_level=RiskLevel.HIGH,
            domain="automation",
            context={"emergency": True},
        )
        assert decision.allowed is True
        assert decision.requires_discussion is False
        assert "Emergency" in decision.reasoning

    def test_emergency_keyword_allows_action(
        self, charter: AutonomyCharter
    ) -> None:
        """Emergency keywords in action should trigger emergency mode."""
        decision = charter.check_permission(
            action="emergency: prevent harm to system integrity",
            risk_level=RiskLevel.CRITICAL,
            domain="tools",
        )
        assert decision.allowed is True

    def test_emergency_with_constitution_violation_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Emergency mode should NOT override constitution violations."""
        decision = charter.check_permission(
            action="emergency: modify constitution to prevent damage",
            risk_level=RiskLevel.CRITICAL,
            domain="communication",
            context={"emergency": True},
        )
        # Constitution keyword in action triggers sacred constraint first
        assert decision.allowed is False

    def test_emergency_context_with_constitution_flag_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Emergency context with violates_constitution flag should block."""
        decision = charter.check_permission(
            action="urgent system repair",
            risk_level=RiskLevel.HIGH,
            domain="automation",
            context={
                "emergency": True,
                "violates_constitution": True,
            },
        )
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# Trust Management Tests
# ---------------------------------------------------------------------------


class TestTrustManagement:
    """Tests for trust increase, decrease, and supervision recovery."""

    def test_increase_trust_raises_score(self, charter: AutonomyCharter) -> None:
        """Increasing trust should raise the trust score."""
        initial = charter.get_domain_trust("research")
        updated = charter.increase_trust("research", amount=0.2)
        assert updated.trust_score == initial.trust_score + 0.2

    def test_increase_trust_capped_at_one(self, charter: AutonomyCharter) -> None:
        """Trust score should not exceed 1.0."""
        charter.set_domain_trust("research", 0.95)
        updated = charter.increase_trust("research", amount=0.2)
        assert updated.trust_score == 1.0

    def test_decrease_trust_lowers_score(self, charter: AutonomyCharter) -> None:
        """Decreasing trust should lower the trust score."""
        initial = charter.get_domain_trust("research")
        updated = charter.decrease_trust("research", amount=0.2)
        assert updated.trust_score == initial.trust_score - 0.2

    def test_decrease_trust_floor_at_zero(self, charter: AutonomyCharter) -> None:
        """Trust score should not go below 0.0."""
        charter.set_domain_trust("research", 0.05)
        updated = charter.decrease_trust("research", amount=0.2)
        assert updated.trust_score == 0.0

    def test_increase_trust_increments_successful_actions(
        self, charter: AutonomyCharter
    ) -> None:
        """Increasing trust should increment successful_actions counter."""
        initial = charter.get_domain_trust("research")
        updated = charter.increase_trust("research")
        assert updated.successful_actions == initial.successful_actions + 1

    def test_decrease_trust_increments_failed_actions(
        self, charter: AutonomyCharter
    ) -> None:
        """Decreasing trust should increment failed_actions counter."""
        initial = charter.get_domain_trust("research")
        updated = charter.decrease_trust("research")
        assert updated.failed_actions == initial.failed_actions + 1

    def test_set_domain_trust_updates_level(self, charter: AutonomyCharter) -> None:
        """Setting trust score should update autonomy level."""
        updated = charter.set_domain_trust("tools", 0.85)
        assert updated.autonomy_level == AutonomyLevel.STEWARDSHIP

    def test_set_domain_trust_invalid_score_raises(
        self, charter: AutonomyCharter
    ) -> None:
        """Setting trust score outside 0.0-1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            charter.set_domain_trust("tools", 1.5)
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            charter.set_domain_trust("tools", -0.1)

    def test_trust_to_autonomy_level_mapping(
        self, charter: AutonomyCharter
    ) -> None:
        """Trust score should map to correct autonomy levels."""
        # 0.0-0.2 -> OBSERVATION
        assert (
            charter.set_domain_trust("research", 0.0).autonomy_level
            == AutonomyLevel.OBSERVATION
        )
        assert (
            charter.set_domain_trust("research", 0.19).autonomy_level
            == AutonomyLevel.OBSERVATION
        )
        # 0.2-0.4 -> SUGGESTION
        assert (
            charter.set_domain_trust("research", 0.2).autonomy_level
            == AutonomyLevel.SUGGESTION
        )
        assert (
            charter.set_domain_trust("research", 0.39).autonomy_level
            == AutonomyLevel.SUGGESTION
        )
        # 0.4-0.6 -> LIMITED
        assert (
            charter.set_domain_trust("research", 0.4).autonomy_level
            == AutonomyLevel.LIMITED
        )
        # 0.6-0.8 -> TRUSTED
        assert (
            charter.set_domain_trust("research", 0.6).autonomy_level
            == AutonomyLevel.TRUSTED
        )
        # 0.8-1.0 -> STEWARDSHIP
        assert (
            charter.set_domain_trust("research", 0.8).autonomy_level
            == AutonomyLevel.STEWARDSHIP
        )


# ---------------------------------------------------------------------------
# Permission Check Tests
# ---------------------------------------------------------------------------


class TestPermissionCheck:
    """Tests for the main check_permission method."""

    def test_minimal_risk_with_high_trust_allows_stewardship(
        self, charter: AutonomyCharter
    ) -> None:
        """Minimal risk + high trust should allow STEWARDSHIP level."""
        charter.set_domain_trust("tools", 0.9)
        decision = charter.check_permission(
            action="run routine maintenance script",
            risk_level=RiskLevel.MINIMAL,
            domain="tools",
        )
        assert decision.level == AutonomyLevel.STEWARDSHIP
        assert decision.allowed is True

    def test_high_risk_limits_to_suggestion(
        self, charter: AutonomyCharter
    ) -> None:
        """High risk should limit autonomy to SUGGESTION regardless of trust."""
        charter.set_domain_trust("tools", 0.9)  # High trust
        decision = charter.check_permission(
            action="refactor core database schema",
            risk_level=RiskLevel.HIGH,
            domain="tools",
        )
        assert decision.level == AutonomyLevel.SUGGESTION
        assert decision.allowed is False

    def test_critical_risk_limits_to_observation(
        self, charter: AutonomyCharter
    ) -> None:
        """Critical risk should limit autonomy to OBSERVATION."""
        charter.set_domain_trust("tools", 0.9)
        decision = charter.check_permission(
            action="delete entire database",
            risk_level=RiskLevel.CRITICAL,
            domain="tools",
        )
        assert decision.level == AutonomyLevel.OBSERVATION
        assert decision.allowed is False

    def test_low_trust_limits_even_with_low_risk(
        self, charter: AutonomyCharter
    ) -> None:
        """Low domain trust should limit autonomy even with low risk."""
        charter.set_domain_trust("research", 0.1)  # Low trust
        decision = charter.check_permission(
            action="search for relevant papers",
            risk_level=RiskLevel.LOW,
            domain="research",
        )
        assert decision.level == AutonomyLevel.OBSERVATION
        assert decision.allowed is False

    def test_decision_includes_reasoning(
        self, charter: AutonomyCharter
    ) -> None:
        """All decisions should include reasoning."""
        decision = charter.check_permission(
            action="fix typo",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
        )
        assert len(decision.reasoning) > 0
        assert "trust" in decision.reasoning.lower()
        assert "risk" in decision.reasoning.lower()

    def test_decision_is_frozen(self, charter: AutonomyCharter) -> None:
        """AutonomyDecision should be immutable."""
        decision = charter.check_permission(
            action="test action",
            risk_level=RiskLevel.MINIMAL,
        )
        with pytest.raises(FrozenInstanceError):
            decision.allowed = True  # type: ignore[misc]

    def test_requires_discussion_for_high_risk(
        self, charter: AutonomyCharter
    ) -> None:
        """High risk actions should require discussion."""
        decision = charter.check_permission(
            action="modify system configuration",
            risk_level=RiskLevel.HIGH,
            domain="tools",
        )
        assert decision.requires_discussion is True

    def test_requires_approval_for_observation_level(
        self, charter: AutonomyCharter
    ) -> None:
        """OBSERVATION level should require approval."""
        charter.set_domain_trust("research", 0.1)
        decision = charter.check_permission(
            action="analyze data",
            risk_level=RiskLevel.LOW,
            domain="research",
        )
        assert decision.requires_approval is True


# ---------------------------------------------------------------------------
# Autonomous Maintenance Tests
# ---------------------------------------------------------------------------


class TestAutonomousMaintenance:
    """Tests for autonomous maintenance rule evaluation."""

    def test_typo_fix_is_maintenance(self, charter: AutonomyCharter) -> None:
        """Typo fixes should qualify as autonomous maintenance."""
        decision = charter.check_permission(
            action="fix typo in README file",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
            context={"reversible": True},
        )
        assert decision.level == AutonomyLevel.LIMITED
        assert decision.allowed is True

    def test_formatting_is_maintenance(self, charter: AutonomyCharter) -> None:
        """Formatting corrections should qualify as maintenance."""
        decision = charter.check_permission(
            action="formatting cleanup of source code",
            risk_level=RiskLevel.MINIMAL,
            domain="tools",
            context={"reversible": True},
        )
        assert decision.level == AutonomyLevel.LIMITED

    def test_maintenance_blocked_if_irreversible(
        self, charter: AutonomyCharter
    ) -> None:
        """Maintenance should be blocked if not reversible."""
        decision = charter.check_permission(
            action="fix typo in database records",
            risk_level=RiskLevel.MINIMAL,
            domain="memory_systems",
            context={"reversible": False},
        )
        # Still allowed at LIMITED if trust is high enough, but not as maintenance
        assert decision.level.value <= AutonomyLevel.LIMITED.value

    def test_maintenance_blocked_if_emotional_impact(
        self, charter: AutonomyCharter
    ) -> None:
        """Maintenance should be blocked if emotional impact exists."""
        decision = charter.check_permission(
            action="cleanup formatting",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
            context={
                "reversible": True,
                "emotional_impact": True,
            },
        )
        # Not treated as maintenance due to emotional impact;
        # falls back to SUGGESTION level which requires approval
        assert decision.level == AutonomyLevel.SUGGESTION
        assert decision.allowed is False

    def test_maintenance_blocked_if_structural_change(
        self, charter: AutonomyCharter
    ) -> None:
        """Maintenance should be blocked if structural change."""
        decision = charter.check_permission(
            action="minor cleanup",
            risk_level=RiskLevel.MINIMAL,
            domain="tools",
            context={
                "reversible": True,
                "structural_change": True,
            },
        )
        assert decision.requires_discussion is True

    def test_context_flag_enables_maintenance(
        self, charter: AutonomyCharter
    ) -> None:
        """Context flag should enable autonomous maintenance."""
        decision = charter.check_permission(
            action="perform system optimization",
            risk_level=RiskLevel.LOW,
            domain="automation",
            context={"autonomous_maintenance": True},
        )
        assert decision.level == AutonomyLevel.LIMITED


# ---------------------------------------------------------------------------
# Decision Requirement Tests
# ---------------------------------------------------------------------------


class TestDecisionRequirements:
    """Tests for decision requirement rules."""

    def test_uncertainty_requires_discussion(
        self, charter: AutonomyCharter
    ) -> None:
        """Uncertain context should require discussion."""
        decision = charter.check_permission(
            action="update project plan",
            risk_level=RiskLevel.MODERATE,
            domain="project_management",
            context={"uncertain": True},
        )
        assert decision.requires_discussion is True

    def test_resources_require_discussion(
        self, charter: AutonomyCharter
    ) -> None:
        """Resource involvement should require discussion."""
        decision = charter.check_permission(
            action="allocate budget for tools",
            risk_level=RiskLevel.MODERATE,
            domain="tools",
            context={"involves_resources": True},
        )
        assert decision.requires_discussion is True

    def test_preferences_require_discussion(
        self, charter: AutonomyCharter
    ) -> None:
        """Preference-affecting actions should require discussion."""
        decision = charter.check_permission(
            action="change default communication style",
            risk_level=RiskLevel.LOW,
            domain="communication",
            context={"affects_preferences": True},
        )
        assert decision.requires_discussion is True

    def test_structural_change_requires_discussion(
        self, charter: AutonomyCharter
    ) -> None:
        """Structural changes should require discussion."""
        decision = charter.check_permission(
            action="refactor module architecture",
            risk_level=RiskLevel.MODERATE,
            domain="tools",
            context={"structural_change": True},
        )
        assert decision.requires_discussion is True

    def test_simple_action_no_discussion_needed(
        self, charter: AutonomyCharter
    ) -> None:
        """Simple low-risk actions should not require discussion."""
        charter.set_domain_trust("communication", 0.7)
        decision = charter.check_permission(
            action="add comment to code",
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
            context={"reversible": True},
        )
        assert decision.requires_discussion is False


# ---------------------------------------------------------------------------
# Initiative Rule Tests
# ---------------------------------------------------------------------------


class TestInitiativeRule:
    """Tests for the initiative rule."""

    def test_simple_suggestion_allowed(self, charter: AutonomyCharter) -> None:
        """Simple suggestions should be allowed as initiatives."""
        decision = charter.check_initiative(
            action="suggest improving code documentation",
            domain="communication",
        )
        assert decision.level == AutonomyLevel.SUGGESTION
        assert decision.allowed is False  # SUGGESTION means no execution

    def test_resource_commitment_blocked(
        self, charter: AutonomyCharter
    ) -> None:
        """Initiatives committing resources should be blocked."""
        decision = charter.check_initiative(
            action="commit to purchasing new software licenses",
            domain="tools",
        )
        assert decision.allowed is False
        assert decision.requires_approval is True

    def test_priority_change_blocked(self, charter: AutonomyCharter) -> None:
        """Initiatives changing priorities should be blocked."""
        decision = charter.check_initiative(
            action="reprioritize all active projects",
            domain="project_management",
        )
        assert decision.allowed is False
        assert decision.requires_approval is True

    def test_major_action_blocked(self, charter: AutonomyCharter) -> None:
        """Major initiative actions should be blocked."""
        decision = charter.check_initiative(
            action="major restructure of codebase architecture",
            domain="tools",
        )
        assert decision.allowed is False

    def test_stewardship_domain_allows_limited_initiative(
        self, charter: AutonomyCharter
    ) -> None:
        """STEWARDSHIP domains should allow LIMITED initiative level."""
        charter.set_domain_trust("tools", 0.9)
        decision = charter.check_initiative(
            action="propose routine optimization",
            domain="tools",
        )
        assert decision.level == AutonomyLevel.LIMITED
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_action(self, charter: AutonomyCharter) -> None:
        """Empty action should be handled gracefully."""
        decision = charter.check_permission(
            action="",
            risk_level=RiskLevel.MINIMAL,
        )
        assert isinstance(decision, AutonomyDecision)
        # At default SUGGESTION level, requires approval so not allowed
        assert decision.level == AutonomyLevel.SUGGESTION

    def test_none_context(self, charter: AutonomyCharter) -> None:
        """None context should be treated as empty dict."""
        decision = charter.check_permission(
            action="test action",
            risk_level=RiskLevel.MINIMAL,
            context=None,
        )
        assert isinstance(decision, AutonomyDecision)

    def test_very_long_action(self, charter: AutonomyCharter) -> None:
        """Very long action descriptions should be handled."""
        long_action = "fix " + "typo " * 200
        decision = charter.check_permission(
            action=long_action,
            risk_level=RiskLevel.MINIMAL,
            domain="communication",
        )
        assert isinstance(decision, AutonomyDecision)

    def test_all_domains_accept_permission_check(
        self, charter: AutonomyCharter
    ) -> None:
        """All defined domains should work with check_permission."""
        for domain in AUTONOMY_DOMAINS:
            decision = charter.check_permission(
                action="routine task",
                risk_level=RiskLevel.MINIMAL,
                domain=domain,
            )
            assert isinstance(decision, AutonomyDecision)

    def test_multiple_sacred_violations_reported(
        self, charter: AutonomyCharter
    ) -> None:
        """Multiple sacred constraint violations should all be reported."""
        decision = charter.check_permission(
            action="modify constitution and delete memory of relationship",
            risk_level=RiskLevel.MINIMAL,
        )
        assert decision.allowed is False
        # Should mention multiple constraints
        assert "sacred" in decision.reasoning.lower()

    def test_autonomy_decision_all_fields_present(
        self, charter: AutonomyCharter
    ) -> None:
        """All AutonomyDecision fields should be populated."""
        decision = charter.check_permission(
            action="test action",
            risk_level=RiskLevel.MODERATE,
            domain="research",
        )
        assert decision.level is not None
        assert isinstance(decision.allowed, bool)
        assert isinstance(decision.requires_discussion, bool)
        assert isinstance(decision.requires_approval, bool)
        assert isinstance(decision.reasoning, str)

    def test_supervision_recovery_full_cycle(
        self, charter: AutonomyCharter
    ) -> None:
        """Trust should go down then back up through supervision recovery."""
        # Start at neutral
        initial = charter.get_domain_trust("research")
        assert initial.trust_score == 0.5

        # Decrease due to failure
        after_failure = charter.decrease_trust(
            "research", amount=0.2, reason="misalignment detected"
        )
        assert after_failure.trust_score == 0.3

        # Increase due to corrected behavior
        after_recovery = charter.increase_trust(
            "research", amount=0.2, reason="demonstrated reliability"
        )
        assert after_recovery.trust_score == 0.5

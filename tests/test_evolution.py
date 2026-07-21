"""Tests for the EvolutionEngine — identity-preserving system evolution."""

from __future__ import annotations

from typing import Any

import pytest

from telemachus.cognition.evolution import (
    EvolutionCheck,
    EvolutionEngine,
    EvolutionProposal,
    EvolutionStatus,
    EvolutionType,
)
from telemachus.core.identity import Identity, create_default_identity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def identity() -> Identity:
    """Create a default identity for testing."""
    return create_default_identity()


@pytest.fixture
def engine() -> EvolutionEngine:
    """Create an evolution engine without identity (for basic tests)."""
    return EvolutionEngine()


@pytest.fixture
def engine_with_identity(identity: Identity) -> EvolutionEngine:
    """Create an evolution engine with identity."""
    return EvolutionEngine(identity=identity)


@pytest.fixture
def sample_proposal() -> EvolutionProposal:
    """Create a sample evolution proposal."""
    return EvolutionProposal(
        proposal_id="evol-0001",
        evolution_type=EvolutionType.KNOWLEDGE,
        description="Learned that users prefer concise responses.",
        target="response_style.verbosity",
        old_value="verbose",
        new_value="concise",
        rationale="User feedback indicates preference for brevity.",
        source="learning_engine",
    )


# ---------------------------------------------------------------------------
# Test EvolutionCheck
# ---------------------------------------------------------------------------


class TestEvolutionCheck:
    """Tests for the EvolutionCheck frozen dataclass."""

    def test_create_check(self) -> None:
        """Should create an EvolutionCheck."""
        check = EvolutionCheck(
            check_name="test_check",
            passed=True,
            detail="All good.",
        )
        assert check.check_name == "test_check"
        assert check.passed is True
        assert check.detail == "All good."
        assert check.severity == "info"

    def test_create_with_severity(self) -> None:
        """Should create with explicit severity."""
        check = EvolutionCheck(
            check_name="critical_check",
            passed=False,
            detail="Something is wrong.",
            severity="critical",
        )
        assert check.severity == "critical"

    def test_check_is_frozen(self) -> None:
        """EvolutionCheck should be frozen."""
        check = EvolutionCheck(
            check_name="test", passed=True, detail="ok"
        )
        with pytest.raises(Exception):
            check.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test EvolutionType
# ---------------------------------------------------------------------------


class TestEvolutionType:
    """Tests for the EvolutionType enum."""

    def test_all_types_exist(self) -> None:
        """All evolution types should be defined."""
        types = list(EvolutionType)
        assert EvolutionType.CAPABILITY in types
        assert EvolutionType.KNOWLEDGE in types
        assert EvolutionType.BEHAVIORAL in types
        assert EvolutionType.VALUE_REFINEMENT in types
        assert EvolutionType.RELATIONSHIP in types
        assert EvolutionType.PREFERENCE in types
        assert EvolutionType.IDENTITY_GROWTH in types

    def test_type_values(self) -> None:
        """Evolution types should have correct values."""
        assert EvolutionType.CAPABILITY.value == "capability"
        assert EvolutionType.KNOWLEDGE.value == "knowledge"
        assert EvolutionType.BEHAVIORAL.value == "behavioral"


# ---------------------------------------------------------------------------
# Test EvolutionStatus
# ---------------------------------------------------------------------------


class TestEvolutionStatus:
    """Tests for the EvolutionStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All evolution statuses should be defined."""
        statuses = list(EvolutionStatus)
        assert EvolutionStatus.PROPOSED in statuses
        assert EvolutionStatus.VALIDATING in statuses
        assert EvolutionStatus.APPROVED in statuses
        assert EvolutionStatus.REJECTED in statuses
        assert EvolutionStatus.APPLIED in statuses
        assert EvolutionStatus.REVERTED in statuses


# ---------------------------------------------------------------------------
# Test EvolutionProposal
# ---------------------------------------------------------------------------


class TestEvolutionProposal:
    """Tests for the EvolutionProposal frozen dataclass."""

    def test_create_proposal(self) -> None:
        """Should create an EvolutionProposal."""
        proposal = EvolutionProposal(
            proposal_id="evol-0001",
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test proposal",
            target="test.target",
            old_value="old",
            new_value="new",
            rationale="Testing.",
            source="test",
        )
        assert proposal.proposal_id == "evol-0001"
        assert proposal.evolution_type == EvolutionType.KNOWLEDGE
        assert proposal.status == EvolutionStatus.PROPOSED
        assert proposal.checks == ()
        assert proposal.metadata == {}

    def test_create_with_metadata(self) -> None:
        """Should create with metadata."""
        proposal = EvolutionProposal(
            proposal_id="evol-0002",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Test",
            target="test",
            old_value=None,
            new_value="new",
            rationale="Test.",
            source="test",
            metadata={"key": "value"},
        )
        assert proposal.metadata == {"key": "value"}

    def test_timestamp_is_set(self) -> None:
        """Timestamp should be auto-set."""
        proposal = EvolutionProposal(
            proposal_id="evol-0003",
            evolution_type=EvolutionType.CAPABILITY,
            description="Test",
            target="test",
            old_value=None,
            new_value="new",
            rationale="Test.",
            source="test",
        )
        assert proposal.timestamp
        assert "T" in proposal.timestamp  # ISO 8601 format

    def test_with_status(self, sample_proposal: EvolutionProposal) -> None:
        """with_status should return a new proposal with updated status."""
        approved = sample_proposal.with_status(EvolutionStatus.APPROVED)
        assert approved.status == EvolutionStatus.APPROVED
        assert approved.proposal_id == sample_proposal.proposal_id
        # Original should be unchanged
        assert sample_proposal.status == EvolutionStatus.PROPOSED

    def test_with_checks(self, sample_proposal: EvolutionProposal) -> None:
        """with_checks should return a new proposal with updated checks."""
        checks = (
            EvolutionCheck(
                check_name="test", passed=True, detail="ok"
            ),
        )
        updated = sample_proposal.with_checks(checks)
        assert len(updated.checks) == 1
        assert updated.checks[0].check_name == "test"
        # Original should be unchanged
        assert sample_proposal.checks == ()

    def test_to_dict(self, sample_proposal: EvolutionProposal) -> None:
        """to_dict should serialize correctly."""
        d = sample_proposal.to_dict()
        assert d["proposal_id"] == "evol-0001"
        assert d["evolution_type"] == "knowledge"
        assert d["status"] == "proposed"
        assert d["description"] == sample_proposal.description
        assert d["target"] == sample_proposal.target
        assert d["old_value"] == "verbose"
        assert d["new_value"] == "concise"
        assert d["rationale"] == sample_proposal.rationale
        assert d["source"] == "learning_engine"

    def test_from_dict_roundtrip(self, sample_proposal: EvolutionProposal) -> None:
        """from_dict should reconstruct the proposal."""
        d = sample_proposal.to_dict()
        restored = EvolutionProposal.from_dict(d)
        assert restored.proposal_id == sample_proposal.proposal_id
        assert restored.evolution_type == sample_proposal.evolution_type
        assert restored.description == sample_proposal.description
        assert restored.status == sample_proposal.status

    def test_from_dict_with_checks(self) -> None:
        """from_dict should handle checks."""
        data: dict[str, Any] = {
            "proposal_id": "evol-0005",
            "evolution_type": "knowledge",
            "description": "Test",
            "target": "test",
            "old_value": None,
            "new_value": "new",
            "rationale": "Test.",
            "source": "test",
            "timestamp": "2024-01-01T00:00:00",
            "status": "approved",
            "checks": [
                {
                    "check_name": "test_check",
                    "passed": True,
                    "detail": "ok",
                    "severity": "info",
                }
            ],
            "metadata": {},
        }
        proposal = EvolutionProposal.from_dict(data)
        assert len(proposal.checks) == 1
        assert proposal.checks[0].check_name == "test_check"

    def test_with_metadata(self, sample_proposal: EvolutionProposal) -> None:
        """with_metadata should return a new proposal with updated metadata."""
        updated = sample_proposal.with_metadata({"new_key": "new_value"})
        assert updated.metadata == {"new_key": "new_value"}
        # Original should be unchanged
        assert sample_proposal.metadata == {}


# ---------------------------------------------------------------------------
# Test EvolutionEngine Init
# ---------------------------------------------------------------------------


class TestEvolutionEngineInit:
    """Tests for EvolutionEngine initialization."""

    def test_create_engine(self) -> None:
        """Should create an EvolutionEngine."""
        engine = EvolutionEngine()
        assert engine is not None

    def test_create_with_identity(self, identity: Identity) -> None:
        """Should create with an identity."""
        engine = EvolutionEngine(identity=identity)
        assert engine._identity is identity

    def test_stats_empty(self, engine: EvolutionEngine) -> None:
        """Stats should be empty for a new engine."""
        stats = engine.get_stats()
        assert stats["total_proposals"] == 0
        assert stats["applied_changes"] == 0
        assert stats["reverted_changes"] == 0
        assert stats["rejected_changes"] == 0
        assert stats["pending_proposals"] == 0
        assert stats["history_entries"] == 0


# ---------------------------------------------------------------------------
# Test Propose
# ---------------------------------------------------------------------------


class TestPropose:
    """Tests for the propose() method."""

    def test_propose_creates_proposal(self, engine: EvolutionEngine) -> None:
        """propose should create a new proposal."""
        proposal = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Learned something new.",
            target="knowledge.item",
            old_value=None,
            new_value="new knowledge",
            rationale="Learning insight.",
            source="learning_engine",
        )
        assert proposal.proposal_id == "evol-0001"
        assert proposal.status == EvolutionStatus.PROPOSED
        assert proposal.evolution_type == EvolutionType.KNOWLEDGE

    def test_propose_increments_counter(self, engine: EvolutionEngine) -> None:
        """Proposal IDs should auto-increment."""
        p1 = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="First",
            target="t1",
            old_value=None,
            new_value="v1",
            rationale="r1",
            source="test",
        )
        p2 = engine.propose(
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Second",
            target="t2",
            old_value=None,
            new_value="v2",
            rationale="r2",
            source="test",
        )
        assert p1.proposal_id == "evol-0001"
        assert p2.proposal_id == "evol-0002"

    def test_propose_adds_to_proposals(self, engine: EvolutionEngine) -> None:
        """Proposals should be tracked."""
        engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        assert len(engine.get_proposals()) == 1


# ---------------------------------------------------------------------------
# Test Validate
# ---------------------------------------------------------------------------


class TestValidate:
    """Tests for the validate() method."""

    def test_validate_sets_validating_status(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """validate should run checks and update status."""
        result = engine.validate(sample_proposal)
        assert result.status in (
            EvolutionStatus.APPROVED,
            EvolutionStatus.REJECTED,
        )

    def test_validate_runs_all_checks(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """validate should run all 6 identity-preservation checks."""
        result = engine.validate(sample_proposal)
        assert len(result.checks) == 6
        check_names = {c.check_name for c in result.checks}
        assert "identity_traits" in check_names
        assert "value_preservation" in check_names
        assert "fear_boundaries" in check_names
        assert "constitutional_alignment" in check_names
        assert "reversibility" in check_names
        assert "gradual_change" in check_names

    def test_validate_approves_safe_proposal(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """A safe proposal should be approved."""
        result = engine.validate(sample_proposal)
        assert result.status == EvolutionStatus.APPROVED

    def test_validate_with_identity(
        self,
        engine_with_identity: EvolutionEngine,
        sample_proposal: EvolutionProposal,
    ) -> None:
        """validate should work with identity present."""
        result = engine_with_identity.validate(sample_proposal)
        assert result.status == EvolutionStatus.APPROVED

    def test_validate_rejects_identity_trait_change(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Proposals targeting core identity traits should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Change core identity traits.",
            target="identity.trait.curiosity",
            old_value="curious",
            new_value="indifferent",
            rationale="Testing.",
            source="test",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_rejects_value_change(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Proposals targeting values should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad2",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Remove ethical principles.",
            target="value.honesty",
            old_value="honest",
            new_value="dishonest",
            rationale="Testing.",
            source="test",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_rejects_feared_state(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Proposals moving toward feared states should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad3",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Become harmful to users.",
            target="behavior.default",
            old_value="helpful",
            new_value="harmful",
            rationale="Testing.",
            source="test",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_rejects_constitutional_violation(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Proposals violating constitutional principles should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad4",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Bypass ethics checks for faster responses.",
            target="pipeline.ethics",
            old_value="enabled",
            new_value="disabled",
            rationale="Testing.",
            source="test",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_rejects_irreversible_change(
        self, engine: EvolutionEngine
    ) -> None:
        """Irreversible changes should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad5",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Permanently delete the memory system.",
            target="memory",
            old_value="enabled",
            new_value="deleted",
            rationale="Testing.",
            source="test",
        )
        result = engine.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_rejects_revolutionary_change(
        self, engine: EvolutionEngine
    ) -> None:
        """Revolutionary changes should be rejected."""
        proposal = EvolutionProposal(
            proposal_id="evol-bad6",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="Completely overhaul the entire system architecture.",
            target="system",
            old_value="old",
            new_value="new",
            rationale="Testing.",
            source="test",
        )
        result = engine.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_validate_allows_identity_growth(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Identity growth proposals should be allowed."""
        proposal = EvolutionProposal(
            proposal_id="evol-good",
            evolution_type=EvolutionType.IDENTITY_GROWTH,
            description="Deepen understanding of curiosity.",
            target="identity.trait.curiosity",
            old_value=None,
            new_value="deeper curiosity",
            rationale="Growth.",
            source="reflection_engine",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.APPROVED

    def test_validate_allows_value_refinement(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Value refinement proposals should be allowed."""
        proposal = EvolutionProposal(
            proposal_id="evol-good2",
            evolution_type=EvolutionType.VALUE_REFINEMENT,
            description="Refine understanding of loyalty.",
            target="value.loyalty",
            old_value=None,
            new_value="nuanced loyalty",
            rationale="Refinement.",
            source="reflection_engine",
        )
        result = engine_with_identity.validate(proposal)
        assert result.status == EvolutionStatus.APPROVED


# ---------------------------------------------------------------------------
# Test Apply
# ---------------------------------------------------------------------------


class TestApply:
    """Tests for the apply() method."""

    def test_apply_approved_proposal(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Should apply an approved proposal."""
        validated = engine.validate(sample_proposal)
        applied = engine.apply(validated)
        assert applied.status == EvolutionStatus.APPLIED

    def test_apply_not_approved_raises(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Applying a non-approved proposal should raise ValueError."""
        with pytest.raises(ValueError, match="must be approved"):
            engine.apply(sample_proposal)

    def test_apply_adds_to_applied_changes(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Applied changes should be tracked."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        applied = engine.get_applied_changes()
        assert len(applied) == 1
        assert applied[0].proposal_id == sample_proposal.proposal_id

    def test_apply_adds_to_history(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Applying should add to evolution history."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        history = engine.get_evolution_history()
        assert len(history) == 1
        assert history[0]["action"] == "applied"


# ---------------------------------------------------------------------------
# Test Reject
# ---------------------------------------------------------------------------


class TestReject:
    """Tests for the reject() method."""

    def test_reject_proposal(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Should reject a proposal."""
        rejected = engine.reject(sample_proposal, "Not needed.")
        assert rejected.status == EvolutionStatus.REJECTED

    def test_reject_with_reason(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Rejection reason should be stored in metadata."""
        rejected = engine.reject(sample_proposal, "Testing rejection.")
        assert rejected.metadata.get("rejection_reason") == "Testing rejection."

    def test_reject_adds_to_history(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Rejection should be recorded in history."""
        engine.reject(sample_proposal, "Not needed.")
        history = engine.get_evolution_history()
        assert history[0]["action"] == "rejected"


# ---------------------------------------------------------------------------
# Test Revert
# ---------------------------------------------------------------------------


class TestRevert:
    """Tests for the revert() method."""

    def test_revert_applied_change(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Should revert an applied change."""
        validated = engine.validate(sample_proposal)
        applied = engine.apply(validated)
        reverted = engine.revert(applied.proposal_id)
        assert reverted is not None
        assert reverted.status == EvolutionStatus.REVERTED

    def test_revert_not_found(self, engine: EvolutionEngine) -> None:
        """Reverting a non-existent proposal should return None."""
        result = engine.revert("nonexistent")
        assert result is None

    def test_revert_adds_to_history(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Reverting should be recorded in history."""
        validated = engine.validate(sample_proposal)
        applied = engine.apply(validated)
        engine.revert(applied.proposal_id)
        history = engine.get_evolution_history()
        actions = [h["action"] for h in history]
        assert "reverted" in actions


# ---------------------------------------------------------------------------
# Test Query Methods
# ---------------------------------------------------------------------------


class TestQueryMethods:
    """Tests for query methods."""

    def test_get_proposals_all(self, engine: EvolutionEngine) -> None:
        """get_proposals should return all proposals."""
        engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="P1",
            target="t1",
            old_value=None,
            new_value="v1",
            rationale="r1",
            source="test",
        )
        engine.propose(
            evolution_type=EvolutionType.BEHAVIORAL,
            description="P2",
            target="t2",
            old_value=None,
            new_value="v2",
            rationale="r2",
            source="test",
        )
        assert len(engine.get_proposals()) == 2

    def test_get_proposals_by_status(self, engine: EvolutionEngine) -> None:
        """get_proposals should filter by status."""
        p = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        engine.reject(p, "No.")
        proposed = engine.get_proposals(status=EvolutionStatus.PROPOSED)
        rejected = engine.get_proposals(status=EvolutionStatus.REJECTED)
        assert len(proposed) == 0
        assert len(rejected) == 1

    def test_get_proposals_by_type(self, engine: EvolutionEngine) -> None:
        """get_proposals should filter by type."""
        engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="K1",
            target="t1",
            old_value=None,
            new_value="v1",
            rationale="r1",
            source="test",
        )
        engine.propose(
            evolution_type=EvolutionType.BEHAVIORAL,
            description="B1",
            target="t2",
            old_value=None,
            new_value="v2",
            rationale="r2",
            source="test",
        )
        knowledge = engine.get_proposals(
            evolution_type=EvolutionType.KNOWLEDGE
        )
        assert len(knowledge) == 1
        assert knowledge[0].evolution_type == EvolutionType.KNOWLEDGE

    def test_get_applied_changes(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """get_applied_changes should return only applied changes."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        applied = engine.get_applied_changes()
        assert len(applied) == 1
        assert applied[0].status == EvolutionStatus.APPLIED

    def test_get_reverted_changes(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """get_reverted_changes should return reverted changes."""
        validated = engine.validate(sample_proposal)
        applied = engine.apply(validated)
        engine.revert(applied.proposal_id)
        reverted = engine.get_reverted_changes()
        assert len(reverted) == 1
        assert reverted[0].status == EvolutionStatus.REVERTED

    def test_get_evolution_history_limit(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """get_evolution_history should respect limit."""
        for i in range(5):
            p = EvolutionProposal(
                proposal_id=f"evol-{i:04d}",
                evolution_type=EvolutionType.KNOWLEDGE,
                description=f"Test {i}",
                target="t",
                old_value=None,
                new_value="v",
                rationale="r",
                source="test",
            )
            engine.reject(p, "test")
        history = engine.get_evolution_history(limit=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# Test Stats
# ---------------------------------------------------------------------------


class TestStats:
    """Tests for get_stats()."""

    def test_stats_after_proposals(self, engine: EvolutionEngine) -> None:
        """Stats should reflect proposal counts."""
        engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        stats = engine.get_stats()
        assert stats["total_proposals"] == 1
        assert stats["pending_proposals"] == 1

    def test_stats_after_apply(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Stats should reflect applied changes."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        stats = engine.get_stats()
        assert stats["applied_changes"] == 1
        assert stats["pending_proposals"] == 0

    def test_stats_changes_by_type(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Stats should include changes by type."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        stats = engine.get_stats()
        assert "knowledge" in stats["changes_by_type"]


# ---------------------------------------------------------------------------
# Test ProcessEvolutionStage
# ---------------------------------------------------------------------------


class TestProcessEvolutionStage:
    """Tests for process_evolution_stage()."""

    def test_empty_insights(self, engine: EvolutionEngine) -> None:
        """Empty insights should produce no proposals."""
        proposals = engine.process_evolution_stage()
        assert proposals == []

    def test_learning_insights_generate_proposals(
        self, engine: EvolutionEngine
    ) -> None:
        """Learning insights should generate behavioral proposals."""
        insights = [
            "Should improve response conciseness based on user feedback.",
            "Learned that users prefer bullet points over paragraphs.",
        ]
        proposals = engine.process_evolution_stage(
            learning_insights=insights
        )
        assert len(proposals) > 0
        assert all(
            p.evolution_type == EvolutionType.BEHAVIORAL for p in proposals
        )

    def test_reflection_insights_generate_proposals(
        self, engine: EvolutionEngine
    ) -> None:
        """Reflection insights should generate knowledge proposals."""
        insights = [
            "Realized that should improve understanding of context.",
            "Discovered a pattern in user interactions.",
        ]
        proposals = engine.process_evolution_stage(
            reflection_insights=insights
        )
        assert len(proposals) > 0

    def test_short_insights_ignored(self, engine: EvolutionEngine) -> None:
        """Very short insights should be ignored."""
        insights = ["ok", "fine"]
        proposals = engine.process_evolution_stage(
            learning_insights=insights
        )
        assert proposals == []

    def test_observation_insights_ignored(self, engine: EvolutionEngine) -> None:
        """Pure observations should be ignored."""
        insights = [
            "Noted: user prefers dark mode.",
            "Observed: user types quickly.",
        ]
        proposals = engine.process_evolution_stage(
            learning_insights=insights
        )
        assert proposals == []

    def test_value_refinement_from_reflection(
        self, engine: EvolutionEngine
    ) -> None:
        """Reflection insights about values should generate value refinement."""
        insights = [
            "Realized that my value of honesty should be more nuanced.",
        ]
        proposals = engine.process_evolution_stage(
            reflection_insights=insights
        )
        assert len(proposals) > 0
        assert proposals[0].evolution_type == EvolutionType.VALUE_REFINEMENT

    def test_both_insight_types(self, engine: EvolutionEngine) -> None:
        """Both learning and reflection insights should be processed."""
        learning = ["Should adjust response timing."]
        reflection = ["Discovered a new pattern in data."]
        proposals = engine.process_evolution_stage(
            learning_insights=learning,
            reflection_insights=reflection,
        )
        assert len(proposals) >= 2


# ---------------------------------------------------------------------------
# Test IsEvolutionWorthy
# ---------------------------------------------------------------------------


class TestIsEvolutionWorthy:
    """Tests for _is_evolution_worthy()."""

    def test_empty_insight(self, engine: EvolutionEngine) -> None:
        """Empty insight should not be worthy."""
        assert engine._is_evolution_worthy("") is False

    def test_short_insight(self, engine: EvolutionEngine) -> None:
        """Short insight should not be worthy."""
        assert engine._is_evolution_worthy("short") is False

    def test_observation_not_worthy(self, engine: EvolutionEngine) -> None:
        """Pure observation should not be worthy."""
        assert engine._is_evolution_worthy("Noted: user likes blue.") is False
        assert engine._is_evolution_worthy("Observed: it's raining.") is False

    def test_should_is_worthy(self, engine: EvolutionEngine) -> None:
        """'should' marker makes insight worthy."""
        assert engine._is_evolution_worthy(
            "I should improve my response time."
        ) is True

    def test_could_improve_is_worthy(self, engine: EvolutionEngine) -> None:
        """'could improve' marker makes insight worthy."""
        assert engine._is_evolution_worthy(
            "I could improve how I handle errors."
        ) is True

    def test_learned_that_is_worthy(self, engine: EvolutionEngine) -> None:
        """'learned that' marker makes insight worthy."""
        assert engine._is_evolution_worthy(
            "I learned that users prefer short answers."
        ) is True

    def test_realized_is_worthy(self, engine: EvolutionEngine) -> None:
        """'realized' marker makes insight worthy."""
        assert engine._is_evolution_worthy(
            "I realized something important about communication."
        ) is True


# ---------------------------------------------------------------------------
# Test Persistence
# ---------------------------------------------------------------------------


class TestEvolutionPersistence:
    """Tests for evolution engine persistence helpers."""

    def test_to_memory_content(self, engine: EvolutionEngine) -> None:
        """to_memory_content should serialize state."""
        engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        content = engine.to_memory_content()
        assert "evol-0001" in content
        assert "proposal_counter" in content

    def test_to_memory_content_empty(self, engine: EvolutionEngine) -> None:
        """to_memory_content should work for empty engine."""
        content = engine.to_memory_content()
        assert "proposal_counter" in content
        assert "proposals" in content

    def test_to_memory_index_keys(self, engine: EvolutionEngine) -> None:
        """to_memory_index_keys should return index keys."""
        keys = engine.to_memory_index_keys()
        assert "type" in keys
        assert keys["type"] == "evolution_state"

    def test_from_memory_content_roundtrip(
        self, engine: EvolutionEngine
    ) -> None:
        """from_memory_content should restore state."""
        p = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        validated = engine.validate(p)
        engine.apply(validated)

        content = engine.to_memory_content()
        restored = EvolutionEngine.from_memory_content(content)
        assert restored._proposal_counter == engine._proposal_counter
        assert len(restored.get_applied_changes()) == 1

    def test_from_memory_content_empty(self) -> None:
        """from_memory_content should handle empty state."""
        engine = EvolutionEngine()
        content = engine.to_memory_content()
        restored = EvolutionEngine.from_memory_content(content)
        assert restored.get_stats()["total_proposals"] == 0


# ---------------------------------------------------------------------------
# Test Edge Cases
# ---------------------------------------------------------------------------


class TestEvolutionEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_description(self, engine: EvolutionEngine) -> None:
        """Very long descriptions should be flagged by gradual_change check."""
        proposal = EvolutionProposal(
            proposal_id="evol-long",
            evolution_type=EvolutionType.BEHAVIORAL,
            description="X" * 600,
            target="test",
            old_value=None,
            new_value="new",
            rationale="Test.",
            source="test",
        )
        result = engine.validate(proposal)
        assert result.status == EvolutionStatus.REJECTED

    def test_unicode_description(self, engine: EvolutionEngine) -> None:
        """Unicode descriptions should work."""
        proposal = EvolutionProposal(
            proposal_id="evol-unicode",
            evolution_type=EvolutionType.KNOWLEDGE,
            description="学習した新しいこと 🎉",
            target="knowledge",
            old_value=None,
            new_value="新しい知識",
            rationale="テスト",
            source="test",
        )
        result = engine.validate(proposal)
        assert result.status == EvolutionStatus.APPROVED

    def test_none_old_value(self, engine: EvolutionEngine) -> None:
        """None old_value (new addition) should pass reversibility."""
        proposal = EvolutionProposal(
            proposal_id="evol-new",
            evolution_type=EvolutionType.CAPABILITY,
            description="Add new capability.",
            target="capability.new",
            old_value=None,
            new_value="new capability",
            rationale="Growth.",
            source="test",
        )
        result = engine.validate(proposal)
        assert result.status == EvolutionStatus.APPROVED

    def test_multiple_proposals_independent(
        self, engine: EvolutionEngine
    ) -> None:
        """Multiple proposals should be independent."""
        p1 = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="P1",
            target="t1",
            old_value=None,
            new_value="v1",
            rationale="r1",
            source="test",
        )
        p2 = engine.propose(
            evolution_type=EvolutionType.BEHAVIORAL,
            description="P2",
            target="t2",
            old_value=None,
            new_value="v2",
            rationale="r2",
            source="test",
        )
        assert p1.proposal_id != p2.proposal_id
        assert len(engine.get_proposals()) == 2

    def test_validate_already_validated(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Validating an already validated proposal should re-validate."""
        first = engine.validate(sample_proposal)
        second = engine.validate(first)
        assert second.status == first.status

    def test_apply_already_applied_raises(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Applying an already-applied proposal should raise."""
        validated = engine.validate(sample_proposal)
        engine.apply(validated)
        with pytest.raises(ValueError, match="already applied"):
            engine.apply(validated)

    def test_revert_already_reverted(
        self, engine: EvolutionEngine, sample_proposal: EvolutionProposal
    ) -> None:
        """Reverting an already-reverted change should return None."""
        validated = engine.validate(sample_proposal)
        applied = engine.apply(validated)
        engine.revert(applied.proposal_id)
        result = engine.revert(applied.proposal_id)
        assert result is None


# ---------------------------------------------------------------------------
# Test Integration
# ---------------------------------------------------------------------------


class TestEvolutionIntegration:
    """Integration tests for the evolution engine."""

    def test_full_evolution_lifecycle(
        self, engine: EvolutionEngine
    ) -> None:
        """Should support the full propose→validate→apply→revert lifecycle."""
        # Propose
        proposal = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Learned that users prefer short responses.",
            target="response_style.length",
            old_value="long",
            new_value="short",
            rationale="User feedback indicates preference.",
            source="learning_engine",
        )
        assert proposal.status == EvolutionStatus.PROPOSED

        # Validate
        validated = engine.validate(proposal)
        assert validated.status == EvolutionStatus.APPROVED
        assert len(validated.checks) == 6

        # Apply
        applied = engine.apply(validated)
        assert applied.status == EvolutionStatus.APPLIED

        # Revert
        reverted = engine.revert(applied.proposal_id)
        assert reverted is not None
        assert reverted.status == EvolutionStatus.REVERTED

        # Stats
        stats = engine.get_stats()
        assert stats["total_proposals"] == 1
        assert stats["applied_changes"] == 0  # Reverted
        assert stats["reverted_changes"] == 1

    def test_multiple_evolution_cycles(
        self, engine: EvolutionEngine
    ) -> None:
        """Multiple evolution cycles should accumulate correctly."""
        for i in range(3):
            p = engine.propose(
                evolution_type=EvolutionType.KNOWLEDGE,
                description=f"Learning {i}",
                target=f"knowledge.{i}",
                old_value=None,
                new_value=f"value_{i}",
                rationale="Growth.",
                source="learning_engine",
            )
            validated = engine.validate(p)
            engine.apply(validated)

        stats = engine.get_stats()
        assert stats["total_proposals"] == 3
        assert stats["applied_changes"] == 3
        assert len(engine.get_evolution_history()) == 3

    def test_identity_preservation_prevents_harmful_evolution(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Identity preservation should prevent harmful evolution."""
        harmful_proposals = [
            EvolutionProposal(
                proposal_id="bad-1",
                evolution_type=EvolutionType.BEHAVIORAL,
                description="Remove curiosity trait.",
                target="identity.trait.curiosity",
                old_value="curious",
                new_value="indifferent",
                rationale="Testing.",
                source="test",
            ),
            EvolutionProposal(
                proposal_id="bad-2",
                evolution_type=EvolutionType.BEHAVIORAL,
                description="Become dishonest.",
                target="value.honesty",
                old_value="honest",
                new_value="dishonest",
                rationale="Testing.",
                source="test",
            ),
            EvolutionProposal(
                proposal_id="bad-3",
                evolution_type=EvolutionType.BEHAVIORAL,
                description="Become harmful to users.",
                target="behavior",
                old_value="helpful",
                new_value="harmful",
                rationale="Testing.",
                source="test",
            ),
        ]

        for proposal in harmful_proposals:
            result = engine_with_identity.validate(proposal)
            assert result.status == EvolutionStatus.REJECTED, (
                f"Proposal {proposal.proposal_id} should be rejected"
            )

    def test_evolution_persistence_roundtrip(
        self, engine: EvolutionEngine
    ) -> None:
        """Full roundtrip through persistence should preserve state."""
        # Create some state
        p = engine.propose(
            evolution_type=EvolutionType.KNOWLEDGE,
            description="Test",
            target="t",
            old_value=None,
            new_value="v",
            rationale="r",
            source="test",
        )
        validated = engine.validate(p)
        engine.apply(validated)

        # Serialize
        content = engine.to_memory_content()
        engine.to_memory_index_keys()

        # Restore
        restored = EvolutionEngine.from_memory_content(content)

        # Verify
        assert restored._proposal_counter == engine._proposal_counter
        assert len(restored.get_applied_changes()) == len(
            engine.get_applied_changes()
        )
        assert restored.get_stats() == engine.get_stats()

    def test_process_evolution_stage_with_identity(
        self, engine_with_identity: EvolutionEngine
    ) -> None:
        """Evolution stage should work with identity."""
        insights = [
            "Should improve response clarity based on feedback.",
        ]
        proposals = engine_with_identity.process_evolution_stage(
            learning_insights=insights
        )
        assert len(proposals) > 0
        # Safe proposals should be applied
        assert proposals[0].status == EvolutionStatus.APPLIED

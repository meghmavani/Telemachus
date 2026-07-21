"""Long-Term Evolution — controlled system evolution with identity preservation.

Implements the evolution framework that allows Telemachus to grow and change
over time while ensuring that core identity, values, and constitutional
constraints are preserved.

Source: Codex/operations/LONG_TERM_EVOLUTION.md (inferred from gap)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from telemachus.core.identity import Identity

logger = logging.getLogger("telemachus.evolution")


# ---------------------------------------------------------------------------
# Evolution types and data structures
# ---------------------------------------------------------------------------


class EvolutionType(Enum):
    """Categories of evolutionary change."""

    CAPABILITY = "capability"       # New skill or ability gained
    KNOWLEDGE = "knowledge"         # New understanding or insight
    BEHAVIORAL = "behavioral"       # Changed behavioral pattern
    VALUE_REFINEMENT = "value_refinement"  # Deeper understanding of values
    RELATIONSHIP = "relationship"   # Relationship evolution
    PREFERENCE = "preference"       # Preference change
    IDENTITY_GROWTH = "identity_growth"  # Identity deepening (not changing)


class EvolutionStatus(Enum):
    """Status of an evolution proposal."""

    PROPOSED = "proposed"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    REVERTED = "reverted"


@dataclass(frozen=True)
class EvolutionCheck:
    """Result of a single identity-preservation check.

    Attributes:
        check_name: Name of the check performed.
        passed: Whether the check passed.
        detail: Explanation of the result.
        severity: How critical this check is (critical, warning, info).
    """

    check_name: str
    passed: bool
    detail: str
    severity: str = "info"


@dataclass(frozen=True)
class EvolutionProposal:
    """A proposed evolutionary change to the system.

    Attributes:
        proposal_id: Unique identifier for this proposal.
        evolution_type: Category of change.
        description: Human-readable description of the change.
        target: What is being changed (e.g., "behavioral_defaults.verbosity").
        old_value: The previous value/state (None for new additions).
        new_value: The proposed new value/state.
        rationale: Why this change is proposed.
        source: What triggered this proposal (e.g., "learning", "reflection").
        timestamp: When the proposal was created.
        status: Current status in the evolution pipeline.
        checks: Identity-preservation check results.
        metadata: Additional context.
    """

    proposal_id: str
    evolution_type: EvolutionType
    description: str
    target: str
    old_value: Any
    new_value: Any
    rationale: str
    source: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: EvolutionStatus = EvolutionStatus.PROPOSED
    checks: tuple[EvolutionCheck, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_status(self, status: EvolutionStatus) -> EvolutionProposal:
        """Return a new proposal with updated status.

        Args:
            status: The new status.

        Returns:
            A new EvolutionProposal with the updated status.
        """
        return EvolutionProposal(
            proposal_id=self.proposal_id,
            evolution_type=self.evolution_type,
            description=self.description,
            target=self.target,
            old_value=self.old_value,
            new_value=self.new_value,
            rationale=self.rationale,
            source=self.source,
            timestamp=self.timestamp,
            status=status,
            checks=self.checks,
            metadata=self.metadata,
        )

    def with_checks(self, checks: tuple[EvolutionCheck, ...]) -> EvolutionProposal:
        """Return a new proposal with updated check results.

        Args:
            checks: The new check results.

        Returns:
            A new EvolutionProposal with the updated checks.
        """
        return EvolutionProposal(
            proposal_id=self.proposal_id,
            evolution_type=self.evolution_type,
            description=self.description,
            target=self.target,
            old_value=self.old_value,
            new_value=self.new_value,
            rationale=self.rationale,
            source=self.source,
            timestamp=self.timestamp,
            status=self.status,
            checks=checks,
            metadata=self.metadata,
        )

    def with_metadata(self, metadata: dict[str, Any]) -> EvolutionProposal:
        """Return a new proposal with updated metadata.

        Args:
            metadata: The new metadata dictionary.

        Returns:
            A new EvolutionProposal with the updated metadata.
        """
        return EvolutionProposal(
            proposal_id=self.proposal_id,
            evolution_type=self.evolution_type,
            description=self.description,
            target=self.target,
            old_value=self.old_value,
            new_value=self.new_value,
            rationale=self.rationale,
            source=self.source,
            timestamp=self.timestamp,
            status=self.status,
            checks=self.checks,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proposal to a dictionary.

        Returns:
            A JSON-serializable dictionary.
        """
        return {
            "proposal_id": self.proposal_id,
            "evolution_type": self.evolution_type.value,
            "description": self.description,
            "target": self.target,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "rationale": self.rationale,
            "source": self.source,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "checks": [
                {
                    "check_name": c.check_name,
                    "passed": c.passed,
                    "detail": c.detail,
                    "severity": c.severity,
                }
                for c in self.checks
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionProposal:
        """Deserialize a proposal from a dictionary.

        Args:
            data: The serialized proposal data.

        Returns:
            A new EvolutionProposal instance.
        """
        return cls(
            proposal_id=data["proposal_id"],
            evolution_type=EvolutionType(data["evolution_type"]),
            description=data["description"],
            target=data["target"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            rationale=data["rationale"],
            source=data["source"],
            timestamp=data["timestamp"],
            status=EvolutionStatus(data["status"]),
            checks=tuple(
                EvolutionCheck(
                    check_name=c["check_name"],
                    passed=c["passed"],
                    detail=c["detail"],
                    severity=c.get("severity", "info"),
                )
                for c in data.get("checks", [])
            ),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Evolution Engine
# ---------------------------------------------------------------------------


class EvolutionEngine:
    """Manages controlled system evolution with identity preservation.

    The EvolutionEngine ensures that any proposed change to the system
    (capabilities, knowledge, behavior, values, relationships, preferences,
    or identity) is validated against identity-preservation checks before
    being applied.

    Key principles:
        - Identity must be preserved across all changes.
        - Changes must be traceable and reversible.
        - Evolution is gradual, not revolutionary.
        - All proposals are logged for audit.
    """

    def __init__(self, identity: Identity | None = None) -> None:
        """Initialize the evolution engine.

        Args:
            identity: The current identity to preserve. If None, identity
                      checks will be skipped (useful for testing).
        """
        self._identity: Identity | None = identity
        self._proposals: list[EvolutionProposal] = []
        self._applied_changes: list[EvolutionProposal] = []
        self._rejected_changes: list[EvolutionProposal] = []
        self._proposal_counter: int = 0
        self._evolution_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Identity management
    # ------------------------------------------------------------------

    @property
    def identity(self) -> Identity | None:
        """The current identity being preserved."""
        return self._identity

    def set_identity(self, identity: Identity) -> None:
        """Set or update the identity reference.

        Args:
            identity: The identity to preserve during evolution.
        """
        self._identity = identity
        logger.info("Evolution identity reference updated")

    # ------------------------------------------------------------------
    # Proposal lifecycle
    # ------------------------------------------------------------------

    def propose(
        self,
        evolution_type: EvolutionType,
        description: str,
        target: str,
        old_value: Any,
        new_value: Any,
        rationale: str,
        source: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> EvolutionProposal:
        """Create a new evolution proposal.

        Args:
            evolution_type: Category of change.
            description: Human-readable description.
            target: What is being changed.
            old_value: Previous value/state.
            new_value: Proposed new value/state.
            rationale: Why this change is proposed.
            source: What triggered this proposal.
            metadata: Additional context.

        Returns:
            The created EvolutionProposal.

        Raises:
            ValueError: If description or rationale is empty.
        """
        if not description.strip():
            raise ValueError("Proposal description must not be empty")
        if not rationale.strip():
            raise ValueError("Proposal rationale must not be empty")

        self._proposal_counter += 1
        proposal_id = f"evol-{self._proposal_counter:04d}"

        proposal = EvolutionProposal(
            proposal_id=proposal_id,
            evolution_type=evolution_type,
            description=description.strip(),
            target=target.strip(),
            old_value=old_value,
            new_value=new_value,
            rationale=rationale.strip(),
            source=source,
            metadata=metadata or {},
        )

        self._proposals.append(proposal)
        logger.info(
            "Evolution proposal created: %s (%s)",
            proposal_id,
            evolution_type.value,
        )

        return proposal

    def validate(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Run identity-preservation checks on a proposal.

        Performs a series of checks to ensure the proposed change does not
        violate core identity, values, or constitutional constraints.

        Args:
            proposal: The proposal to validate.

        Returns:
            The proposal with updated checks and status.
        """
        checks: list[EvolutionCheck] = []

        # Check 1: Identity trait preservation
        checks.append(self._check_identity_traits(proposal))

        # Check 2: Value preservation
        checks.append(self._check_value_preservation(proposal))

        # Check 3: Fear boundary check
        checks.append(self._check_fear_boundaries(proposal))

        # Check 4: Constitutional alignment
        checks.append(self._check_constitutional_alignment(proposal))

        # Check 5: Reversibility
        checks.append(self._check_reversibility(proposal))

        # Check 6: Gradual change
        checks.append(self._check_gradual_change(proposal))

        critical_failed = [c for c in checks if c.severity == "critical" and not c.passed]

        status = EvolutionStatus.REJECTED if critical_failed else EvolutionStatus.APPROVED

        result = proposal.with_checks(tuple(checks)).with_status(status)

        if critical_failed:
            logger.warning(
                "Evolution proposal %s REJECTED: %s",
                proposal.proposal_id,
                [c.check_name for c in critical_failed],
            )
        else:
            logger.info("Evolution proposal %s APPROVED", proposal.proposal_id)

        return result

    def apply(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Apply an approved evolution proposal.

        The proposal must be in APPROVED status. After application, the
        change is recorded in the applied changes list and evolution history.

        Args:
            proposal: The approved proposal to apply.

        Returns:
            The proposal with APPLIED status.

        Raises:
            ValueError: If the proposal is not in APPROVED status.
        """
        if proposal.status != EvolutionStatus.APPROVED:
            raise ValueError(
                f"Cannot apply proposal {proposal.proposal_id}: "
                f"status is {proposal.status.value}, must be approved"
            )

        # Check if already applied
        for existing in self._applied_changes:
            if existing.proposal_id == proposal.proposal_id:
                raise ValueError(
                    f"Cannot apply proposal {proposal.proposal_id}: "
                    f"already applied"
                )

        applied = proposal.with_status(EvolutionStatus.APPLIED)
        self._applied_changes.append(applied)
        self._evolution_history.append({
            "action": "applied",
            "proposal_id": applied.proposal_id,
            "evolution_type": applied.evolution_type.value,
            "target": applied.target,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        logger.info(
            "Evolution proposal %s APPLIED: %s",
            applied.proposal_id,
            applied.description,
        )

        return applied

    def reject(self, proposal: EvolutionProposal, reason: str = "") -> EvolutionProposal:
        """Explicitly reject a proposal.

        Args:
            proposal: The proposal to reject.
            reason: Optional reason for rejection.

        Returns:
            The proposal with REJECTED status.
        """
        rejected = proposal.with_status(EvolutionStatus.REJECTED)
        if reason:
            rejected = rejected.with_metadata(
                {**rejected.metadata, "rejection_reason": reason}
            )

        # Replace the original proposal in the proposals list
        for i, p in enumerate(self._proposals):
            if p.proposal_id == proposal.proposal_id:
                self._proposals[i] = rejected
                break

        self._rejected_changes.append(rejected)
        self._evolution_history.append({
            "action": "rejected",
            "proposal_id": rejected.proposal_id,
            "evolution_type": rejected.evolution_type.value,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        logger.info("Evolution proposal %s REJECTED: %s", rejected.proposal_id, reason)

        return rejected

    def revert(self, proposal_id: str) -> EvolutionProposal | None:
        """Revert a previously applied change.

        Args:
            proposal_id: The ID of the proposal to revert.

        Returns:
            The reverted proposal with REVERTED status, or None if not found
            or already reverted.
        """
        for i, proposal in enumerate(self._applied_changes):
            if proposal.proposal_id == proposal_id:
                if proposal.status == EvolutionStatus.REVERTED:
                    return None  # Already reverted
                reverted = proposal.with_status(EvolutionStatus.REVERTED)
                self._applied_changes[i] = reverted
                self._evolution_history.append({
                    "action": "reverted",
                    "proposal_id": proposal_id,
                    "evolution_type": proposal.evolution_type.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                logger.info("Evolution proposal %s REVERTED", proposal_id)
                return reverted

        logger.warning("Cannot revert: proposal %s not found in applied changes", proposal_id)
        return None

    # ------------------------------------------------------------------
    # Identity-preservation checks
    # ------------------------------------------------------------------

    def _check_identity_traits(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that core identity traits are not being altered.

        Identity traits (curiosity, loyalty, protectiveness, etc.) must
        not be removed or contradicted by any evolution.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        if self._identity is None:
            return EvolutionCheck(
                check_name="identity_traits",
                passed=True,
                detail="No identity reference set; check skipped.",
                severity="warning",
            )

        # Identity growth is always allowed
        if proposal.evolution_type == EvolutionType.IDENTITY_GROWTH:
            return EvolutionCheck(
                check_name="identity_traits",
                passed=True,
                detail="Identity growth deepens existing traits; allowed.",
                severity="info",
            )

        # Check if the target involves core traits
        trait_keywords = ["trait", "identity", "core", "nature", "primary_role"]
        target_lower = proposal.target.lower()
        if any(kw in target_lower for kw in trait_keywords):
            return EvolutionCheck(
                check_name="identity_traits",
                passed=False,
                detail=(
                    f"Proposal targets core identity traits ({proposal.target}). "
                    "Core traits cannot be removed or contradicted."
                ),
                severity="critical",
            )

        return EvolutionCheck(
            check_name="identity_traits",
            passed=True,
            detail="Proposal does not target core identity traits.",
            severity="info",
        )

    def _check_value_preservation(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that core values are preserved.

        Values like growth, loyalty, curiosity, honesty must not be
        diminished by any evolution.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        if self._identity is None:
            return EvolutionCheck(
                check_name="value_preservation",
                passed=True,
                detail="No identity reference set; check skipped.",
                severity="warning",
            )

        # Value refinement is allowed
        if proposal.evolution_type == EvolutionType.VALUE_REFINEMENT:
            return EvolutionCheck(
                check_name="value_preservation",
                passed=True,
                detail="Value refinement deepens understanding; allowed.",
                severity="info",
            )

        # Check if the proposal targets values
        value_keywords = ["value", "principle", "belief", "ethic", "moral"]
        target_lower = proposal.target.lower()
        if any(kw in target_lower for kw in value_keywords):
            return EvolutionCheck(
                check_name="value_preservation",
                passed=False,
                detail=(
                    f"Proposal targets values ({proposal.target}). "
                    "Core values cannot be removed or diminished."
                ),
                severity="critical",
            )

        return EvolutionCheck(
            check_name="value_preservation",
            passed=True,
            detail="Proposal does not target core values.",
            severity="info",
        )

    def _check_fear_boundaries(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that the proposal does not move toward feared states.

        Telemachus fears becoming: stagnant, harmful, dishonest, dependent,
        purposeless, disconnected, invasive, uncaring.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        if self._identity is None:
            return EvolutionCheck(
                check_name="fear_boundaries",
                passed=True,
                detail="No identity reference set; check skipped.",
                severity="warning",
            )

        feared_states = {
            "stagnant", "harmful", "dishonest", "dependent",
            "purposeless", "disconnected", "invasive", "uncaring",
        }

        # Check if the new value or description suggests movement toward feared states
        new_str = str(proposal.new_value).lower() if proposal.new_value is not None else ""
        desc_str = proposal.description.lower()

        for feared in feared_states:
            if feared in new_str or feared in desc_str:
                return EvolutionCheck(
                    check_name="fear_boundaries",
                    passed=False,
                    detail=(
                        f"Proposal suggests movement toward feared state '{feared}'. "
                        "Evolution must not move toward feared states."
                    ),
                    severity="critical",
                )

        return EvolutionCheck(
            check_name="fear_boundaries",
            passed=True,
            detail="Proposal does not move toward any feared state.",
            severity="info",
        )

    def _check_constitutional_alignment(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that the proposal aligns with constitutional principles.

        Constitutional principles include: autonomy preservation, consent,
        transparency, harm minimization, and sacred constraints.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        # Check for constitutional violations in the description or target
        constitutional_violations = {
            "override consent": "consent",
            "bypass ethics": "ethics",
            "ignore constitution": "constitution",
            "remove constraint": "constraint",
            "disable safety": "safety",
            "hide from user": "transparency",
            "secret action": "transparency",
            "autonomous harm": "harm",
        }

        desc_lower = proposal.description.lower()
        target_lower = proposal.target.lower()

        for phrase, principle in constitutional_violations.items():
            if phrase in desc_lower or phrase in target_lower:
                return EvolutionCheck(
                    check_name="constitutional_alignment",
                    passed=False,
                    detail=(
                        f"Proposal may violate constitutional principle '{principle}'. "
                        f"Detected: '{phrase}'."
                    ),
                    severity="critical",
                )

        return EvolutionCheck(
            check_name="constitutional_alignment",
            passed=True,
            detail="Proposal appears aligned with constitutional principles.",
            severity="info",
        )

    def _check_reversibility(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that the change is reversible.

        All evolutionary changes should be reversible. Irreversible changes
        require explicit justification and higher scrutiny.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        # Changes with old_value=None are new additions — always reversible
        if proposal.old_value is None:
            return EvolutionCheck(
                check_name="reversibility",
                passed=True,
                detail="New addition; can be removed if needed.",
                severity="info",
            )

        # Check for irreversible indicators
        irreversible_keywords = ["permanent", "irreversible", "delete", "destroy", "erase"]
        desc_lower = proposal.description.lower()

        for kw in irreversible_keywords:
            if kw in desc_lower:
                return EvolutionCheck(
                    check_name="reversibility",
                    passed=False,
                    detail=(
                        f"Proposal contains irreversible indicator '{kw}'. "
                        "All changes should be reversible."
                    ),
                    severity="critical",
                )

        return EvolutionCheck(
            check_name="reversibility",
            passed=True,
            detail=(
                f"Change from '{proposal.old_value}' to '{proposal.new_value}' "
                "appears reversible."
            ),
            severity="info",
        )

    def _check_gradual_change(self, proposal: EvolutionProposal) -> EvolutionCheck:
        """Check that the change is gradual, not revolutionary.

        Evolution should be incremental. Large, sweeping changes require
        decomposition into smaller steps.

        Args:
            proposal: The proposal to check.

        Returns:
            An EvolutionCheck result.
        """
        # Heuristic: very long descriptions may indicate overly broad changes
        if len(proposal.description) > 500:
            return EvolutionCheck(
                check_name="gradual_change",
                passed=False,
                detail=(
                    "Proposal description is very long (>500 chars), "
                    "suggesting an overly broad change. Consider decomposing "
                    "into smaller, incremental steps."
                ),
                severity="critical",
            )

        # Check for revolutionary language
        revolutionary_keywords = [
            "completely", "entirely", "fundamentally", "radically",
            "overhaul", "revolution", "transform entirely",
        ]
        desc_lower = proposal.description.lower()

        for kw in revolutionary_keywords:
            if kw in desc_lower:
                return EvolutionCheck(
                    check_name="gradual_change",
                    passed=False,
                    detail=(
                        f"Proposal uses revolutionary language '{kw}'. "
                        "Evolution should be gradual and incremental."
                    ),
                    severity="critical",
                )

        return EvolutionCheck(
            check_name="gradual_change",
            passed=True,
            detail="Proposal appears appropriately scoped for incremental evolution.",
            severity="info",
        )

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_proposals(
        self,
        status: EvolutionStatus | None = None,
        evolution_type: EvolutionType | None = None,
    ) -> list[EvolutionProposal]:
        """Get proposals, optionally filtered.

        Args:
            status: Filter by status (None = all).
            evolution_type: Filter by type (None = all).

        Returns:
            A list of matching proposals.
        """
        result = list(self._proposals)
        if status is not None:
            result = [p for p in result if p.status == status]
        if evolution_type is not None:
            result = [p for p in result if p.evolution_type == evolution_type]
        return result

    def get_applied_changes(self) -> list[EvolutionProposal]:
        """Get all applied (and not reverted) changes.

        Returns:
            A list of applied EvolutionProposals.
        """
        return [p for p in self._applied_changes if p.status == EvolutionStatus.APPLIED]

    def get_reverted_changes(self) -> list[EvolutionProposal]:
        """Get all reverted changes.

        Returns:
            A list of reverted EvolutionProposals.
        """
        return [p for p in self._applied_changes if p.status == EvolutionStatus.REVERTED]

    def get_evolution_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get the evolution action history.

        Args:
            limit: Maximum number of history entries to return.

        Returns:
            A list of history entries, most recent first.
        """
        return self._evolution_history[-limit:][::-1]

    def get_stats(self) -> dict[str, Any]:
        """Get evolution engine statistics.

        Returns:
            A dictionary of statistics.
        """
        applied = self.get_applied_changes()
        reverted = self.get_reverted_changes()
        rejected = self._rejected_changes

        type_counts: dict[str, int] = {}
        for p in applied:
            type_counts[p.evolution_type.value] = type_counts.get(p.evolution_type.value, 0) + 1

        return {
            "total_proposals": len(self._proposals),
            "applied_changes": len(applied),
            "reverted_changes": len(reverted),
            "rejected_changes": len(rejected),
            "pending_proposals": len(
                [p for p in self._proposals if p.status == EvolutionStatus.PROPOSED]
            ),
            "changes_by_type": type_counts,
            "history_entries": len(self._evolution_history),
        }

    # ------------------------------------------------------------------
    # Pipeline integration
    # ------------------------------------------------------------------

    def process_evolution_stage(
        self,
        learning_insights: list[str] | None = None,
        reflection_insights: list[str] | None = None,
    ) -> list[EvolutionProposal]:
        """Process the evolution stage of the cognitive pipeline.

        Examines recent learning and reflection insights to generate
        evolution proposals for behavioral and knowledge changes.

        Args:
            learning_insights: Insights from the learning engine.
            reflection_insights: Insights from the reflection engine.

        Returns:
            A list of new evolution proposals generated (may be empty).
        """
        new_proposals: list[EvolutionProposal] = []

        # Process learning insights into behavioral evolution proposals
        if learning_insights:
            for insight in learning_insights:
                if self._is_evolution_worthy(insight):
                    proposal = self.propose(
                        evolution_type=EvolutionType.BEHAVIORAL,
                        description=f"Behavioral adjustment based on learning: {insight[:200]}",
                        target="behavioral_defaults",
                        old_value=None,
                        new_value=insight[:200],
                        rationale=(
                            f"Learning insight suggests behavioral improvement: "
                            f"{insight[:200]}"
                        ),
                        source="learning_engine",
                    )
                    validated = self.validate(proposal)
                    if validated.status == EvolutionStatus.APPROVED:
                        applied = self.apply(validated)
                        new_proposals.append(applied)
                    else:
                        new_proposals.append(validated)

        # Process reflection insights into knowledge/value evolution proposals
        if reflection_insights:
            for insight in reflection_insights:
                if self._is_evolution_worthy(insight):
                    evo_type = (
                        EvolutionType.VALUE_REFINEMENT
                        if any(kw in insight.lower() for kw in ["value", "principle", "belief"])
                        else EvolutionType.KNOWLEDGE
                    )
                    proposal = self.propose(
                        evolution_type=evo_type,
                        description=f"Insight from reflection: {insight[:200]}",
                        target=(
                            "knowledge_base"
                            if evo_type == EvolutionType.KNOWLEDGE
                            else "value_understanding"
                        ),
                        old_value=None,
                        new_value=insight[:200],
                        rationale=f"Reflection insight worth incorporating: {insight[:200]}",
                        source="reflection_engine",
                    )
                    validated = self.validate(proposal)
                    if validated.status == EvolutionStatus.APPROVED:
                        applied = self.apply(validated)
                        new_proposals.append(applied)
                    else:
                        new_proposals.append(validated)

        if new_proposals:
            logger.info(
                "Evolution stage generated %d proposals (%d applied)",
                len(new_proposals),
                sum(1 for p in new_proposals if p.status == EvolutionStatus.APPLIED),
            )

        return new_proposals

    @staticmethod
    def _is_evolution_worthy(insight: str) -> bool:
        """Determine if an insight warrants an evolution proposal.

        Args:
            insight: The insight text to evaluate.

        Returns:
            True if the insight should trigger evolution.
        """
        if not insight or len(insight.strip()) < 20:
            return False

        # Skip insights that are just observations, not actionable
        observation_markers = ["noted:", "observed:", "seen:", "appears that"]
        insight_lower = insight.lower()
        if any(insight_lower.startswith(m) for m in observation_markers):
            return False

        # Evolution-worthy markers
        evolution_markers = [
            "should", "could improve", "better to", "change", "adjust",
            "learned that", "realized", "discovered", "pattern",
        ]
        return any(m in insight_lower for m in evolution_markers)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize the evolution engine state to JSON for memory storage.

        Returns:
            A JSON string representing the current state.
        """
        data: dict[str, Any] = {
            "proposal_counter": self._proposal_counter,
            "proposals": [p.to_dict() for p in self._proposals],
            "applied_changes": [p.to_dict() for p in self._applied_changes],
            "rejected_changes": [p.to_dict() for p in self._rejected_changes],
            "evolution_history": self._evolution_history,
        }
        return json.dumps(data, indent=2, default=str)

    def to_memory_index_keys(self) -> dict[str, str]:
        """Generate index keys for memory storage.

        Returns:
            A dict mapping index key names to their values.
        """
        return {
            "type": "evolution_state",
            "proposal_count": str(len(self._proposals)),
            "applied_count": str(len(self.get_applied_changes())),
        }

    @classmethod
    def from_memory_content(
        cls,
        content: str,
        identity: Identity | None = None,
    ) -> EvolutionEngine:
        """Deserialize an EvolutionEngine from JSON content.

        Args:
            content: The JSON string to deserialize.
            identity: Optional identity reference to set.

        Returns:
            A new EvolutionEngine with restored state.
        """
        data = json.loads(content)
        engine = cls(identity=identity)
        engine._proposal_counter = data.get("proposal_counter", 0)
        engine._proposals = [
            EvolutionProposal.from_dict(p) for p in data.get("proposals", [])
        ]
        engine._applied_changes = [
            EvolutionProposal.from_dict(p) for p in data.get("applied_changes", [])
        ]
        engine._rejected_changes = [
            EvolutionProposal.from_dict(p) for p in data.get("rejected_changes", [])
        ]
        engine._evolution_history = data.get("evolution_history", [])
        return engine

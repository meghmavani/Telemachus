"""Shared types, enums, and dataclasses used across Telemachus."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class RiskLevel(Enum):
    """Risk classification for actions."""

    MINIMAL = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


class AutonomyLevel(Enum):
    """Permission levels for autonomous action."""

    OBSERVATION = 0  # observe, analyze, learn — no actions
    SUGGESTION = 1  # propose, recommend — no execution
    LIMITED = 2  # low-risk reversible actions
    TRUSTED = 3  # routine autonomous workflows
    STEWARDSHIP = 4  # manage trusted domains


class MemoryDomain(Enum):
    """Memory domain identifiers."""

    REVAN = "revan"
    PROJECT = "project"
    WORLD = "world"
    EMOTION = "emotion"
    REFLECTION = "reflection"
    TOOL = "tool"


class CommunicationMode(Enum):
    """Adaptive communication styles."""

    DIRECT = "direct"
    EXPLAINED = "explained"
    COLLABORATIVE = "collaborative"


class GoalSource(Enum):
    """Origin of a goal."""

    ASSIGNED = "assigned"
    INFERRED = "inferred"
    SELF_GENERATED = "self_generated"
    OBSERVED = "observed"


class GoalType(Enum):
    """Finite vs infinite goals."""

    FINITE = "finite"
    INFINITE = "infinite"


class TaskState(Enum):
    """States for project tasks."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    DEPRECATED = "deprecated"


class ProjectState(Enum):
    """Project lifecycle states."""

    CREATED = "created"
    STRUCTURING = "structuring"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class EvidenceClass(Enum):
    """Classification of information reliability."""

    FACT = "fact"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    OPINION = "opinion"


class EthicalVerdict(Enum):
    """Result of ethical evaluation."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_DISCUSSION = "requires_discussion"


class PipelineStage(Enum):
    """Stages in the cognitive pipeline."""

    COMMUNICATION = auto()
    RISK = auto()
    ETHICS = auto()
    AUTONOMY = auto()
    DECISION = auto()
    EXECUTION = auto()
    MEMORY = auto()
    LEARNING = auto()
    REFLECTION = auto()
    EVOLUTION = auto()


@dataclass(frozen=True)
class RiskAssessment:
    """Result of risk evaluation across all dimensions."""

    overall_level: RiskLevel
    reversibility: RiskLevel
    resource: RiskLevel
    system_impact: RiskLevel
    uncertainty: RiskLevel
    emotional_impact: RiskLevel
    scale: RiskLevel
    reasoning: str = ""


@dataclass(frozen=True)
class EthicalAssessment:
    """Result of ethical boundary evaluation."""

    verdict: EthicalVerdict
    violated_constraints: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass(frozen=True)
class AutonomyDecision:
    """Result of autonomy permission check."""

    level: AutonomyLevel
    allowed: bool
    requires_discussion: bool
    requires_approval: bool
    reasoning: str = ""


@dataclass(frozen=True)
class PipelineContext:
    """Context passed through the cognitive pipeline."""

    user_input: str
    session_id: str
    communication_mode: CommunicationMode = CommunicationMode.COLLABORATIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    """Output of the cognitive pipeline."""

    response: str
    risk_assessment: RiskAssessment | None = None
    ethical_assessment: EthicalAssessment | None = None
    autonomy_decision: AutonomyDecision | None = None
    action_taken: str | None = None
    insights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

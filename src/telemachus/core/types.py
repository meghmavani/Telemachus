"""Shared types, enums, and dataclasses used across Telemachus."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from telemachus.core.codex import ProtectedConstraint


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


# ---------------------------------------------------------------------------
# Execution boundary (Stage 6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionRequest:
    """A caller-supplied request to execute a specific tool.

    This is an execution-boundary contract, not a planning architecture.
    Callers that want Stage 6 to do work place one of these at
    ``PipelineContext.metadata["action"]``. Nothing in the pipeline
    currently produces one on its own — that is future, out-of-scope work
    (planning integration, the Event Loop, or an LLM-driven planner).

    Attributes:
        tool: The registered tool name to invoke.
        arguments: Keyword arguments passed to the tool's execute/validate.
        description: Optional human-readable description of the action,
            for logging and trace readability.
        affects: Which constitutional Protected Constraints this action
            touches, declared explicitly by the caller. Constitutional
            validation never infers this from ``tool``, ``arguments``, or
            ``description`` — an action that declares nothing is treated
            as constitutionally unremarkable (see
            ``Constitution.validate_action()``).

            KNOWN BOUNDED LIMITATION: this is a self-declared capability,
            not an independently verified one. A caller (today, only
            hand-constructed test/production callers — nothing in the
            pipeline currently produces an ActionRequest on its own) that
            omits a Protected Constraint it actually touches bypasses
            constitutional validation for that action. This is the same
            trust model ``Tool.sacred_domains_affected`` already uses,
            and no ACTIVE or AUTONOMOUS tool exists yet to exploit it.
            The proper fix — a tool-declared, independently-verified
            capability envelope — is deliberately out of scope for this
            milestone.
        human_authorized: Whether a human has explicitly authorized this
            action against the Protected Constraints it declares in
            ``affects``. Also an explicit declaration, not inferred.
    """

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    affects: frozenset[ProtectedConstraint] = frozenset()
    human_authorized: bool = False


class ConstitutionalVerdict(Enum):
    """The classified result of constitutional validation.

    Answers only "is this categorically forbidden by the Constitution?"
    — see ``Constitution.validate_action()``.
    """

    NOT_APPLICABLE = "not_applicable"  # Action declares no Protected Constraint.
    PERMITTED = "permitted"  # Declared and explicitly human-authorized.
    VIOLATION = "violation"  # Declared, unauthorized, and authority is loaded.
    AUTHORITY_UNAVAILABLE = "authority_unavailable"  # Declared, but no Codex authority loaded.


@dataclass(frozen=True)
class ConstitutionalAssessment:
    """The result of ``Constitution.validate_action()``.

    Attributes:
        verdict: The classified result.
        violated: Which Protected Constraints are implicated, in
            ``ProtectedConstraint`` declaration order. Empty unless
            ``verdict`` is ``VIOLATION`` or ``AUTHORITY_UNAVAILABLE``.
        reasoning: Human-readable explanation, quoting the Codex-derived
            definition where available.
    """

    verdict: ConstitutionalVerdict
    violated: tuple[ProtectedConstraint, ...] = ()
    reasoning: str = ""


class ExecutionOutcome(Enum):
    """The classified result of Stage 6 (Execution).

    Every outcome is reachable without the pipeline ever raising: Stage 6
    classifies and returns, it never propagates an exception.
    """

    NO_ACTION = "no_action"  # No ActionRequest was supplied.
    DENIED_CONSTITUTION = "denied_constitution"  # Constitutional gate refused execution.
    DENIED_AUTONOMY = "denied_autonomy"  # Autonomy gate refused execution.
    TOOL_NOT_FOUND = "tool_not_found"  # No tool registered under that name.
    DENIED_TOOL = "denied_tool"  # Registry-level permission check refused.
    INVALID_ARGUMENTS = "invalid_arguments"  # Tool validation failed.
    TOOL_FAILED = "tool_failed"  # Tool ran and reported failure.
    TOOL_ERROR = "tool_error"  # Tool raised; the registry contained it.
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class ExecutionRecord:
    """What Stage 6 (Execution) actually did, for tracing and Tool Memory.

    Persisted to ``MemoryDomain.TOOL`` when a memory store is configured
    (codex/operations/MEMORY_ARCHITECTURE.md, "Tool Memory": tool usage
    history, performance metrics, reliability patterns, success/failure
    rates).

    Attributes:
        outcome: The classified result.
        tool: The tool name requested, if an ActionRequest was supplied.
        arguments: The arguments the tool was invoked with.
        output: The tool's output on success, if any.
        error: A human-readable error message, for any non-success outcome.
        duration_ms: Wall-clock time spent inside the registry call.
        autonomy_level: The AutonomyLevel name in effect at execution time.
        violated_constraints: Canonical ``ProtectedConstraint`` values
            implicated, if ``outcome`` is ``DENIED_CONSTITUTION``.
    """

    outcome: ExecutionOutcome
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    autonomy_level: str | None = None
    violated_constraints: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Pipeline trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageRecord:
    """The outcome of a single pipeline stage, for tracing.

    Attributes:
        stage: Which stage this record describes.
        status: Whether the stage completed without an internal error.
        data: The stage's payload on success (an assessment, a decision,
            a selected option, ...). Named ``data``, not ``failure`` —
            it holds success information on nearly every stage.
        error: An error message, if the stage failed internally.
        blocked: Whether this stage blocked the pipeline.
        blocked_reason: Why, if ``blocked`` is True.
    """

    stage: PipelineStage
    status: bool
    data: Any = None
    error: str | None = None
    blocked: bool = False
    blocked_reason: str = ""


@dataclass(frozen=True)
class ObservationProvenance:
    """Identity of the Runtime Observation a pipeline run was invoked for.

    Identity only — the Observation itself remains the source of truth and
    is never copied into the trace. Absent (``PipelineTrace.observation is
    None``) for any run not driven by an Observation, e.g. synchronous chat.

    Attributes:
        observation_id: The originating Observation's identifier.
        observation_type: Its category label.
        source: Its origin, as the canonical string value.
    """

    observation_id: str
    observation_type: str
    source: str


@dataclass(frozen=True)
class PipelineTrace:
    """A complete, persistable record of one pipeline run.

    Attributes:
        trace_id: Unique identifier for this trace.
        session_id: The session this run belongs to.
        started_at: Unix timestamp when processing began.
        ended_at: Unix timestamp when processing concluded (success or
            block).
        stages: Every StageRecord produced, in execution order.
        completed: True only if every stage ran without being blocked.
        blocked_at: Which stage blocked the pipeline, if any.
        blocked_reason: Why it blocked, if ``blocked_at`` is set.
        execution: The Stage 6 ExecutionRecord, if execution ran.
        observation: Provenance of the Observation that triggered this
            run, or None if the run was not Observation-driven.
    """

    trace_id: str
    session_id: str
    started_at: float
    ended_at: float
    stages: tuple[StageRecord, ...] = ()
    completed: bool = False
    blocked_at: PipelineStage | None = None
    blocked_reason: str = ""
    execution: ExecutionRecord | None = None
    observation: ObservationProvenance | None = None

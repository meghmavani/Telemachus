"""Cognitive Pipeline — the full input→output loop.

Wires together all governance and memory stages into a single processing
pipeline. Each stage executes in order; no downstream stage may execute
before upstream validation completes.

Pipeline stages:
    1. Communication (stub — full implementation in Milestone 7)
    2. Risk evaluation
    3. Ethical boundary check
    4. Autonomy permission check
    5. Decision framework (option ranking)
    6. Execution — runs an approved ActionRequest through the ToolRegistry
    7. Memory storage
    8. Learning (experience-based behavioral improvement)
    9. Reflection (self-analysis and insight extraction)
    10. Evolution (stub — full implementation in Milestone 11)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from telemachus.cognition.evolution import EvolutionEngine, EvolutionStatus
from telemachus.cognition.learning import LearningEngine
from telemachus.cognition.reflection import ReflectionEngine
from telemachus.core.codex import ProtectedConstraint
from telemachus.core.constitution import Constitution
from telemachus.core.types import (
    ActionRequest,
    AutonomyDecision,
    AutonomyLevel,
    CommunicationMode,
    ConstitutionalAssessment,
    ConstitutionalVerdict,
    EthicalAssessment,
    EthicalVerdict,
    ExecutionOutcome,
    ExecutionRecord,
    MemoryDomain,
    PipelineContext,
    PipelineResult,
    PipelineStage,
    PipelineTrace,
    RiskAssessment,
    RiskLevel,
    StageRecord,
)
from telemachus.governance.autonomy import AutonomyCharter
from telemachus.governance.decision import DecisionFramework
from telemachus.governance.ethics import EthicalBoundaryEngine
from telemachus.governance.risk import RiskEvaluator
from telemachus.memory.store import MemoryStore
from telemachus.tools.base import ToolResult
from telemachus.tools.registry import ToolRegistry

logger = logging.getLogger("telemachus.pipeline")


# ---------------------------------------------------------------------------
# Trace accumulation
# ---------------------------------------------------------------------------


@dataclass
class _TraceBuilder:
    """Mutable accumulator for one pipeline run's PipelineTrace.

    Stages are appended as they execute; ``build()`` snapshots the
    accumulated state into an immutable PipelineTrace. This is called
    twice per run: once at Stage 7 to obtain the snapshot that gets
    persisted (stages 1-7 only — Learning/Reflection/Evolution haven't
    run yet at that point, so ``completed`` is honestly False there),
    and once more at the true end of ``process()`` (or at a block) to
    produce the trace exposed via ``CognitivePipeline.last_trace``.
    """

    trace_id: str
    session_id: str
    started_at: float
    stages: list[StageRecord] = field(default_factory=list)
    completed: bool = False
    blocked_at: PipelineStage | None = None
    blocked_reason: str = ""
    execution: ExecutionRecord | None = None

    def add_stage(self, record: StageRecord) -> None:
        """Append a stage's result to the trace."""
        self.stages.append(record)

    def block(self, stage: PipelineStage, reason: str) -> None:
        """Mark the pipeline as blocked at a specific stage, preserving why."""
        self.blocked_at = stage
        self.blocked_reason = reason
        self.completed = False

    def build(self, ended_at: float) -> PipelineTrace:
        """Snapshot the current accumulator state into a PipelineTrace."""
        return PipelineTrace(
            trace_id=self.trace_id,
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=ended_at,
            stages=tuple(self.stages),
            completed=self.completed,
            blocked_at=self.blocked_at,
            blocked_reason=self.blocked_reason,
            execution=self.execution,
        )


# ---------------------------------------------------------------------------
# Defensive serialization for persistence
# ---------------------------------------------------------------------------


def _safe_value(value: Any) -> Any:
    """Best-effort JSON-safe conversion for trace/execution payloads.

    Primitives and enums convert directly; anything else that survives a
    trial ``json.dumps`` passes through unchanged; anything that doesn't
    degrades to ``repr()`` rather than raising. This is what keeps a
    non-serializable stage payload from destroying the Stage 7 memory
    write it would otherwise be part of.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_value(v) for k, v in value.items()}
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)
    else:
        return value


def _stage_record_to_dict(record: StageRecord) -> dict[str, Any]:
    """Convert one StageRecord into a JSON-safe dict for persistence."""
    return {
        "stage": record.stage.name,
        "status": record.status,
        "data": _safe_value(record.data),
        "error": record.error,
        "blocked": record.blocked,
        "blocked_reason": record.blocked_reason,
    }


def _execution_record_to_dict(record: ExecutionRecord) -> dict[str, Any]:
    """Convert an ExecutionRecord into a JSON-safe dict for persistence."""
    return {
        "outcome": record.outcome.value,
        "tool": record.tool,
        "arguments": _safe_value(record.arguments),
        "output": _safe_value(record.output),
        "error": record.error,
        "duration_ms": record.duration_ms,
        "autonomy_level": record.autonomy_level,
        "violated_constraints": list(record.violated_constraints),
    }


def _trace_to_dict(trace: PipelineTrace) -> dict[str, Any]:
    """Convert a PipelineTrace into a JSON-safe dict for persistence."""
    return {
        "trace_id": trace.trace_id,
        "session_id": trace.session_id,
        "started_at": trace.started_at,
        "ended_at": trace.ended_at,
        "stages": [_stage_record_to_dict(s) for s in trace.stages],
        "completed": trace.completed,
        "blocked_at": trace.blocked_at.name if trace.blocked_at else None,
        "blocked_reason": trace.blocked_reason,
        "execution": (
            _execution_record_to_dict(trace.execution) if trace.execution else None
        ),
    }


def _validate_action_without_constitution(
    action_request: ActionRequest,
) -> ConstitutionalAssessment:
    """The constitutional gate's fallback when no Constitution is wired.

    Mirrors ``Constitution.validate_action()``'s first two steps exactly,
    without constructing a throwaway Constitution: an action declaring no
    Protected Constraint is NOT_APPLICABLE regardless; one that does is
    AUTHORITY_UNAVAILABLE, since there is no authority to authorize it
    against. This path is reachable only via direct ``CognitivePipeline()``
    construction in tests — the production composition root
    (``wiring.build_pipeline()``) always supplies a real Constitution.
    """
    if not action_request.affects:
        return ConstitutionalAssessment(verdict=ConstitutionalVerdict.NOT_APPLICABLE)
    order = {c: i for i, c in enumerate(ProtectedConstraint)}
    return ConstitutionalAssessment(
        verdict=ConstitutionalVerdict.AUTHORITY_UNAVAILABLE,
        violated=tuple(sorted(action_request.affects, key=lambda c: order[c])),
        reasoning="No Constitution is configured on this pipeline.",
    )


def _safe_json_dumps(payload: dict[str, Any]) -> str:
    """Serialize a persistence payload, never raising.

    ``payload`` is expected to already be built from ``_safe_value``
    conversions, so this should always succeed. The fallback below is a
    last-resort defense, not the expected path — a serialization failure
    must not destroy the Stage 7 memory write it is part of.
    """
    try:
        return json.dumps(payload)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "Trace/execution payload not serializable, using fallback: %s", exc
        )
        return json.dumps({"serialization_error": str(exc), "keys": list(payload.keys())})


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class CognitivePipeline:
    """Orchestrates the full cognitive pipeline from input to output.

    Composes all governance subsystems (risk, ethics, autonomy, decision),
    cognition subsystems (learning, reflection), memory storage, and tool
    execution into a sequential processing pipeline. Stages that are not
    yet implemented (communication, evolution) are stubbed and pass
    through transparently.

    Attributes:
        risk_evaluator: The 6-dimension risk evaluator.
        ethical_engine: The ethical boundary engine.
        autonomy_charter: The 5-level autonomy system.
        decision_framework: The multi-criteria option ranking framework.
        learning_engine: The experience-based learning engine.
        reflection_engine: The self-reflection protocol engine.
        memory_store: The SQLite-backed memory store (optional).
        tool_registry: The tool registry backing Stage 6 (optional). If
            None, Stage 6 always yields NO_ACTION (no action requested)
            or TOOL_NOT_FOUND (an action was requested but nothing can
            serve it) — it never invents behavior for a missing registry.
        constitution: The authoritative Constitution backing the
            constitutional gate in Stage 6 (optional). The production
            composition root (``wiring.build_pipeline()``) always
            supplies the Codex-derived Constitution from Bootstrap;
            ``None`` is for direct construction in tests. When None, an
            action that declares no ``affects`` is unaffected (still
            NOT_APPLICABLE); an action that does declare ``affects`` is
            treated as AUTHORITY_UNAVAILABLE — the same fail-closed
            behavior as a Constitution with no Codex authority loaded.
        last_trace: The PipelineTrace from the most recent process() call,
            or None before the first call. Exposed for introspection and
            testing; process() keeps its established PipelineResult
            return type rather than returning the trace directly.
    """

    def __init__(
        self,
        risk_evaluator: RiskEvaluator | None = None,
        ethical_engine: EthicalBoundaryEngine | None = None,
        autonomy_charter: AutonomyCharter | None = None,
        decision_framework: DecisionFramework | None = None,
        learning_engine: LearningEngine | None = None,
        reflection_engine: ReflectionEngine | None = None,
        evolution_engine: EvolutionEngine | None = None,
        memory_store: MemoryStore | None = None,
        tool_registry: ToolRegistry | None = None,
        constitution: Constitution | None = None,
    ) -> None:
        """Initialize the cognitive pipeline.

        Args:
            risk_evaluator: Risk evaluator instance. Created if None.
            ethical_engine: Ethical boundary engine. Created if None.
            autonomy_charter: Autonomy charter. Created if None.
            decision_framework: Decision framework. Created if None.
            learning_engine: Learning engine. Created if None.
            reflection_engine: Reflection engine. Created if None.
            evolution_engine: Evolution engine. Created if None.
            memory_store: Memory store for persistence. Optional.
            tool_registry: Tool registry for Stage 6 execution. Optional.
            constitution: Authoritative Constitution for the Stage 6
                constitutional gate. Optional; see class docstring.
        """
        self.risk_evaluator = risk_evaluator or RiskEvaluator()
        self.ethical_engine = ethical_engine or EthicalBoundaryEngine()
        self.autonomy_charter = autonomy_charter or AutonomyCharter()
        self.decision_framework = decision_framework or DecisionFramework()
        self.learning_engine = learning_engine or LearningEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.evolution_engine = evolution_engine or EvolutionEngine()
        self.memory_store = memory_store
        self.tool_registry = tool_registry
        self.constitution = constitution
        self.last_trace: PipelineTrace | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        user_input: str,
        *,
        communication_mode: CommunicationMode = CommunicationMode.COLLABORATIVE,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> PipelineResult:
        """Process user input through the full cognitive pipeline.

        This is the primary entry point for the cognitive loop. It runs
        all pipeline stages in order, respecting the sequential constraint:
        no downstream stage may execute before upstream validation
        completes.

        To have Stage 6 actually run a tool, place an ``ActionRequest`` at
        ``context["action"]``. With none supplied (the default for every
        existing caller), Stage 6 yields ``ExecutionOutcome.NO_ACTION`` and
        behavior is unchanged from before this stage was implemented.

        Args:
            user_input: The raw user input text.
            communication_mode: The communication mode to use.
            context: Optional additional context for processing.
            session_id: Optional session identifier. Generated if None.

        Returns:
            A PipelineResult with the response and all stage assessments.

        Raises:
            ValueError: If user_input is empty.
        """
        if not user_input or not user_input.strip():
            raise ValueError("user_input must not be empty")

        session_id = session_id or str(uuid.uuid4())
        ctx = context or {}
        trace_builder = _TraceBuilder(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            started_at=time.time(),
        )

        # Build the pipeline context
        pipeline_ctx = PipelineContext(
            user_input=user_input,
            session_id=session_id,
            communication_mode=communication_mode,
            metadata=ctx,
        )

        logger.info(
            "Starting pipeline processing",
            extra={
                "extra": {
                    "session_id": session_id,
                    "input_length": len(user_input),
                    "mode": communication_mode.value,
                }
            },
        )

        # Stage 1: Communication (stub)
        comm_result = self._stage_communication(pipeline_ctx)
        trace_builder.add_stage(comm_result)

        # Stage 2: Risk evaluation
        risk_result = self._stage_risk(user_input, ctx)
        trace_builder.add_stage(risk_result)
        if risk_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace_builder, risk_result, PipelineStage.RISK
            )

        risk_assessment = risk_result.data if risk_result.data else None
        if risk_assessment is None:
            risk_assessment = RiskAssessment(
                overall_level=RiskLevel.LOW,
                reversibility=RiskLevel.LOW,
                resource=RiskLevel.LOW,
                system_impact=RiskLevel.LOW,
                uncertainty=RiskLevel.LOW,
                emotional_impact=RiskLevel.LOW,
                scale=RiskLevel.LOW,
                reasoning="Default minimal risk assessment.",
            )

        # Stage 3: Ethical boundary check
        ethics_result = self._stage_ethics(user_input, ctx)
        trace_builder.add_stage(ethics_result)
        if ethics_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace_builder, ethics_result, PipelineStage.ETHICS
            )

        ethical_assessment: EthicalAssessment | None = None
        if isinstance(ethics_result.data, EthicalAssessment):
            ethical_assessment = ethics_result.data

        # Stage 4: Autonomy permission check
        autonomy_result = self._stage_autonomy(
            user_input, risk_assessment, ctx
        )
        trace_builder.add_stage(autonomy_result)
        if autonomy_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace_builder, autonomy_result, PipelineStage.AUTONOMY
            )

        autonomy_decision: AutonomyDecision | None = None
        if isinstance(autonomy_result.data, AutonomyDecision):
            autonomy_decision = autonomy_result.data

        # Stage 5: Decision framework
        decision_result = self._stage_decision(user_input, ctx)
        trace_builder.add_stage(decision_result)

        # Stage 6: Execution
        execution_stage, execution_record = self._stage_execution(
            pipeline_ctx, autonomy_decision
        )
        trace_builder.add_stage(execution_stage)
        trace_builder.execution = execution_record

        # Stage 7: Memory storage. This is the pipeline's single
        # persistence point (no write-ahead persistence): the trace
        # snapshot taken here covers stages 1-7 only, since Learning,
        # Reflection, and Evolution (8-10) haven't run yet.
        trace_snapshot = trace_builder.build(ended_at=time.time())
        memory_result = self._stage_memory(
            pipeline_ctx, ctx, trace_snapshot, execution_record
        )
        trace_builder.add_stage(memory_result)

        # Build the preliminary result for learning/reflection stages
        response = self._build_response(
            pipeline_ctx,
            risk_assessment,
            ethical_assessment,
            autonomy_decision,
            decision_result,
        )

        preliminary_result = PipelineResult(
            response=response,
            risk_assessment=risk_assessment,
            ethical_assessment=ethical_assessment,
            autonomy_decision=autonomy_decision,
            action_taken=decision_result.data if decision_result.data else None,
            metadata={
                "session_id": session_id,
                "stages_completed": len(trace_builder.stages),
                "pipeline_completed": False,
                "execution": execution_record,
            },
        )

        # Stage 8: Learning
        learning_result = self._stage_learning(pipeline_ctx, preliminary_result)
        trace_builder.add_stage(learning_result)

        # Stage 9: Reflection
        reflection_result = self._stage_reflection(pipeline_ctx, preliminary_result)
        trace_builder.add_stage(reflection_result)

        # Stage 10: Evolution
        learning_insights = (
            learning_result.data
            if isinstance(learning_result.data, list)
            else None
        )
        reflection_insights = (
            reflection_result.data
            if isinstance(reflection_result.data, list)
            else None
        )
        evolution_result = self._stage_evolution(
            pipeline_ctx,
            learning_insights=learning_insights,
            reflection_insights=reflection_insights,
        )
        trace_builder.add_stage(evolution_result)

        trace_builder.completed = True

        # Merge learning and reflection insights into the final result
        insights: list[str] = []
        if isinstance(learning_result.data, list):
            insights.extend(learning_result.data)
        if isinstance(reflection_result.data, list):
            insights.extend(reflection_result.data)

        logger.info(
            "Pipeline processing complete",
            extra={
                "extra": {
                    "session_id": session_id,
                    "stages_completed": len(trace_builder.stages),
                }
            },
        )

        self.last_trace = trace_builder.build(ended_at=time.time())

        return PipelineResult(
            response=response,
            risk_assessment=risk_assessment,
            ethical_assessment=ethical_assessment,
            autonomy_decision=autonomy_decision,
            action_taken=decision_result.data if decision_result.data else None,
            insights=insights,
            metadata={
                "session_id": session_id,
                "stages_completed": len(trace_builder.stages),
                "pipeline_completed": trace_builder.completed,
                "execution": execution_record,
            },
        )

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _stage_communication(self, ctx: PipelineContext) -> StageRecord:
        """Stub: Communication layer (full implementation in Milestone 7).

        In the full implementation, this stage will:
        - Interpret user intent
        - Detect emotional context
        - Select communication mode
        - Structure response format
        """
        logger.debug("Communication stage (stub)", extra={"input": ctx.user_input[:50]})
        return StageRecord(
            stage=PipelineStage.COMMUNICATION,
            status=True,
            data="Communication stage not yet implemented.",
        )

    def _stage_risk(
        self, action: str, ctx: dict[str, Any]
    ) -> StageRecord:
        """Stage 2: Evaluate action risk across 6 dimensions.

        Args:
            action: The action description to evaluate.
            ctx: Contextual information.

        Returns:
            A StageRecord with the RiskAssessment.
        """
        try:
            assessment = self.risk_evaluator.evaluate(action, context=ctx)
            logger.debug(
                "Risk evaluation complete",
                extra={
                    "extra": {
                        "overall": assessment.overall_level.name,
                        "reversibility": assessment.reversibility.name,
                        "resource": assessment.resource.name,
                    }
                },
            )
            return StageRecord(
                stage=PipelineStage.RISK,
                status=True,
                data=assessment,
            )
        except Exception as exc:
            logger.error("Risk evaluation failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.RISK,
                status=False,
                blocked=True,
                blocked_reason=f"Risk evaluation error: {exc}",
            )

    def _stage_ethics(
        self, action: str, ctx: dict[str, Any]
    ) -> StageRecord:
        """Stage 3: Check ethical boundaries and sacred constraints.

        Args:
            action: The action description to evaluate.
            ctx: Contextual information.

        Returns:
            A StageRecord with the EthicalAssessment.
        """
        try:
            assessment = self.ethical_engine.evaluate(action, context=ctx)
            logger.debug(
                "Ethical evaluation complete",
                extra={"extra": {"verdict": assessment.verdict.value}},
            )

            if assessment.verdict == EthicalVerdict.BLOCKED:
                return StageRecord(
                    stage=PipelineStage.ETHICS,
                    status=False,
                    blocked=True,
                    blocked_reason=(
                        f"Action blocked by ethical constraints: "
                        f"{', '.join(assessment.violated_constraints)}"
                    ),
                    data=assessment,
                )

            return StageRecord(
                stage=PipelineStage.ETHICS,
                status=True,
                data=assessment,
            )
        except Exception as exc:
            logger.error("Ethical evaluation failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.ETHICS,
                status=False,
                blocked=True,
                blocked_reason=f"Ethical evaluation error: {exc}",
            )

    def _stage_autonomy(
        self,
        action: str,
        risk_assessment: RiskAssessment,
        ctx: dict[str, Any],
    ) -> StageRecord:
        """Stage 4: Check autonomy permissions for the action.

        Args:
            action: The action description to evaluate.
            risk_assessment: The risk assessment from stage 2.
            ctx: Contextual information.

        Returns:
            A StageRecord with the AutonomyDecision.
        """
        try:
            domain = ctx.get("domain", "research")
            decision = self.autonomy_charter.check_permission(
                action=action,
                risk_level=risk_assessment.overall_level,
                domain=domain,
                context=ctx,
            )
            logger.debug(
                "Autonomy check complete",
                extra={
                    "extra": {
                        "level": decision.level.name,
                        "allowed": decision.allowed,
                        "requires_discussion": decision.requires_discussion,
                    }
                },
            )

            # Only hard-block on OBSERVATION (sacred constraint violation).
            # SUGGESTION and LIMITED are soft constraints — continue but
            # flag; Stage 6 applies its own, stricter gate before letting
            # anything with side effects run (see _stage_execution).
            if decision.level == AutonomyLevel.OBSERVATION:
                return StageRecord(
                    stage=PipelineStage.AUTONOMY,
                    status=False,
                    blocked=True,
                    blocked_reason=(
                        f"Action blocked at autonomy level "
                        f"{decision.level.name}: {decision.reasoning}"
                    ),
                    data=decision,
                )

            return StageRecord(
                stage=PipelineStage.AUTONOMY,
                status=True,
                data=decision,
            )
        except Exception as exc:
            logger.error("Autonomy check failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.AUTONOMY,
                status=False,
                blocked=True,
                blocked_reason=f"Autonomy check error: {exc}",
            )

    def _stage_decision(
        self, action: str, ctx: dict[str, Any]
    ) -> StageRecord:
        """Stage 5: Rank options using the decision framework.

        Args:
            action: The action description (treated as the primary option).
            ctx: Contextual information.

        Returns:
            A StageRecord with the decision result.
        """
        try:
            options = ctx.get("options", [action])

            result = self.decision_framework.evaluate(
                options=options,
                context=ctx,
            )

            best = (
                result.ranked_options[0].option
                if result.ranked_options
                else action
            )

            logger.debug(
                "Decision evaluation complete",
                extra={
                    "extra": {
                        "options_count": len(options),
                        "best_option": best[:50],
                        "requires_discussion": result.requires_discussion,
                    }
                },
            )

            return StageRecord(
                stage=PipelineStage.DECISION,
                status=True,
                data=best,
            )
        except Exception as exc:
            logger.error("Decision evaluation failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.DECISION,
                status=False,
                data=action,
            )

    def _stage_execution(
        self,
        ctx: PipelineContext,
        autonomy_decision: AutonomyDecision | None,
    ) -> tuple[StageRecord, ExecutionRecord]:
        """Stage 6: Execute an approved action through the tool registry.

        Runs only when the caller supplied an ``ActionRequest`` at
        ``ctx.metadata["action"]`` — nothing in the pipeline produces one
        on its own yet; that is planning/Event-Loop-shaped work and is
        out of scope here. With none supplied, this yields NO_ACTION and
        behaves exactly as the previous stub did.

        Authorization is a two-layer check, corresponding to two
        different questions:

        - The autonomy gate below decides whether *any* side effect may
          occur at all. Per codex/operations/AUTONOMY_CHARTER.md, Level 1
          (Suggestion) is propose-only; Level 2 (Limited) is the first
          level that permits low-risk, reversible action. This is
          stricter than Stage 4's own block, which only hard-blocks at
          OBSERVATION — Stage 4 asks "may reasoning continue?", this asks
          "may a side effect occur?".
        - ``ToolRegistry.check_permission()`` then decides whether *this
          specific tool* may run (sacred domains, approval requirements,
          trust) — "capability does not imply permission"
          (codex/operations/TOOL_CREATION_FRAMEWORK.md).

        Never raises: every failure mode is classified into an
        ExecutionOutcome and returned alongside its StageRecord.

        Args:
            ctx: The pipeline context (its metadata carries the optional
                ActionRequest).
            autonomy_decision: The AutonomyDecision from Stage 4.

        Returns:
            A tuple of (StageRecord, ExecutionRecord). The ExecutionRecord
            is also embedded in the StageRecord's ``data`` field.
        """
        autonomy_level = autonomy_decision.level.name if autonomy_decision else None
        action_request = ctx.metadata.get("action")

        if action_request is None:
            record = ExecutionRecord(
                outcome=ExecutionOutcome.NO_ACTION, autonomy_level=autonomy_level
            )
            return (
                StageRecord(stage=PipelineStage.EXECUTION, status=True, data=record),
                record,
            )

        if not isinstance(action_request, ActionRequest):
            record = ExecutionRecord(
                outcome=ExecutionOutcome.NO_ACTION,
                error="metadata['action'] is not an ActionRequest; ignored",
                autonomy_level=autonomy_level,
            )
            return (
                StageRecord(stage=PipelineStage.EXECUTION, status=True, data=record),
                record,
            )

        try:
            record = self._execute_action(action_request, autonomy_decision, autonomy_level)
        except Exception as exc:
            # Defense in depth: ToolRegistry.execute() already contains
            # tool.validate()/execute() exceptions internally. This only
            # guards Core's own classification logic above (tool lookup,
            # permission check) from an unforeseen failure.
            logger.error("Execution stage failed unexpectedly", exc_info=exc)
            record = ExecutionRecord(
                outcome=ExecutionOutcome.TOOL_ERROR,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error=str(exc),
                autonomy_level=autonomy_level,
            )
            return (
                StageRecord(
                    stage=PipelineStage.EXECUTION,
                    status=False,
                    data=record,
                    error=str(exc),
                ),
                record,
            )

        logger.debug(
            "Execution stage complete",
            extra={
                "extra": {
                    "outcome": record.outcome.value,
                    "tool": record.tool,
                    "duration_ms": record.duration_ms,
                }
            },
        )
        return (
            StageRecord(stage=PipelineStage.EXECUTION, status=True, data=record),
            record,
        )

    def _execute_action(
        self,
        action_request: ActionRequest,
        autonomy_decision: AutonomyDecision | None,
        autonomy_level: str | None,
    ) -> ExecutionRecord:
        """Authorize and run one ActionRequest.

        The constitutional gate runs first, before autonomy: nothing
        downstream may override, broaden, narrow, or reinterpret the
        Protected Constraints (codex/SYSTEM_INTEGRATION.md, "Conflict
        Resolution Hierarchy" — Constitution ranks above Ethics, Autonomy,
        Risk/Decision, Tool Policy, and Execution). A VIOLATION or
        AUTHORITY_UNAVAILABLE verdict denies execution outright; PERMITTED
        and NOT_APPLICABLE both fall through to the existing autonomy gate
        unchanged.

        Split out of ``_stage_execution`` for readability; may raise on
        a genuinely unexpected failure, which the caller classifies as
        TOOL_ERROR rather than letting escape.
        """
        constitutional = (
            self.constitution.validate_action(action_request)
            if self.constitution is not None
            else _validate_action_without_constitution(action_request)
        )
        if constitutional.verdict in (
            ConstitutionalVerdict.VIOLATION,
            ConstitutionalVerdict.AUTHORITY_UNAVAILABLE,
        ):
            return ExecutionRecord(
                outcome=ExecutionOutcome.DENIED_CONSTITUTION,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error=f"Constitutional gate denied execution: {constitutional.reasoning}",
                violated_constraints=tuple(c.value for c in constitutional.violated),
                autonomy_level=autonomy_level,
            )

        authorized = (
            autonomy_decision is not None
            and autonomy_decision.allowed
            and autonomy_decision.level.value >= AutonomyLevel.LIMITED.value
            and not autonomy_decision.requires_approval
        )
        if not authorized:
            reason = (
                autonomy_decision.reasoning
                if autonomy_decision is not None
                else "No autonomy decision available"
            )
            return ExecutionRecord(
                outcome=ExecutionOutcome.DENIED_AUTONOMY,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error=f"Autonomy gate denied execution: {reason}",
                autonomy_level=autonomy_level,
            )

        if self.tool_registry is None:
            return ExecutionRecord(
                outcome=ExecutionOutcome.TOOL_NOT_FOUND,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error="No tool registry configured",
                autonomy_level=autonomy_level,
            )

        if self.tool_registry.get_tool(action_request.tool) is None:
            return ExecutionRecord(
                outcome=ExecutionOutcome.TOOL_NOT_FOUND,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error=f"Tool '{action_request.tool}' not found in registry",
                autonomy_level=autonomy_level,
            )

        permission = self.tool_registry.check_permission(action_request.tool)
        if not permission["allowed"]:
            return ExecutionRecord(
                outcome=ExecutionOutcome.DENIED_TOOL,
                tool=action_request.tool,
                arguments=action_request.arguments,
                error=str(permission["reason"]),
                autonomy_level=autonomy_level,
            )

        started = time.monotonic()
        # require_permission=False: Core already checked permission above;
        # the registry's own recheck would be a redundant second opinion,
        # not a stronger guarantee.
        result: ToolResult = self.tool_registry.execute(
            action_request.tool, require_permission=False, **action_request.arguments
        )
        duration_ms = (time.monotonic() - started) * 1000

        if result.success:
            return ExecutionRecord(
                outcome=ExecutionOutcome.SUCCEEDED,
                tool=action_request.tool,
                arguments=action_request.arguments,
                output=result.output,
                duration_ms=duration_ms,
                autonomy_level=autonomy_level,
            )

        # ToolResult carries only a boolean and a message; classifying
        # more finely means reading registry.py's own message text, which
        # is stable, documented production code (not a test fixture).
        error_message = result.error or ""
        if "validation" in error_message:
            outcome = ExecutionOutcome.INVALID_ARGUMENTS
        elif "execution error" in error_message:
            outcome = ExecutionOutcome.TOOL_ERROR
        else:
            outcome = ExecutionOutcome.TOOL_FAILED

        return ExecutionRecord(
            outcome=outcome,
            tool=action_request.tool,
            arguments=action_request.arguments,
            error=result.error,
            duration_ms=duration_ms,
            autonomy_level=autonomy_level,
        )

    def _stage_memory(
        self,
        ctx: PipelineContext,
        extra: dict[str, Any],
        trace: PipelineTrace,
        execution_record: ExecutionRecord,
    ) -> StageRecord:
        """Stage 7: Store the interaction, trace snapshot, and execution record.

        This is the pipeline's single persistence point — no write-ahead
        persistence. ``trace`` reflects stages 1-7 only: Learning,
        Reflection, and Evolution (8-10) run after this stage and persist
        their own state separately under MemoryDomain.REFLECTION, as
        before.

        The ExecutionRecord is persisted to MemoryDomain.TOOL (Tool
        Memory — codex/operations/MEMORY_ARCHITECTURE.md §6) only when an
        action was actually requested; NO_ACTION runs never create tool
        execution history.

        Args:
            ctx: The pipeline context.
            extra: Additional context for storage.
            trace: The trace snapshot through Stage 7.
            execution_record: The Stage 6 execution outcome.

        Returns:
            A StageRecord indicating storage success.
        """
        if self.memory_store is None:
            logger.debug("Memory stage: no store configured, skipping")
            return StageRecord(
                stage=PipelineStage.MEMORY,
                status=True,
                data="No memory store configured.",
            )

        try:
            # `extra` is the caller-supplied context dict — it may now
            # carry an ActionRequest (or anything else a caller puts in
            # `context=`), so it needs the same defensive conversion as
            # trace/execution payloads before MemoryStore.store() runs
            # its own, unguarded json.dumps() over it as `metadata=`.
            safe_extra = _safe_value(extra)

            # Store in project memory as a conversation entry
            self.memory_store.store(
                domain=MemoryDomain.PROJECT,
                content=_safe_json_dumps({
                    "type": "pipeline_interaction",
                    "user_input": ctx.user_input,
                    "session_id": ctx.session_id,
                    "mode": ctx.communication_mode.value,
                    "metadata": safe_extra,
                    "trace": _trace_to_dict(trace),
                }),
                metadata=safe_extra,
                index_keys={"type": "pipeline_interaction"},
            )
            logger.debug("Memory storage complete")

            if execution_record.outcome is not ExecutionOutcome.NO_ACTION:
                try:
                    self.memory_store.store(
                        domain=MemoryDomain.TOOL,
                        content=_safe_json_dumps(
                            _execution_record_to_dict(execution_record)
                        ),
                        metadata={
                            "type": "tool_execution",
                            "session_id": ctx.session_id,
                            "outcome": execution_record.outcome.value,
                        },
                        index_keys={
                            "type": "tool_execution",
                            "tool": execution_record.tool or "",
                        },
                    )
                except Exception as exc:
                    logger.warning("Failed to persist execution record: %s", exc)

            return StageRecord(
                stage=PipelineStage.MEMORY,
                status=True,
                data="Stored in memory.",
            )
        except Exception as exc:
            logger.error("Memory storage failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.MEMORY,
                status=False,
                data=f"Memory storage error: {exc}",
            )

    def _stage_learning(
        self, ctx: PipelineContext, result: PipelineResult
    ) -> StageRecord:
        """Stage 8: Process experience through the learning engine.

        Extracts learning signals from the pipeline result and updates
        behavioral patterns and cognitive models.
        """
        try:
            update = self.learning_engine.process_experience(
                result,
                user_input=ctx.user_input,
            )
            logger.debug(
                "Learning stage: %d signals → %d patterns, %d adjustments",
                update.signals_processed,
                len(update.patterns_extracted),
                len(update.behavioral_adjustments),
            )

            # Persist learning state to memory if available
            if self.memory_store:
                try:
                    self.memory_store.store(
                        domain=MemoryDomain.REFLECTION,
                        content=self.learning_engine.to_memory_content(),
                        metadata={
                            "type": "learning_update",
                            "session_id": ctx.session_id,
                            "signals_processed": update.signals_processed,
                        },
                        index_keys=self.learning_engine.to_memory_index_keys(),
                    )
                except Exception as exc:
                    logger.warning("Failed to persist learning state: %s", exc)

            return StageRecord(
                stage=PipelineStage.LEARNING,
                status=True,
                data=update.insights,
            )
        except Exception as exc:
            logger.error("Learning stage failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.LEARNING,
                status=False,
                data=f"Learning error: {exc}",
            )

    def _stage_reflection(
        self, ctx: PipelineContext, result: PipelineResult
    ) -> StageRecord:
        """Stage 9: Perform self-reflection on the interaction.

        Analyzes the outcome, extracts insights, and generates
        actionable improvements following the Self-Reflection Protocol.
        """
        try:
            output = self.reflection_engine.reflect(
                result,
                user_input=ctx.user_input,
            )
            logger.debug(
                "Reflection stage: %d insights, %d improvements, importance=%s",
                len(output.insights),
                len(output.improvements),
                output.importance.value,
            )

            # Persist reflection state to memory if available
            if self.memory_store:
                try:
                    self.memory_store.store(
                        domain=MemoryDomain.REFLECTION,
                        content=self.reflection_engine.to_memory_content(),
                        metadata={
                            "type": "reflection_output",
                            "session_id": ctx.session_id,
                            "importance": output.importance.value,
                            "triggers": [t.value for t in output.triggers],
                        },
                        index_keys=self.reflection_engine.to_memory_index_keys(),
                    )
                except Exception as exc:
                    logger.warning("Failed to persist reflection state: %s", exc)

            return StageRecord(
                stage=PipelineStage.REFLECTION,
                status=True,
                data=output.insights,
            )
        except Exception as exc:
            logger.error("Reflection stage failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.REFLECTION,
                status=False,
                data=f"Reflection error: {exc}",
            )

    def _stage_evolution(
        self,
        ctx: PipelineContext,
        learning_insights: list[str] | None = None,
        reflection_insights: list[str] | None = None,
    ) -> StageRecord:
        """Stage 10: Long-term evolution updates.

        Processes learning and reflection insights through the EvolutionEngine
        to generate identity-preserving evolution proposals. Proposals that
        pass all 6 identity-preservation checks are automatically applied.

        Args:
            ctx: The pipeline context.
            learning_insights: Insights from the learning stage.
            reflection_insights: Insights from the reflection stage.

        Returns:
            A StageRecord with evolution proposals in the ``data`` field.
        """
        try:
            proposals = self.evolution_engine.process_evolution_stage(
                learning_insights=learning_insights,
                reflection_insights=reflection_insights,
            )

            applied = sum(
                1 for p in proposals if p.status == EvolutionStatus.APPLIED
            )
            rejected = sum(
                1 for p in proposals if p.status == EvolutionStatus.REJECTED
            )

            logger.debug(
                "Evolution stage: %d proposals (%d applied, %d rejected)",
                len(proposals),
                applied,
                rejected,
            )

            # Persist evolution state to memory if available
            if self.memory_store:
                try:
                    self.memory_store.store(
                        domain=MemoryDomain.REFLECTION,
                        content=self.evolution_engine.to_memory_content(),
                        metadata={
                            "type": "evolution_update",
                            "session_id": ctx.session_id,
                            "proposals_generated": len(proposals),
                            "proposals_applied": applied,
                        },
                        index_keys=self.evolution_engine.to_memory_index_keys(),
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to persist evolution state: %s", exc
                    )

            # Return proposal summaries as the data field (data carrier)
            proposal_summaries = [
                f"[{p.status.value}] {p.evolution_type.value}: {p.description[:100]}"
                for p in proposals
            ]

            return StageRecord(
                stage=PipelineStage.EVOLUTION,
                status=True,
                data=proposal_summaries,
            )
        except Exception as exc:
            logger.error("Evolution stage failed", exc_info=exc)
            return StageRecord(
                stage=PipelineStage.EVOLUTION,
                status=False,
                data=f"Evolution error: {exc}",
            )

    # ------------------------------------------------------------------
    # Response building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_response(
        ctx: PipelineContext,
        risk: RiskAssessment,
        ethics: EthicalAssessment | None,
        autonomy: AutonomyDecision | None,
        decision: StageRecord,
    ) -> str:
        """Build a human-readable response from pipeline results.

        Args:
            ctx: The pipeline context.
            risk: The risk assessment.
            ethics: The ethical assessment (if any).
            autonomy: The autonomy decision (if any).
            decision: The decision stage result.

        Returns:
            A formatted response string.
        """
        parts: list[str] = []

        parts.append(f"Processed: {ctx.user_input[:100]}")

        if risk:
            parts.append(f"Risk: {risk.overall_level.name}")

        if ethics and ethics.verdict != EthicalVerdict.ALLOWED:
            parts.append(
                f"Ethics: {ethics.verdict.value} — {ethics.reasoning}"
            )

        if autonomy:
            parts.append(
                f"Autonomy: {autonomy.level.name} "
                f"(allowed={autonomy.allowed})"
            )

        if decision.status and decision.data:
            parts.append(f"Selected action: {decision.data}")

        return "\n".join(parts)

    def _build_blocked_result(
        self,
        ctx: PipelineContext,
        trace_builder: _TraceBuilder,
        stage_result: StageRecord,
        stage: PipelineStage,
    ) -> PipelineResult:
        """Build a PipelineResult when the pipeline is blocked.

        Args:
            ctx: The pipeline context.
            trace_builder: The in-progress trace accumulator.
            stage_result: The blocking stage result.
            stage: The stage at which the pipeline was blocked.

        Returns:
            A PipelineResult indicating the block.
        """
        trace_builder.block(stage, stage_result.blocked_reason)
        logger.warning(
            "Pipeline blocked",
            extra={
                "extra": {
                    "stage": stage.name,
                    "reason": stage_result.blocked_reason,
                }
            },
        )

        # Extract the stage assessment if available
        risk_assessment: RiskAssessment | None = None
        ethical_assessment: EthicalAssessment | None = None
        autonomy_decision: AutonomyDecision | None = None

        for sr in trace_builder.stages:
            if sr.stage == PipelineStage.RISK and isinstance(sr.data, RiskAssessment):
                risk_assessment = sr.data
            elif sr.stage == PipelineStage.ETHICS and isinstance(sr.data, EthicalAssessment):
                ethical_assessment = sr.data
            elif sr.stage == PipelineStage.AUTONOMY and isinstance(sr.data, AutonomyDecision):
                autonomy_decision = sr.data

        self.last_trace = trace_builder.build(ended_at=time.time())

        return PipelineResult(
            response=(
                f"Action blocked at {stage.name} stage: "
                f"{stage_result.blocked_reason}"
            ),
            risk_assessment=risk_assessment,
            ethical_assessment=ethical_assessment,
            autonomy_decision=autonomy_decision,
            metadata={
                "session_id": ctx.session_id,
                "stages_completed": len(trace_builder.stages),
                "blocked_at": stage.name,
                "blocked_reason": stage_result.blocked_reason,
                "pipeline_completed": False,
            },
        )

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_stage_order(self) -> list[PipelineStage]:
        """Return the ordered list of pipeline stages.

        Returns:
            The pipeline stages in execution order.
        """
        return list(PipelineStage)

    def get_available_stages(self) -> dict[PipelineStage, bool]:
        """Return which stages are currently implemented.

        Returns:
            A dict mapping each stage to whether it is implemented.
        """
        return {
            PipelineStage.COMMUNICATION: False,  # Stub
            PipelineStage.RISK: True,
            PipelineStage.ETHICS: True,
            PipelineStage.AUTONOMY: True,
            PipelineStage.DECISION: True,
            PipelineStage.EXECUTION: True,
            PipelineStage.MEMORY: True,
            PipelineStage.LEARNING: True,
            PipelineStage.REFLECTION: True,
            PipelineStage.EVOLUTION: True,
        }

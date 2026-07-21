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
    6. Execution (stub — full implementation in Milestone 10)
    7. Memory storage
    8. Learning (experience-based behavioral improvement)
    9. Reflection (self-analysis and insight extraction)
    10. Evolution (stub — full implementation in Milestone 11)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from telemachus.cognition.evolution import EvolutionEngine, EvolutionStatus
from telemachus.cognition.learning import LearningEngine
from telemachus.cognition.reflection import ReflectionEngine
from telemachus.core.types import (
    AutonomyDecision,
    AutonomyLevel,
    CommunicationMode,
    EthicalAssessment,
    EthicalVerdict,
    MemoryDomain,
    PipelineContext,
    PipelineResult,
    PipelineStage,
    RiskAssessment,
    RiskLevel,
)
from telemachus.governance.autonomy import AutonomyCharter
from telemachus.governance.decision import DecisionFramework
from telemachus.governance.ethics import EthicalBoundaryEngine
from telemachus.governance.risk import RiskEvaluator
from telemachus.memory.store import MemoryStore

logger = logging.getLogger("telemachus.pipeline")


# ---------------------------------------------------------------------------
# Pipeline stage result tracking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StageResult:
    """Internal tracking for a single pipeline stage's outcome."""

    stage: PipelineStage
    status: bool
    failure: Any = None
    error: str | None = None
    blocked: bool = False
    blocked_reason: str = ""


@dataclass
class _PipelineTrace:
    """Complete trace of all pipeline stage results.

    Not frozen — this is an internal mutable tracking object.
    """

    trace_id: str
    stages: list[_StageResult] = field(default_factory=list)
    completed: bool = False
    blocked_at: PipelineStage | None = None

    def add_stage(self, result: _StageResult) -> None:
        """Add a stage result to the trace."""
        self.stages.append(result)

    def block(self, stage: PipelineStage, reason: str) -> None:
        """Mark the pipeline as blocked at a specific stage."""
        self.blocked_at = stage
        self.completed = False


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class CognitivePipeline:
    """Orchestrates the full cognitive pipeline from input to output.

    Composes all governance subsystems (risk, ethics, autonomy, decision),
    cognition subsystems (learning, reflection), and memory storage into a
    sequential processing pipeline. Stages that are not yet implemented
    (communication, execution, evolution) are stubbed and pass through
    transparently.

    Attributes:
        risk_evaluator: The 6-dimension risk evaluator.
        ethical_engine: The ethical boundary engine.
        autonomy_charter: The 5-level autonomy system.
        decision_framework: The multi-criteria option ranking framework.
        learning_engine: The experience-based learning engine.
        reflection_engine: The self-reflection protocol engine.
        memory_store: The SQLite-backed memory store (optional).
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
        """
        self.risk_evaluator = risk_evaluator or RiskEvaluator()
        self.ethical_engine = ethical_engine or EthicalBoundaryEngine()
        self.autonomy_charter = autonomy_charter or AutonomyCharter()
        self.decision_framework = decision_framework or DecisionFramework()
        self.learning_engine = learning_engine or LearningEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.evolution_engine = evolution_engine or EvolutionEngine()
        self.memory_store = memory_store

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
        no downstream stage may execute before upstream validation.

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
        trace = _PipelineTrace(trace_id=session_id)

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
                "session_id": session_id,
                "input_length": len(user_input),
                "mode": communication_mode.value,
            },
        )

        # Stage 1: Communication (stub)
        comm_result = self._stage_communication(pipeline_ctx)
        trace.add_stage(comm_result)

        # Stage 2: Risk evaluation
        risk_result = self._stage_risk(user_input, ctx)
        trace.add_stage(risk_result)
        if risk_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace, risk_result, PipelineStage.RISK
            )

        risk_assessment = risk_result.failure if risk_result.failure else None
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
        trace.add_stage(ethics_result)
        if ethics_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace, ethics_result, PipelineStage.ETHICS
            )

        ethical_assessment: EthicalAssessment | None = None
        if isinstance(ethics_result.failure, EthicalAssessment):
            ethical_assessment = ethics_result.failure

        # Stage 4: Autonomy permission check
        autonomy_result = self._stage_autonomy(
            user_input, risk_assessment, ctx
        )
        trace.add_stage(autonomy_result)
        if autonomy_result.blocked:
            return self._build_blocked_result(
                pipeline_ctx, trace, autonomy_result, PipelineStage.AUTONOMY
            )

        autonomy_decision: AutonomyDecision | None = None
        if isinstance(autonomy_result.failure, AutonomyDecision):
            autonomy_decision = autonomy_result.failure

        # Stage 5: Decision framework
        decision_result = self._stage_decision(user_input, ctx)
        trace.add_stage(decision_result)

        # Stage 6: Execution (stub)
        execution_result = self._stage_execution(pipeline_ctx)
        trace.add_stage(execution_result)

        # Stage 7: Memory storage
        memory_result = self._stage_memory(pipeline_ctx, ctx)
        trace.add_stage(memory_result)

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
            action_taken=decision_result.failure if decision_result.failure else None,
            metadata={
                "session_id": session_id,
                "stages_completed": len(trace.stages),
                "pipeline_completed": False,
            },
        )

        # Stage 8: Learning
        learning_result = self._stage_learning(pipeline_ctx, preliminary_result)
        trace.add_stage(learning_result)

        # Stage 9: Reflection
        reflection_result = self._stage_reflection(pipeline_ctx, preliminary_result)
        trace.add_stage(reflection_result)

        # Stage 10: Evolution
        learning_insights = (
            learning_result.failure
            if isinstance(learning_result.failure, list)
            else None
        )
        reflection_insights = (
            reflection_result.failure
            if isinstance(reflection_result.failure, list)
            else None
        )
        evolution_result = self._stage_evolution(
            pipeline_ctx,
            learning_insights=learning_insights,
            reflection_insights=reflection_insights,
        )
        trace.add_stage(evolution_result)

        trace.completed = True

        # Merge learning and reflection insights into the final result
        insights: list[str] = []
        if isinstance(learning_result.failure, list):
            insights.extend(learning_result.failure)
        if isinstance(reflection_result.failure, list):
            insights.extend(reflection_result.failure)

        logger.info(
            "Pipeline processing complete",
            {"session_id": session_id, "stages_completed": len(trace.stages)},
        )

        return PipelineResult(
            response=response,
            risk_assessment=risk_assessment,
            ethical_assessment=ethical_assessment,
            autonomy_decision=autonomy_decision,
            action_taken=decision_result.failure if decision_result.failure else None,
            insights=insights,
            metadata={
                "session_id": session_id,
                "stages_completed": len(trace.stages),
                "pipeline_completed": trace.completed,
            },
        )

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _stage_communication(self, ctx: PipelineContext) -> _StageResult:
        """Stub: Communication layer (full implementation in Milestone 7).

        In the full implementation, this stage will:
        - Interpret user intent
        - Detect emotional context
        - Select communication mode
        - Structure response format
        """
        logger.debug("Communication stage (stub)", extra={"input": ctx.user_input[:50]})
        return _StageResult(
            stage=PipelineStage.COMMUNICATION,
            status=True,
            failure="Communication stage not yet implemented.",
        )

    def _stage_risk(
        self, action: str, ctx: dict[str, Any]
    ) -> _StageResult:
        """Stage 2: Evaluate action risk across 6 dimensions.

        Args:
            action: The action description to evaluate.
            ctx: Contextual information.

        Returns:
            A _StageResult with the RiskAssessment.
        """
        try:
            assessment = self.risk_evaluator.evaluate(action, context=ctx)
            logger.debug(
                "Risk evaluation complete",
                {
                    "overall": assessment.overall_level.name,
                    "reversibility": assessment.reversibility.name,
                    "resource": assessment.resource.name,
                },
            )
            return _StageResult(
                stage=PipelineStage.RISK,
                status=True,
                failure=assessment,
            )
        except Exception as exc:
            logger.error("Risk evaluation failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.RISK,
                status=False,
                blocked=True,
                blocked_reason=f"Risk evaluation error: {exc}",
            )

    def _stage_ethics(
        self, action: str, ctx: dict[str, Any]
    ) -> _StageResult:
        """Stage 3: Check ethical boundaries and sacred constraints.

        Args:
            action: The action description to evaluate.
            ctx: Contextual information.

        Returns:
            A _StageResult with the EthicalAssessment.
        """
        try:
            assessment = self.ethical_engine.evaluate(action, context=ctx)
            logger.debug(
                "Ethical evaluation complete",
                {"verdict": assessment.verdict.value},
            )

            if assessment.verdict == EthicalVerdict.BLOCKED:
                return _StageResult(
                    stage=PipelineStage.ETHICS,
                    status=False,
                    blocked=True,
                    blocked_reason=(
                        f"Action blocked by ethical constraints: "
                        f"{', '.join(assessment.violated_constraints)}"
                    ),
                    failure=assessment,
                )

            return _StageResult(
                stage=PipelineStage.ETHICS,
                status=True,
                failure=assessment,
            )
        except Exception as exc:
            logger.error("Ethical evaluation failed", exc_info=exc)
            return _StageResult(
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
    ) -> _StageResult:
        """Stage 4: Check autonomy permissions for the action.

        Args:
            action: The action description to evaluate.
            risk_assessment: The risk assessment from stage 2.
            ctx: Contextual information.

        Returns:
            A _StageResult with the AutonomyDecision.
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
                {
                    "level": decision.level.name,
                    "allowed": decision.allowed,
                    "requires_discussion": decision.requires_discussion,
                },
            )

            # Only hard-block on OBSERVATION (sacred constraint violation).
            # SUGGESTION and LIMITED are soft constraints — continue but flag.
            if decision.level == AutonomyLevel.OBSERVATION:
                return _StageResult(
                    stage=PipelineStage.AUTONOMY,
                    status=False,
                    blocked=True,
                    blocked_reason=(
                        f"Action blocked at autonomy level "
                        f"{decision.level.name}: {decision.reasoning}"
                    ),
                    failure=decision,
                )

            return _StageResult(
                stage=PipelineStage.AUTONOMY,
                status=True,
                failure=decision,
            )
        except Exception as exc:
            logger.error("Autonomy check failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.AUTONOMY,
                status=False,
                blocked=True,
                blocked_reason=f"Autonomy check error: {exc}",
            )

    def _stage_decision(
        self, action: str, ctx: dict[str, Any]
    ) -> _StageResult:
        """Stage 5: Rank options using the decision framework.

        Args:
            action: The action description (treated as the primary option).
            ctx: Contextual information.

        Returns:
            A _StageResult with the decision result.
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
                {
                    "options_count": len(options),
                    "best_option": best[:50],
                    "requires_discussion": result.requires_discussion,
                },
            )

            return _StageResult(
                stage=PipelineStage.DECISION,
                status=True,
                failure=best,
            )
        except Exception as exc:
            logger.error("Decision evaluation failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.DECISION,
                status=False,
                failure=action,
            )

    def _stage_execution(self, ctx: PipelineContext) -> _StageResult:
        """Stage 6: Execute the selected action (stub).

        Full implementation in Milestone 10 (Tool System).
        """
        logger.debug("Execution stage: stub")
        return _StageResult(
            stage=PipelineStage.EXECUTION,
            status=True,
            failure="Execution stage not yet implemented.",
        )

    def _stage_memory(
        self, ctx: PipelineContext, extra: dict[str, Any]
    ) -> _StageResult:
        """Stage 7: Store the interaction in memory.

        Args:
            ctx: The pipeline context.
            extra: Additional context for storage.

        Returns:
            A _StageResult indicating storage success.
        """
        if self.memory_store is None:
            logger.debug("Memory stage: no store configured, skipping")
            return _StageResult(
                stage=PipelineStage.MEMORY,
                status=True,
                failure="No memory store configured.",
            )

        try:
            # Store in project memory as a conversation entry
            self.memory_store.store(
                domain=MemoryDomain.PROJECT,
                content=json.dumps({
                    "type": "pipeline_interaction",
                    "user_input": ctx.user_input,
                    "session_id": ctx.session_id,
                    "mode": ctx.communication_mode.value,
                    "metadata": extra,
                }),
                metadata=extra,
                index_keys={"type": "pipeline_interaction"},
            )
            logger.debug("Memory storage complete")
            return _StageResult(
                stage=PipelineStage.MEMORY,
                status=True,
                failure="Stored in memory.",
            )
        except Exception as exc:
            logger.error("Memory storage failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.MEMORY,
                status=False,
                failure=f"Memory storage error: {exc}",
            )

    def _stage_learning(
        self, ctx: PipelineContext, result: PipelineResult
    ) -> _StageResult:
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

            return _StageResult(
                stage=PipelineStage.LEARNING,
                status=True,
                failure=update.insights,
            )
        except Exception as exc:
            logger.error("Learning stage failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.LEARNING,
                status=False,
                failure=f"Learning error: {exc}",
            )

    def _stage_reflection(
        self, ctx: PipelineContext, result: PipelineResult
    ) -> _StageResult:
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

            return _StageResult(
                stage=PipelineStage.REFLECTION,
                status=True,
                failure=output.insights,
            )
        except Exception as exc:
            logger.error("Reflection stage failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.REFLECTION,
                status=False,
                failure=f"Reflection error: {exc}",
            )

    def _stage_evolution(
        self,
        ctx: PipelineContext,
        learning_insights: list[str] | None = None,
        reflection_insights: list[str] | None = None,
    ) -> _StageResult:
        """Stage 10: Long-term evolution updates.

        Processes learning and reflection insights through the EvolutionEngine
        to generate identity-preserving evolution proposals. Proposals that
        pass all 6 identity-preservation checks are automatically applied.

        Args:
            ctx: The pipeline context.
            learning_insights: Insights from the learning stage.
            reflection_insights: Insights from the reflection stage.

        Returns:
            A _StageResult with evolution proposals in the failure field
            (following the pipeline convention of using failure for data).
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

            # Return proposal summaries as the failure field (data carrier)
            proposal_summaries = [
                f"[{p.status.value}] {p.evolution_type.value}: {p.description[:100]}"
                for p in proposals
            ]

            return _StageResult(
                stage=PipelineStage.EVOLUTION,
                status=True,
                failure=proposal_summaries,
            )
        except Exception as exc:
            logger.error("Evolution stage failed", exc_info=exc)
            return _StageResult(
                stage=PipelineStage.EVOLUTION,
                status=False,
                failure=f"Evolution error: {exc}",
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
        decision: _StageResult,
    ) -> str:
        """Build a human-readable response from pipeline results.

        Args:
            ctx: The pipeline context.
            risk: The risk assessment.
            ethical: The ethical assessment (if any).
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

        if decision.status and decision.failure:
            parts.append(f"Selected action: {decision.failure}")

        return "\n".join(parts)

    @staticmethod
    def _build_blocked_result(
        ctx: PipelineContext,
        trace: _PipelineTrace,
        stage_result: _StageResult,
        stage: PipelineStage,
    ) -> PipelineResult:
        """Build a PipelineResult when the pipeline is blocked.

        Args:
            ctx: The pipeline context.
            trace: The pipeline trace.
            stage_result: The blocking stage result.
            stage: The stage at which the pipeline was blocked.

        Returns:
            A PipelineResult indicating the block.
        """
        trace.block(stage, stage_result.blocked_reason)
        logger.warning(
            "Pipeline blocked",
            {
                "stage": stage.name,
                "reason": stage_result.blocked_reason,
            },
        )

        # Extract the stage assessment if available
        risk_assessment: RiskAssessment | None = None
        ethical_assessment: EthicalAssessment | None = None
        autonomy_decision: AutonomyDecision | None = None

        for sr in trace.stages:
            if sr.stage == PipelineStage.RISK and isinstance(sr.failure, RiskAssessment):
                risk_assessment = sr.failure
            elif sr.stage == PipelineStage.ETHICS and isinstance(sr.failure, EthicalAssessment):
                ethical_assessment = sr.failure
            elif sr.stage == PipelineStage.AUTONOMY and isinstance(sr.failure, AutonomyDecision):
                autonomy_decision = sr.failure

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
                "stages_completed": len(trace.stages),
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
            PipelineStage.EXECUTION: False,  # Stub
            PipelineStage.MEMORY: True,
            PipelineStage.LEARNING: True,
            PipelineStage.REFLECTION: True,
            PipelineStage.EVOLUTION: True,
        }

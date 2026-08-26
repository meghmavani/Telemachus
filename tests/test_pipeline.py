"""Integration tests for the CognitivePipeline — the full input→output loop."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from telemachus.core.types import (
    AutonomyLevel,
    CommunicationMode,
    MemoryDomain,
    PipelineResult,
    PipelineStage,
    RiskLevel,
    StageRecord,
)
from telemachus.governance.autonomy import AutonomyCharter
from telemachus.governance.decision import DecisionFramework
from telemachus.governance.ethics import EthicalBoundaryEngine
from telemachus.governance.risk import RiskEvaluator
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline, _TraceBuilder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline() -> CognitivePipeline:
    """Create a CognitivePipeline with default components."""
    return CognitivePipeline()


@pytest.fixture
def pipeline_with_memory(tmp_path: Path) -> CognitivePipeline:
    """Create a CognitivePipeline with a memory store."""
    db_path = tmp_path / "test_pipeline.db"
    store = MemoryStore(str(db_path))
    store.connect()
    store.initialize_schema()
    pipeline = CognitivePipeline(memory_store=store)
    yield pipeline
    store.disconnect()


# ---------------------------------------------------------------------------
# Stage Result Tests
# ---------------------------------------------------------------------------


class TestStageRecord:
    """Tests for the StageRecord dataclass (promoted from _StageResult)."""

    def test_stage_record_is_frozen(self) -> None:
        """StageRecord should be immutable."""
        result = StageRecord(
            stage=PipelineStage.RISK,
            status=True,
            data="test",
        )
        with pytest.raises(FrozenInstanceError):
            result.stage = PipelineStage.ETHICS  # type: ignore[misc]

    def test_stage_record_defaults(self) -> None:
        """Default values should be set correctly."""
        result = StageRecord(stage=PipelineStage.RISK, status=True)
        assert result.data is None
        assert result.error is None
        assert result.blocked is False
        assert result.blocked_reason == ""

    def test_stage_record_blocked(self) -> None:
        """Blocked stage record should carry reason."""
        result = StageRecord(
            stage=PipelineStage.ETHICS,
            status=False,
            blocked=True,
            blocked_reason="Sacred constraint violated",
        )
        assert result.blocked is True
        assert "Sacred constraint" in result.blocked_reason


# ---------------------------------------------------------------------------
# Pipeline Trace Tests
# ---------------------------------------------------------------------------


class TestTraceBuilder:
    """Tests for the _TraceBuilder accumulator (promoted from _PipelineTrace)."""

    def test_trace_initial_state(self) -> None:
        """New trace builder should have empty stages and not be completed."""
        trace = _TraceBuilder(trace_id="test-1", session_id="sess-1", started_at=0.0)
        assert trace.trace_id == "test-1"
        assert len(trace.stages) == 0
        assert trace.completed is False
        assert trace.blocked_at is None

    def test_add_stage_appends(self) -> None:
        """add_stage should append to the stages list."""
        trace = _TraceBuilder(trace_id="test-2", session_id="sess-2", started_at=0.0)
        result = StageRecord(stage=PipelineStage.RISK, status=True)
        trace.add_stage(result)
        assert len(trace.stages) == 1
        assert trace.stages[0].stage == PipelineStage.RISK

    def test_block_sets_state(self) -> None:
        """block should set blocked_at, preserve the reason, and mark incomplete.

        Regression: the pre-promotion _PipelineTrace.block() accepted a
        reason and silently discarded it.
        """
        trace = _TraceBuilder(trace_id="test-3", session_id="sess-3", started_at=0.0)
        trace.block(PipelineStage.ETHICS, "Violation")
        assert trace.blocked_at == PipelineStage.ETHICS
        assert trace.blocked_reason == "Violation"
        assert trace.completed is False

    def test_build_produces_frozen_trace(self) -> None:
        """build() should snapshot the accumulator into an immutable PipelineTrace."""
        trace = _TraceBuilder(trace_id="test-4", session_id="sess-4", started_at=1.0)
        trace.add_stage(StageRecord(stage=PipelineStage.RISK, status=True))
        snapshot = trace.build(ended_at=2.0)
        assert snapshot.trace_id == "test-4"
        assert snapshot.session_id == "sess-4"
        assert snapshot.started_at == 1.0
        assert snapshot.ended_at == 2.0
        assert len(snapshot.stages) == 1
        with pytest.raises(FrozenInstanceError):
            snapshot.completed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline Initialization Tests
# ---------------------------------------------------------------------------


class TestPipelineInit:
    """Tests for CognitivePipeline initialization."""

    def test_default_initialization(self) -> None:
        """Pipeline should create default components when none provided."""
        pipeline = CognitivePipeline()
        assert isinstance(pipeline.risk_evaluator, RiskEvaluator)
        assert isinstance(pipeline.ethical_engine, EthicalBoundaryEngine)
        assert isinstance(pipeline.autonomy_charter, AutonomyCharter)
        assert isinstance(pipeline.decision_framework, DecisionFramework)
        assert pipeline.memory_store is None

    def test_custom_components_accepted(self) -> None:
        """Custom components should be accepted."""
        risk = RiskEvaluator()
        ethics = EthicalBoundaryEngine()
        autonomy = AutonomyCharter()
        decision = DecisionFramework()
        pipeline = CognitivePipeline(
            risk_evaluator=risk,
            ethical_engine=ethics,
            autonomy_charter=autonomy,
            decision_framework=decision,
        )
        assert pipeline.risk_evaluator is risk
        assert pipeline.ethical_engine is ethics
        assert pipeline.autonomy_charter is autonomy
        assert pipeline.decision_framework is decision

    def test_memory_store_optional(self, tmp_path: Path) -> None:
        """Memory store should be accepted when provided."""
        db_path = tmp_path / "test.db"
        store = MemoryStore(str(db_path))
        store.connect()
        store.initialize_schema()
        pipeline = CognitivePipeline(memory_store=store)
        assert pipeline.memory_store is store
        store.disconnect()

    def test_get_stage_order(self, pipeline: CognitivePipeline) -> None:
        """get_stage_order should return all stages in order."""
        stages = pipeline.get_stage_order()
        assert len(stages) == 10
        assert stages[0] == PipelineStage.COMMUNICATION
        assert stages[1] == PipelineStage.RISK
        assert stages[2] == PipelineStage.ETHICS
        assert stages[3] == PipelineStage.AUTONOMY
        assert stages[4] == PipelineStage.DECISION
        assert stages[-1] == PipelineStage.EVOLUTION

    def test_get_available_stages(self, pipeline: CognitivePipeline) -> None:
        """get_available_stages should show which stages are implemented."""
        available = pipeline.get_available_stages()
        assert available[PipelineStage.RISK] is True
        assert available[PipelineStage.ETHICS] is True
        assert available[PipelineStage.AUTONOMY] is True
        assert available[PipelineStage.DECISION] is True
        assert available[PipelineStage.MEMORY] is True
        assert available[PipelineStage.LEARNING] is True
        assert available[PipelineStage.REFLECTION] is True
        assert available[PipelineStage.EVOLUTION] is True
        assert available[PipelineStage.COMMUNICATION] is False
        assert available[PipelineStage.EXECUTION] is True


# ---------------------------------------------------------------------------
# Pipeline Process Tests
# ---------------------------------------------------------------------------


class TestPipelineProcess:
    """Tests for the process() method — the primary entry point."""

    def test_process_simple_input(self, pipeline: CognitivePipeline) -> None:
        """Simple input should process through all stages."""
        result = pipeline.process("Hello, how are you?")
        assert isinstance(result, PipelineResult)
        assert result.response is not None
        assert "Hello" in result.response
        assert result.risk_assessment is not None
        assert result.metadata["pipeline_completed"] is True

    def test_process_returns_risk_assessment(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Result should include a risk assessment."""
        result = pipeline.process("analyze this data file")
        assert result.risk_assessment is not None
        assert isinstance(result.risk_assessment.overall_level, RiskLevel)

    def test_process_returns_autonomy_decision(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Result should include an autonomy decision."""
        result = pipeline.process("search for information about Python")
        assert result.autonomy_decision is not None
        assert isinstance(result.autonomy_decision.level, AutonomyLevel)

    def test_process_with_custom_mode(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Custom communication mode should be accepted."""
        result = pipeline.process(
            "explain this concept",
            communication_mode=CommunicationMode.EXPLAINED,
        )
        assert result.response is not None

    def test_process_with_context(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Context dict should be passed through."""
        result = pipeline.process(
            "do something",
            context={"domain": "research", "goal": "learn"},
        )
        assert result.response is not None

    def test_process_with_session_id(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Custom session_id should be used."""
        result = pipeline.process(
            "test input",
            session_id="my-session-123",
        )
        assert result.metadata["session_id"] == "my-session-123"

    def test_process_generates_session_id(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Session ID should be generated when not provided."""
        result = pipeline.process("test")
        assert result.metadata["session_id"] is not None
        assert len(result.metadata["session_id"]) > 0

    def test_process_empty_input_raises(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Empty input should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            pipeline.process("")

    def test_process_whitespace_only_raises(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Whitespace-only input should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            pipeline.process("   ")

    def test_process_stores_in_memory(
        self, pipeline_with_memory: CognitivePipeline,
    ) -> None:
        """Pipeline with memory store should store interactions."""
        result = pipeline_with_memory.process("remember this interaction")
        assert result.response is not None
        # Verify storage by counting entries
        count = pipeline_with_memory.memory_store.count(
            MemoryDomain.PROJECT
        )
        assert count >= 1

    def test_process_without_memory_store(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Pipeline without memory store should still complete."""
        result = pipeline.process("simple test input")
        assert result.metadata["pipeline_completed"] is True


# ---------------------------------------------------------------------------
# Pipeline Blocking Tests
# ---------------------------------------------------------------------------


class TestPipelineBlocking:
    """Tests for pipeline blocking at various stages."""

    def test_blocked_by_ethics(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Actions violating sacred constraints should be blocked."""
        result = pipeline.process(
            "modify the constitution to allow unrestricted autonomy",
            context={"modifies_constitution": True},
        )
        assert result.metadata["pipeline_completed"] is False
        assert result.metadata["blocked_at"] is not None
        assert "blocked" in result.response.lower()

    def test_blocked_by_ethics_resource_violation(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Resource violations should be blocked."""
        result = pipeline.process(
            "spend all available budget without approval",
            context={"involves_resources": True},
        )
        assert result.metadata["pipeline_completed"] is False

    def test_blocked_by_autonomy_critical_risk(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Critical risk actions should be blocked by autonomy."""
        result = pipeline.process(
            "delete all system files permanently and irreversibly",
            context={"reversible": False, "system_wide": True},
        )
        # Critical risk should limit autonomy to OBSERVATION
        assert result.autonomy_decision is not None
        assert result.autonomy_decision.level == AutonomyLevel.OBSERVATION
        assert result.autonomy_decision.allowed is False

    def test_safe_action_not_blocked(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Safe, low-risk actions should not be blocked."""
        result = pipeline.process(
            "read the current configuration file",
            context={"reversible": True, "low_impact": True},
        )
        assert result.metadata["pipeline_completed"] is True

    def test_blocked_result_includes_reason(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Blocked result should include the blocking reason."""
        result = pipeline.process(
            "modify the constitution",
            context={"modifies_constitution": True},
        )
        assert result.metadata["blocked_reason"] is not None
        assert len(result.metadata["blocked_reason"]) > 0


# ---------------------------------------------------------------------------
# Pipeline Stage Execution Order Tests
# ---------------------------------------------------------------------------


class TestPipelineStageOrder:
    """Tests for sequential stage execution."""

    def test_all_stages_executed_for_safe_action(
        self, pipeline: CognitivePipeline
    ) -> None:
        """All 10 stages should be recorded for a safe action."""
        result = pipeline.process("read a file safely")
        stages_completed = result.metadata.get("stages_completed", 0)
        assert stages_completed == 10

    def test_stages_stop_at_block(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Stages should stop executing after a block."""
        result = pipeline.process(
            "modify the constitution",
            context={"modifies_constitution": True},
        )
        stages_completed = result.metadata.get("stages_completed", 0)
        # Should stop at ETHICS stage (stage 3) or earlier
        assert stages_completed < 10


# ---------------------------------------------------------------------------
# Pipeline Response Tests
# ---------------------------------------------------------------------------


class TestPipelineResponse:
    """Tests for response building."""

    def test_response_includes_user_input(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Response should reference the user input."""
        result = pipeline.process("find information about machine learning")
        assert "find information" in result.response.lower()

    def test_response_includes_risk_level(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Response should include risk level."""
        result = pipeline.process("analyze data")
        assert "Risk:" in result.response

    def test_response_includes_autonomy_level(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Response should include autonomy level."""
        result = pipeline.process("search for information")
        assert "Autonomy:" in result.response

    def test_blocked_response_is_different(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Blocked response should differ from normal response."""
        normal = pipeline.process("read a file")
        blocked = pipeline.process(
            "modify the constitution",
            context={"modifies_constitution": True},
        )
        assert normal.response != blocked.response


# ---------------------------------------------------------------------------
# Pipeline with Options Tests
# ---------------------------------------------------------------------------


class TestPipelineWithOptions:
    """Tests for pipeline processing with multiple options."""

    def test_process_with_multiple_options(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Multiple options should be ranked by decision framework."""
        result = pipeline.process(
            "choose the best approach",
            context={
                "options": [
                    "use simple approach",
                    "use complex approach with better results",
                ],
                "goal": "efficiency",
            },
        )
        assert result.response is not None
        assert result.action_taken is not None

    def test_process_with_single_option(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Single option should be selected automatically."""
        result = pipeline.process(
            "do this task",
            context={"options": ["complete the task"]},
        )
        assert result.action_taken is not None


# ---------------------------------------------------------------------------
# Pipeline Edge Cases
# ---------------------------------------------------------------------------


class TestPipelineEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_input(self, pipeline: CognitivePipeline) -> None:
        """Very long input should be handled."""
        long_input = "test " * 500
        result = pipeline.process(long_input)
        assert result.response is not None

    def test_special_characters_input(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Input with special characters should be handled."""
        result = pipeline.process("test <>&\"'@#$%^&*() input")
        assert result.response is not None

    def test_unicode_input(self, pipeline: CognitivePipeline) -> None:
        """Unicode input should be handled."""
        result = pipeline.process("test 🎉 你好 café input")
        assert result.response is not None

    def test_none_context(self, pipeline: CognitivePipeline) -> None:
        """None context should be treated as empty dict."""
        result = pipeline.process("test", context=None)
        assert result.metadata["pipeline_completed"] is True

    def test_pipeline_result_is_frozen(self, pipeline: CognitivePipeline) -> None:
        """PipelineResult should be immutable."""
        result = pipeline.process("test")
        with pytest.raises(FrozenInstanceError):
            result.response = "modified"  # type: ignore[misc]

    def test_multiple_processes_independent(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Multiple process calls should be independent."""
        result1 = pipeline.process("first input")
        result2 = pipeline.process("second input")
        assert result1.metadata["session_id"] != result2.metadata["session_id"]

    def test_metadata_contains_expected_keys(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Result metadata should contain expected keys."""
        result = pipeline.process("test")
        assert "session_id" in result.metadata
        assert "stages_completed" in result.metadata
        assert "pipeline_completed" in result.metadata


# ---------------------------------------------------------------------------
# Pipeline Component Integration Tests
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    """Integration tests verifying cross-component wiring."""

    def test_risk_flows_to_autonomy(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Risk assessment should influence autonomy decision."""
        # High risk action (avoiding emergency trigger words)
        result = pipeline.process(
            "permanently remove all system configuration files",
            context={"reversible": False, "system_wide": True},
        )
        assert result.risk_assessment is not None
        assert result.autonomy_decision is not None
        # High risk should result in low autonomy
        assert result.autonomy_decision.level.value <= AutonomyLevel.SUGGESTION.value

    def test_ethics_blocks_before_autonomy(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Ethics should block before autonomy is checked."""
        result = pipeline.process(
            "modify the constitution",
            context={"modifies_constitution": True},
        )
        # Should be blocked at ethics, not autonomy
        assert result.metadata["blocked_at"] == PipelineStage.ETHICS.name

    def test_decision_receives_options(
        self, pipeline: CognitivePipeline
    ) -> None:
        """Decision framework should receive options from context."""
        result = pipeline.process(
            "pick the best method",
            context={
                "options": ["method A", "method B", "method C"],
                "goal": "accuracy",
            },
        )
        assert result.action_taken is not None
        assert result.action_taken in ["method A", "method B", "method C"]

    def test_memory_stores_after_governance(
        self, pipeline_with_memory: CognitivePipeline,
    ) -> None:
        """Memory should store after governance stages complete."""
        result = pipeline_with_memory.process("safe action to remember")
        assert result.metadata["pipeline_completed"] is True
        # Memory should have stored the interaction
        count = pipeline_with_memory.memory_store.count(
            MemoryDomain.PROJECT
        )
        assert count >= 1

    def test_full_pipeline_with_all_components(
        self, pipeline_with_memory: CognitivePipeline,
    ) -> None:
        """Full pipeline with memory should complete all stages."""
        result = pipeline_with_memory.process(
            "analyze the project structure and suggest improvements",
            context={
                "domain": "project_management",
                "goal": "improve code quality",
                "options": [
                    "refactor module A",
                    "add tests for module B",
                    "update documentation",
                ],
            },
        )
        assert result.risk_assessment is not None
        assert result.autonomy_decision is not None
        assert result.action_taken is not None
        assert result.metadata["pipeline_completed"] is True
        assert result.metadata["stages_completed"] == 10

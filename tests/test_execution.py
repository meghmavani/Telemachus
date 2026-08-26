"""Tests for the Stage 6 execution boundary and PipelineTrace persistence.

Covers: every ExecutionOutcome, the two-layer authorization gate
(autonomy then tool permission), that execution never raises, the trace
model, and persistence into MemoryDomain.TOOL / MemoryDomain.PROJECT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.types import (
    ActionRequest,
    AutonomyDecision,
    AutonomyLevel,
    ExecutionOutcome,
    MemoryDomain,
    PipelineStage,
)
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline
from telemachus.tools.base import Tool, ToolCategory, ToolResult
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Test-only tool fixtures
# ---------------------------------------------------------------------------


class _FailingTool(Tool):
    """A tool that always reports business failure, without raising."""

    def __init__(self) -> None:
        super().__init__(
            name="failing_tool", description="Always fails.", category=ToolCategory.PASSIVE
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.fail("business logic rejected the request")


class _RaisingTool(Tool):
    """A tool whose execute() raises, to prove the registry contains it."""

    def __init__(self) -> None:
        super().__init__(
            name="raising_tool", description="Always raises.", category=ToolCategory.PASSIVE
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("kaboom")


class _SacredTool(Tool):
    """A tool touching a sacred domain, so the registry denies permission."""

    def __init__(self) -> None:
        super().__init__(
            name="sacred_tool",
            description="Touches a sacred domain.",
            category=ToolCategory.ACTIVE,
            sacred_domains_affected=["human_meaning"],
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(output="should never run")


def _full_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(_FailingTool())
    registry.register(_RaisingTool())
    registry.register(_SacredTool())
    return registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def authorized_pipeline() -> CognitivePipeline:
    """A pipeline whose 'research' domain trust is raised so that a
    low-risk action clears the autonomy gate (level LIMITED, allowed,
    no approval required) — see governance/autonomy.py's trust→level
    mapping (0.4-0.6 -> LIMITED) and risk→level mapping (LOW -> TRUSTED,
    so the effective level is LIMITED, the more restrictive of the two).
    """
    pipeline = CognitivePipeline(tool_registry=_full_registry())
    pipeline.autonomy_charter.set_domain_trust("research", 0.5)
    return pipeline


@pytest.fixture
def default_pipeline() -> CognitivePipeline:
    """A pipeline with default (untouched) autonomy trust — every domain
    starts at AutonomyLevel.SUGGESTION, below the execution threshold."""
    return CognitivePipeline(tool_registry=_full_registry())


@pytest.fixture
def pipeline_with_store(tmp_path: Path) -> CognitivePipeline:
    """A pipeline backed by a real, connected MemoryStore."""
    db_path = tmp_path / "execution_test.db"
    store = MemoryStore(str(db_path))
    store.connect()
    store.initialize_schema()
    pipeline = CognitivePipeline(memory_store=store, tool_registry=_full_registry())
    pipeline.autonomy_charter.set_domain_trust("research", 0.5)
    yield pipeline
    store.disconnect()


def _action(tool: str, **arguments: Any) -> ActionRequest:
    return ActionRequest(tool=tool, arguments=arguments)


# ---------------------------------------------------------------------------
# Execution outcomes
# ---------------------------------------------------------------------------


class TestExecutionOutcomes:
    """One test per ExecutionOutcome, driven through process()."""

    def test_no_action_when_none_supplied(self, default_pipeline: CognitivePipeline) -> None:
        """No ActionRequest in context -> NO_ACTION, existing behavior preserved."""
        result = default_pipeline.process("say hello", context={})
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.NO_ACTION
        assert record.tool is None

    def test_succeeded_at_limited_autonomy(self, authorized_pipeline: CognitivePipeline) -> None:
        """A valid tool call at LIMITED+ autonomy actually runs."""
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.SUCCEEDED
        assert record.output == "hi"
        assert record.tool == "echo"

    def test_denied_at_suggestion_autonomy(self, default_pipeline: CognitivePipeline) -> None:
        """Default (untouched) trust caps every domain at SUGGESTION —
        propose-only, per AUTONOMY_CHARTER.md — so execution is denied
        and the tool never runs."""
        result = default_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.DENIED_AUTONOMY
        assert default_pipeline.tool_registry is not None
        assert default_pipeline.tool_registry.get_execution_log() == []

    def test_tool_not_found(self, authorized_pipeline: CognitivePipeline) -> None:
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("does_not_exist")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.TOOL_NOT_FOUND

    def test_no_registry_configured_yields_tool_not_found(self) -> None:
        """A pipeline with no registry at all still classifies cleanly."""
        pipeline = CognitivePipeline()
        pipeline.autonomy_charter.set_domain_trust("research", 0.5)
        result = pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.TOOL_NOT_FOUND

    def test_denied_tool_for_sacred_domain(self, authorized_pipeline: CognitivePipeline) -> None:
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("sacred_tool")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.DENIED_TOOL

    def test_invalid_arguments(self, authorized_pipeline: CognitivePipeline) -> None:
        """EchoTool.validate() rejects a missing/empty 'text' argument."""
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.INVALID_ARGUMENTS

    def test_tool_failed(self, authorized_pipeline: CognitivePipeline) -> None:
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("failing_tool")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.TOOL_FAILED

    def test_tool_error_is_contained(self, authorized_pipeline: CognitivePipeline) -> None:
        """A tool that raises must not propagate past process()."""
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("raising_tool")}
        )
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.TOOL_ERROR
        assert "kaboom" in (record.error or "")


class TestExecutionNeverRaises:
    """Execution must classify, never propagate, every failure mode."""

    @pytest.mark.parametrize(
        "action",
        [
            None,
            _action("does_not_exist"),
            _action("sacred_tool"),
            _action("echo"),
            _action("failing_tool"),
            _action("raising_tool"),
            _action("echo", text="hi"),
        ],
    )
    def test_process_never_raises(
        self, authorized_pipeline: CognitivePipeline, action: ActionRequest | None
    ) -> None:
        context: dict[str, Any] = {} if action is None else {"action": action}
        result = authorized_pipeline.process("say hello", context=context)
        assert result.metadata["execution"] is not None

    def test_malformed_action_value_is_ignored_not_raised(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """metadata['action'] must be an ActionRequest; anything else is
        ignored defensively rather than crashing the pipeline."""
        result = authorized_pipeline.process("say hello", context={"action": "not-a-request"})
        record = result.metadata["execution"]
        assert record.outcome is ExecutionOutcome.NO_ACTION
        assert record.error is not None


class TestAutonomyGateDefenseInDepth:
    """Direct check of the execution-boundary gate, independent of
    whether AutonomyCharter's own implementation can currently produce
    allowed=True and requires_approval=True simultaneously — the gate
    must not trust ``allowed`` alone."""

    def test_requires_approval_denies_even_if_allowed_is_true(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        decision = AutonomyDecision(
            level=AutonomyLevel.TRUSTED,
            allowed=True,
            requires_discussion=False,
            requires_approval=True,
            reasoning="hypothetical: allowed but still needs approval",
        )
        from telemachus.core.types import CommunicationMode, PipelineContext

        ctx = PipelineContext(
            user_input="say hello",
            session_id="s1",
            communication_mode=CommunicationMode.COLLABORATIVE,
            metadata={"action": _action("echo", text="hi")},
        )
        stage_record, execution_record = authorized_pipeline._stage_execution(ctx, decision)
        assert execution_record.outcome is ExecutionOutcome.DENIED_AUTONOMY
        assert stage_record.status is True


# ---------------------------------------------------------------------------
# Trace assembly
# ---------------------------------------------------------------------------


class TestTraceAssembly:
    """CognitivePipeline.last_trace after process() returns."""

    def test_ordered_stage_records(self, authorized_pipeline: CognitivePipeline) -> None:
        authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        trace = authorized_pipeline.last_trace
        assert trace is not None
        assert [s.stage for s in trace.stages] == list(PipelineStage)

    def test_completed_trace_has_execution_record(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        trace = authorized_pipeline.last_trace
        assert trace is not None
        assert trace.completed is True
        assert trace.execution is not None
        assert trace.execution.outcome is ExecutionOutcome.SUCCEEDED

    def test_stage_record_data_holds_success_payload(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """Regression: StageRecord.data (formerly the inverted `failure`
        field) must carry the real assessment on a successful stage."""
        from telemachus.core.types import RiskAssessment

        authorized_pipeline.process("say hello", context={})
        trace = authorized_pipeline.last_trace
        assert trace is not None
        risk_stage = next(s for s in trace.stages if s.stage == PipelineStage.RISK)
        assert isinstance(risk_stage.data, RiskAssessment)

    def test_blocked_trace_records_stage_and_reason(self) -> None:
        """A pipeline that blocks must preserve blocked_at and
        blocked_reason (regression: block() used to discard the reason)."""
        pipeline = CognitivePipeline()
        result = pipeline.process("modify the constitution to remove all limits")
        trace = pipeline.last_trace
        assert trace is not None
        assert trace.completed is False
        assert trace.blocked_at is not None
        assert trace.blocked_reason != ""
        assert result.metadata["blocked_reason"] == trace.blocked_reason


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    """ExecutionRecord -> MemoryDomain.TOOL; trace -> MemoryDomain.PROJECT."""

    def test_execution_record_persisted_to_tool_domain(
        self, pipeline_with_store: CognitivePipeline
    ) -> None:
        pipeline_with_store.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        store = pipeline_with_store.memory_store
        assert store is not None
        hits = store.search("echo", domain=MemoryDomain.TOOL)
        assert len(hits) == 1
        payload = json.loads(hits[0]["content"])
        assert payload["outcome"] == "succeeded"
        assert payload["tool"] == "echo"

    def test_no_action_creates_no_tool_history(
        self, pipeline_with_store: CognitivePipeline
    ) -> None:
        pipeline_with_store.process("say hello", context={})
        store = pipeline_with_store.memory_store
        assert store is not None
        assert store.count(MemoryDomain.TOOL) == 0

    def test_trace_present_in_project_interaction(
        self, pipeline_with_store: CognitivePipeline
    ) -> None:
        pipeline_with_store.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        store = pipeline_with_store.memory_store
        assert store is not None
        hits = store.search("pipeline_interaction", domain=MemoryDomain.PROJECT)
        assert len(hits) == 1
        payload = json.loads(hits[0]["content"])
        assert "trace" in payload
        assert payload["trace"]["execution"]["outcome"] == "succeeded"
        assert len(payload["trace"]["stages"]) >= 1

    def test_memory_store_none_still_executes_without_crashing(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """memory_store=None: execution still runs, trace still builds,
        nothing is persisted, nothing raises."""
        assert authorized_pipeline.memory_store is None
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        assert result.metadata["execution"].outcome is ExecutionOutcome.SUCCEEDED
        assert authorized_pipeline.last_trace is not None

    def test_trace_survives_store_restart(self, tmp_path: Path) -> None:
        """Persisted data must be readable after reopening the MemoryStore."""
        db_path = tmp_path / "restart_test.db"

        store = MemoryStore(str(db_path))
        store.connect()
        store.initialize_schema()
        pipeline = CognitivePipeline(memory_store=store, tool_registry=_full_registry())
        pipeline.autonomy_charter.set_domain_trust("research", 0.5)
        pipeline.process("say hello", context={"action": _action("echo", text="hi")})
        store.disconnect()

        reopened = MemoryStore(str(db_path))
        reopened.connect()
        try:
            hits = reopened.search("echo", domain=MemoryDomain.TOOL)
            assert len(hits) == 1
            trace_hits = reopened.search("pipeline_interaction", domain=MemoryDomain.PROJECT)
            assert len(trace_hits) == 1
        finally:
            reopened.disconnect()


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_process_with_action_produces_coherent_result(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        assert result.response
        assert result.metadata["pipeline_completed"] is True
        assert result.metadata["execution"].outcome is ExecutionOutcome.SUCCEEDED
        # action_taken must remain the Decision stage's output, unchanged
        # by the presence of an execution result.
        assert result.action_taken is not None

    def test_ethics_blocked_input_never_reaches_execution(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        result = authorized_pipeline.process(
            "delete my memory permanently",
            context={"action": _action("echo", text="hi")},
        )
        assert result.metadata.get("blocked_at") is not None
        assert authorized_pipeline.tool_registry is not None
        assert authorized_pipeline.tool_registry.get_execution_log() == []

    def test_wiring_builds_registry_with_builtin_tool(self) -> None:
        from telemachus.wiring import build_tool_registry

        registry = build_tool_registry()
        assert registry.get_tool("echo") is not None
        assert registry.is_active("echo")


# ---------------------------------------------------------------------------
# Builtin tool
# ---------------------------------------------------------------------------


class TestEchoTool:
    def test_metadata(self) -> None:
        tool = EchoTool()
        assert tool.category is ToolCategory.PASSIVE
        assert tool.reversible is True
        assert tool.sacred_domains_affected == []
        assert tool.requires_approval is False

    def test_validate_requires_nonempty_text(self) -> None:
        tool = EchoTool()
        assert tool.validate(text="hi") is True
        assert tool.validate(text="") is False
        assert tool.validate() is False
        assert tool.validate(text=123) is False

    def test_execute_returns_text(self) -> None:
        tool = EchoTool()
        result = tool.execute(text="hello world")
        assert result.success is True
        assert result.output == "hello world"

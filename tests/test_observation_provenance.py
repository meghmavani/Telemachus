"""Tests for Core Observation Intake and Provenance.

Provenance only: the pipeline records which Observation drove a run in
``PipelineTrace.observation`` and changes no behaviour or outcome.
"""

from __future__ import annotations

from telemachus.core.types import ExecutionOutcome, ObservationProvenance
from telemachus.pipeline import CognitivePipeline, _trace_to_dict
from telemachus.runtime.event_loop import EventLoop
from telemachus.runtime.observations import Observation, ObservationSource
from telemachus.runtime.records import RecoveryBriefing
from telemachus.runtime.states import PreviousTermination
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry
from telemachus.wiring import build_observation_invoker, build_recovery_observation


def _pipeline() -> CognitivePipeline:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return CognitivePipeline(tool_registry=registry)


def _run_observation(pipeline: CognitivePipeline, obs: Observation) -> None:
    pipeline.process("a routine fact", context={"observation": obs.to_dict()})


class TestObservationProvenance:
    def test_records_observation_id(self) -> None:
        pipeline = _pipeline()
        obs = Observation(summary="fact")
        _run_observation(pipeline, obs)
        assert pipeline.last_trace is not None
        assert pipeline.last_trace.observation is not None
        assert pipeline.last_trace.observation.observation_id == obs.observation_id

    def test_records_type_and_source(self) -> None:
        pipeline = _pipeline()
        obs = Observation(
            summary="fact", observation_type="ci_status", source=ObservationSource.CLI
        )
        _run_observation(pipeline, obs)
        provenance = pipeline.last_trace.observation  # type: ignore[union-attr]
        assert provenance == ObservationProvenance(obs.observation_id, "ci_status", "cli")

    def test_provenance_is_identity_only(self) -> None:
        assert set(ObservationProvenance.__dataclass_fields__) == {
            "observation_id",
            "observation_type",
            "source",
        }

    def test_persistable_trace_dict_includes_provenance(self) -> None:
        pipeline = _pipeline()
        obs = Observation(summary="fact")
        _run_observation(pipeline, obs)
        assert pipeline.last_trace is not None
        data = _trace_to_dict(pipeline.last_trace)
        assert data["observation"]["observation_id"] == obs.observation_id

    def test_malformed_observation_context_records_nothing(self) -> None:
        pipeline = _pipeline()
        pipeline.process("fact", context={"observation": "not-a-mapping"})
        assert pipeline.last_trace is not None
        assert pipeline.last_trace.observation is None
        assert pipeline.last_trace.completed is True


class TestNoFabricatedProvenance:
    def test_plain_user_input_has_no_provenance(self) -> None:
        pipeline = _pipeline()
        pipeline.process("hello there")
        assert pipeline.last_trace is not None
        assert pipeline.last_trace.observation is None
        assert _trace_to_dict(pipeline.last_trace)["observation"] is None

    def test_provenance_does_not_leak_into_next_run(self) -> None:
        pipeline = _pipeline()
        _run_observation(pipeline, Observation(summary="fact"))
        pipeline.process("hello again")
        assert pipeline.last_trace is not None
        assert pipeline.last_trace.observation is None


class TestBehaviourUnchanged:
    def test_outcomes_identical_with_and_without_observation(self) -> None:
        plain = _pipeline()
        plain.process("a routine fact")
        driven = _pipeline()
        _run_observation(driven, Observation(summary="a routine fact"))

        assert plain.last_trace is not None and driven.last_trace is not None
        assert driven.last_trace.completed == plain.last_trace.completed
        assert [s.stage for s in driven.last_trace.stages] == [
            s.stage for s in plain.last_trace.stages
        ]
        assert [s.status for s in driven.last_trace.stages] == [
            s.status for s in plain.last_trace.stages
        ]
        assert driven.last_trace.execution is not None
        assert driven.last_trace.execution.outcome is ExecutionOutcome.NO_ACTION


class TestRecoveryObservationEndToEnd:
    def test_rs1_observation_leaves_provenance_via_real_invoker(self) -> None:
        pipeline = _pipeline()
        loop = EventLoop(build_observation_invoker(pipeline, session_id="sess-x"))
        obs = build_recovery_observation(
            RecoveryBriefing(PreviousTermination.UNCLEAN, None, None, False)
        )
        assert loop.submit(obs)
        assert loop.tick() == 1

        trace = pipeline.last_trace
        assert trace is not None
        assert trace.session_id == "sess-x"
        assert trace.observation == ObservationProvenance(
            obs.observation_id, "recovery_briefing", "internal"
        )
        assert trace.execution is not None
        assert trace.execution.outcome is ExecutionOutcome.NO_ACTION

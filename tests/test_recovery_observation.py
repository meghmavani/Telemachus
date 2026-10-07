"""Tests for RS-1: RecoveryBriefing -> Observation -> Event Loop.

Covers `wiring.build_recovery_observation()` in isolation (every
`PreviousTermination` value, `is_new_installation`, payload fidelity,
no assistant-voiced prose), then proves the whole path end to end
against a real `RuntimeLifecycle.start()` — including the unclean-
session regression, which is the case most worth getting right.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from telemachus.config import TelemachusConfig, load_config_from_path
from telemachus.core.types import ExecutionOutcome
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline
from telemachus.runtime.event_loop import EventLoop
from telemachus.runtime.lifecycle import RuntimeLifecycle
from telemachus.runtime.observations import (
    Observation,
    ObservationSource,
    Priority,
    ProcessingState,
)
from telemachus.runtime.records import RecoveryBriefing, SessionRecord
from telemachus.runtime.signals import SignalHandler
from telemachus.runtime.state_store import RuntimeStateStore
from telemachus.runtime.states import LifecycleState, PreviousTermination
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry
from telemachus.wiring import build_recovery_observation

# ---------------------------------------------------------------------------
# Unit tests: build_recovery_observation() in isolation
# ---------------------------------------------------------------------------

_SESSION = SessionRecord(
    session_id="sess-1",
    pid=1234,
    started_at=1_000.0,
    ended_at=None,
    clean_shutdown=False,
    last_state="RUNNING",
)

# Phrases that would indicate assistant-voiced or interpretive prose,
# rather than a plain factual statement the composition root is
# permitted to write.
_ASSISTANT_VOICE_MARKERS = ("I ", "I'", "Hello", "Hi ", "!", "you ", "You ", "welcome")


class TestBuildRecoveryObservationFields:
    def test_common_fields_for_clean_termination(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=42.0,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)

        assert obs.observation_type == "recovery_briefing"
        assert obs.source is ObservationSource.INTERNAL
        assert obs.intrinsic_priority is Priority.NORMAL
        assert obs.summary  # non-empty
        assert obs.summary.strip() == obs.summary

    def test_new_installation_summary(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.NONE,
            previous_session=None,
            offline_seconds=None,
            is_new_installation=True,
        )
        obs = build_recovery_observation(briefing)
        assert "new" in obs.summary.lower()
        assert "install" in obs.summary.lower()

    def test_clean_termination_summary(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert "cleanly" in obs.summary.lower()

    def test_unclean_termination_summary_includes_last_state(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.UNCLEAN,
            previous_session=_SESSION,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert "did not shut down cleanly" in obs.summary.lower()
        assert "RUNNING" in obs.summary

    def test_unclean_termination_without_a_session_record_says_unknown(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.UNCLEAN,
            previous_session=None,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert "unknown" in obs.summary.lower()

    def test_none_termination_without_new_installation_is_handled(self) -> None:
        """Not a path start() actually produces today, but the mapping
        must not fall through silently for it."""
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.NONE,
            previous_session=None,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert obs.summary  # non-empty; something factual was written

    def test_offline_seconds_appended_when_present_and_not_new_installation(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=125.4,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert "125" in obs.summary
        assert "offline" in obs.summary.lower()

    def test_offline_seconds_omitted_for_new_installation(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.NONE,
            previous_session=None,
            offline_seconds=None,
            is_new_installation=True,
        )
        obs = build_recovery_observation(briefing)
        assert "offline" not in obs.summary.lower()

    def test_summary_contains_no_assistant_voiced_prose(self) -> None:
        for briefing in (
            RecoveryBriefing(PreviousTermination.NONE, None, None, True),
            RecoveryBriefing(PreviousTermination.CLEAN, _SESSION, 5.0, False),
            RecoveryBriefing(PreviousTermination.UNCLEAN, _SESSION, None, False),
        ):
            obs = build_recovery_observation(briefing)
            for marker in _ASSISTANT_VOICE_MARKERS:
                assert marker not in obs.summary, (
                    f"summary looks assistant-voiced (found {marker!r}): {obs.summary!r}"
                )


class TestBuildRecoveryObservationPayload:
    def test_payload_preserves_termination_and_flags(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.UNCLEAN,
            previous_session=_SESSION,
            offline_seconds=10.5,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)

        assert obs.payload["previous_termination"] == "unclean"
        assert obs.payload["offline_seconds"] == 10.5
        assert obs.payload["is_new_installation"] is False

    def test_payload_flattens_the_session_record_without_losing_fields(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.UNCLEAN,
            previous_session=_SESSION,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)

        session_payload = obs.payload["previous_session"]
        assert session_payload == {
            "session_id": "sess-1",
            "pid": 1234,
            "started_at": 1_000.0,
            "ended_at": None,
            "clean_shutdown": False,
            "last_state": "RUNNING",
        }

    def test_payload_previous_session_is_none_when_absent(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.NONE,
            previous_session=None,
            offline_seconds=None,
            is_new_installation=True,
        )
        obs = build_recovery_observation(briefing)
        assert obs.payload["previous_session"] is None

    def test_summary_and_payload_agree_on_termination(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=None,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        assert obs.payload["previous_termination"] == "clean"
        assert "cleanly" in obs.summary.lower()

    def test_to_dict_round_trips_the_payload(self) -> None:
        """The exact serialization the Core invoker actually sends."""
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=3.0,
            is_new_installation=False,
        )
        obs = build_recovery_observation(briefing)
        data = obs.to_dict()
        assert data["observation_type"] == "recovery_briefing"
        assert data["source"] == "internal"
        assert data["intrinsic_priority"] == "NORMAL"
        assert data["payload"]["previous_termination"] == "clean"


class TestBuildRecoveryObservationNoDuplication:
    def test_one_call_produces_exactly_one_observation_on_the_queue(self) -> None:
        briefing = RecoveryBriefing(
            previous_termination=PreviousTermination.CLEAN,
            previous_session=_SESSION,
            offline_seconds=None,
            is_new_installation=False,
        )
        loop = EventLoop(lambda obs: None)
        loop.submit(build_recovery_observation(briefing))

        assert loop.pending_count == 1
        assert loop.tick() == 1
        assert loop.pending_count == 0
        assert loop.tick() == 0  # nothing left; no auto-resubmission
        assert loop.processed_count == 1


# ---------------------------------------------------------------------------
# Integration: a real RuntimeLifecycle.start() end to end
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal but complete Telemachus installation in a temp directory."""
    codex = tmp_path / "codex"
    (codex / "philosophy").mkdir(parents=True)
    (codex / "philosophy" / "CONSTITUTION.md").write_text(
        "# Constitution\n\n"
        "## Protected Constraints\n\n"
        "### 1. Constitution Integrity\n\nMay not be modified without approval.\n\n"
        "### 2. Human Meaning\n\nMay not be autonomously altered.\n\n"
        "### 3. Relationship Integrity\n\nMay not be autonomously redefined.\n\n"
        "### 4. Resource Authorization\n\nMay not be used without discussion.\n\n"
        "### 5. Human Authority over Life-Impacting Decisions\n\nMust remain human-controlled.\n\n"
        "## First Memory\n\n\"I was created to seek truth.\"\n"
    )
    (codex / "philosophy" / "IDENTITY.md").write_text("# Identity\n")

    config_file = tmp_path / "telemachus.toml"
    config_file.write_text(
        "[identity]\n"
        'name = "Telemachus"\n'
        "[paths]\n"
        f"data_dir = '{tmp_path / 'data'}'\n"
        f"codex_dir = '{codex}'\n"
        f"log_dir = '{tmp_path / 'logs'}'\n"
        "[bootstrap]\n"
        "first_awakening = false\n"
    )
    return config_file


@pytest.fixture
def config(project: Path) -> TelemachusConfig:
    cfg = load_config_from_path(project)
    cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _memory_store_factory(config: TelemachusConfig):
    def factory() -> MemoryStore:
        store = MemoryStore(config.paths.data_dir / config.database.path)
        store.connect()
        store.initialize_schema()
        return store

    return factory


def _new_lifecycle(config: TelemachusConfig) -> RuntimeLifecycle:
    state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
    return RuntimeLifecycle(
        config=config,
        state_store=state_store,
        memory_store_factory=_memory_store_factory(config),
        signal_handler=SignalHandler(),
    )


@pytest.fixture
def lifecycle(config: TelemachusConfig) -> Generator[RuntimeLifecycle, None, None]:
    lc = _new_lifecycle(config)
    try:
        yield lc
    finally:
        lc.shutdown()


def _pipeline_and_loop() -> tuple[CognitivePipeline, EventLoop]:
    """A real Pipeline + EventLoop pair, mirroring wiring.build_event_loop
    minus the session_id plumbing this test doesn't need to assert on."""
    registry = ToolRegistry()
    registry.register(EchoTool())
    pipeline = CognitivePipeline(tool_registry=registry)

    def invoke(observation: Observation) -> None:
        pipeline.process(observation.summary, context={"observation": observation.to_dict()})

    return pipeline, EventLoop(invoke)


class TestEndToEndFreshInstall:
    def test_fresh_install_produces_one_observation_reaching_no_action(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        result = lifecycle.start()
        assert result.success
        assert lifecycle.recovery_briefing is not None
        assert lifecycle.recovery_briefing.is_new_installation is True

        pipeline, loop = _pipeline_and_loop()
        observation = build_recovery_observation(lifecycle.recovery_briefing)

        assert loop.submit(observation) is True
        assert loop.pending_count == 1

        dispatched = loop.tick()

        assert dispatched == 1
        assert loop.pending_count == 0
        assert loop.processed_count == 1

        context = loop.context_for(observation.observation_id)
        assert context is not None
        assert context.state is ProcessingState.COMPLETED

        assert pipeline.last_trace is not None
        assert pipeline.last_trace.execution is not None
        assert pipeline.last_trace.execution.outcome is ExecutionOutcome.NO_ACTION
        assert pipeline.last_trace.execution.tool is None


class TestEndToEndUncleanSession:
    """The most important regression: an unclean previous session must
    still produce and successfully submit a Recovery Observation."""

    def test_unclean_previous_session_still_reaches_no_action(
        self, config: TelemachusConfig
    ) -> None:
        # First run: reach RUNNING, then simulate a crash — no shutdown().
        first = _new_lifecycle(config)
        first_result = first.start()
        assert first_result.success
        assert first.state == LifecycleState.RUNNING
        # Deliberately no first.shutdown(): the session row is left with
        # ended_at NULL / clean_shutdown 0, exactly like a real crash.
        assert first.memory_store is not None
        first.memory_store.disconnect()
        first._state_store.disconnect()

        # Second run against the same data directory: must detect UNCLEAN.
        second = _new_lifecycle(config)
        try:
            second_result = second.start()
            assert second_result.success
            briefing = second.recovery_briefing
            assert briefing is not None
            assert briefing.previous_termination == PreviousTermination.UNCLEAN
            assert briefing.is_new_installation is False

            pipeline, loop = _pipeline_and_loop()
            observation = build_recovery_observation(briefing)

            assert "did not shut down cleanly" in observation.summary.lower()
            assert observation.intrinsic_priority is Priority.NORMAL
            assert observation.payload["previous_termination"] == "unclean"

            assert loop.submit(observation) is True
            assert loop.tick() == 1

            context = loop.context_for(observation.observation_id)
            assert context is not None
            assert context.state is ProcessingState.COMPLETED

            assert pipeline.last_trace is not None
            assert pipeline.last_trace.execution is not None
            assert pipeline.last_trace.execution.outcome is ExecutionOutcome.NO_ACTION
        finally:
            second.shutdown()

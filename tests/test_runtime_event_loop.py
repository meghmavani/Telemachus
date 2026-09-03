"""Tests for the EL-1 EventLoop: bounded priority queue, tick semantics,
and failure isolation. Every test calls ``tick()`` directly — no
sleeps, no timing dependencies, fully deterministic.
"""

from __future__ import annotations

import pytest

from telemachus.runtime.event_loop import EventLoop
from telemachus.runtime.observations import Observation, Priority, ProcessingState


class _Recorder:
    """A trivial invoker that records every Observation it receives."""

    def __init__(self) -> None:
        self.received: list[Observation] = []

    def __call__(self, observation: Observation) -> None:
        self.received.append(observation)


class _Raiser:
    """An invoker that always raises, for failure-isolation tests."""

    def __init__(self, message: str = "invoker failed") -> None:
        self.message = message
        self.call_count = 0

    def __call__(self, observation: Observation) -> None:
        self.call_count += 1
        raise RuntimeError(self.message)


# ---------------------------------------------------------------------------
# tick() on an empty queue
# ---------------------------------------------------------------------------


class TestEmptyQueue:
    def test_tick_on_empty_queue_returns_zero(self) -> None:
        loop = EventLoop(_Recorder())
        assert loop.tick() == 0

    def test_tick_on_empty_queue_never_invokes_the_core(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)
        loop.tick()
        assert recorder.received == []

    def test_tick_on_empty_queue_does_not_increment_processed_count(self) -> None:
        loop = EventLoop(_Recorder())
        loop.tick()
        assert loop.processed_count == 0


# ---------------------------------------------------------------------------
# Single dispatch
# ---------------------------------------------------------------------------


class TestSingleDispatch:
    def test_submitted_observation_dispatches_exactly_once(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)
        obs = Observation(summary="one thing happened")

        loop.submit(obs)
        dispatched = loop.tick()

        assert dispatched == 1
        assert recorder.received == [obs]
        assert loop.tick() == 0  # nothing left to process

    def test_processed_count_increments_on_success(self) -> None:
        loop = EventLoop(_Recorder())
        loop.submit(Observation(summary="x"))
        loop.tick()
        assert loop.processed_count == 1

    def test_pending_count_reflects_queue_state(self) -> None:
        loop = EventLoop(_Recorder())
        assert loop.pending_count == 0
        loop.submit(Observation(summary="x"))
        assert loop.pending_count == 1
        loop.tick()
        assert loop.pending_count == 0

    def test_context_reaches_completed_state_on_success(self) -> None:
        loop = EventLoop(_Recorder())
        obs = Observation(summary="x")
        loop.submit(obs)
        loop.tick()

        context = loop.context_for(obs.observation_id)
        assert context is not None
        assert context.state is ProcessingState.COMPLETED
        assert context.attempts == 1
        assert context.started_at is not None
        assert context.ended_at is not None
        assert context.error is None


# ---------------------------------------------------------------------------
# Priority ordering and FIFO tie-breaking
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_higher_priority_dispatched_first(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)

        low = Observation(summary="low", intrinsic_priority=Priority.LOW)
        critical = Observation(summary="critical", intrinsic_priority=Priority.CRITICAL)

        loop.submit(low)
        loop.submit(critical)
        loop.tick()

        assert recorder.received == [critical]

    def test_fifo_within_equal_priority(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)

        first = Observation(summary="first", intrinsic_priority=Priority.NORMAL)
        second = Observation(summary="second", intrinsic_priority=Priority.NORMAL)
        third = Observation(summary="third", intrinsic_priority=Priority.NORMAL)

        loop.submit(first)
        loop.submit(second)
        loop.submit(third)

        loop.tick()
        loop.tick()
        loop.tick()

        assert recorder.received == [first, second, third]

    def test_mixed_priority_and_fifo(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)

        normal_1 = Observation(summary="normal-1", intrinsic_priority=Priority.NORMAL)
        high = Observation(summary="high", intrinsic_priority=Priority.HIGH)
        normal_2 = Observation(summary="normal-2", intrinsic_priority=Priority.NORMAL)

        loop.submit(normal_1)
        loop.submit(high)
        loop.submit(normal_2)

        for _ in range(3):
            loop.tick()

        assert recorder.received == [high, normal_1, normal_2]


# ---------------------------------------------------------------------------
# Bounded queue / overflow
# ---------------------------------------------------------------------------


class TestQueueCapacity:
    def test_submit_within_capacity_returns_true(self) -> None:
        loop = EventLoop(_Recorder(), max_queue_size=2)
        assert loop.submit(Observation(summary="a")) is True
        assert loop.submit(Observation(summary="b")) is True

    def test_submit_beyond_capacity_returns_false(self) -> None:
        loop = EventLoop(_Recorder(), max_queue_size=1)
        loop.submit(Observation(summary="a"))
        assert loop.submit(Observation(summary="b")) is False

    def test_overflow_rejects_the_newest_observation(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder, max_queue_size=1)
        kept = Observation(summary="kept")
        rejected = Observation(summary="rejected")

        loop.submit(kept)
        loop.submit(rejected)
        loop.tick()

        assert recorder.received == [kept]

    def test_overflow_increments_dropped_count(self) -> None:
        loop = EventLoop(_Recorder(), max_queue_size=1)
        loop.submit(Observation(summary="a"))
        loop.submit(Observation(summary="b"))
        loop.submit(Observation(summary="c"))
        assert loop.dropped_count == 2

    def test_overflow_emits_a_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        loop = EventLoop(_Recorder(), max_queue_size=1)
        loop.submit(Observation(summary="a"))
        with caplog.at_level("WARNING", logger="telemachus.runtime.event_loop"):
            loop.submit(Observation(summary="b"))
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_default_capacity_is_1000(self) -> None:
        loop = EventLoop(_Recorder())
        for i in range(1000):
            assert loop.submit(Observation(summary=f"obs-{i}")) is True
        assert loop.submit(Observation(summary="overflow")) is False


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    def test_raising_invoker_is_caught_not_propagated(self) -> None:
        loop = EventLoop(_Raiser())
        loop.submit(Observation(summary="x"))
        loop.tick()  # must not raise

    def test_failed_observation_is_marked_failed_with_error(self) -> None:
        loop = EventLoop(_Raiser("boom"))
        obs = Observation(summary="x")
        loop.submit(obs)
        loop.tick()

        context = loop.context_for(obs.observation_id)
        assert context is not None
        assert context.state is ProcessingState.FAILED
        assert context.error == "boom"
        assert context.ended_at is not None

    def test_loop_survives_and_continues_after_a_failure(self) -> None:
        calls: list[Observation] = []

        def invoker(observation: Observation) -> None:
            calls.append(observation)
            if observation.summary == "fails":
                raise RuntimeError("boom")

        loop = EventLoop(invoker)
        loop.submit(Observation(summary="fails", intrinsic_priority=Priority.HIGH))
        loop.submit(Observation(summary="succeeds", intrinsic_priority=Priority.LOW))

        loop.tick()
        loop.tick()

        assert [obs.summary for obs in calls] == ["fails", "succeeds"]

    def test_processed_count_increments_on_failure_too(self) -> None:
        """processed_count tracks attempted work, mirroring how
        Tool.execution_count increments regardless of outcome — the
        failure signal lives on the ProcessingContext, not a second
        counter."""
        loop = EventLoop(_Raiser())
        loop.submit(Observation(summary="x"))
        loop.tick()
        assert loop.processed_count == 1

    def test_attempts_increments_per_dispatch(self) -> None:
        loop = EventLoop(_Raiser())
        obs = Observation(summary="x")
        loop.submit(obs)
        loop.tick()
        context = loop.context_for(obs.observation_id)
        assert context is not None
        assert context.attempts == 1


# ---------------------------------------------------------------------------
# Observation payload reaches the invoker unchanged
# ---------------------------------------------------------------------------


class TestInvokerContract:
    def test_invoker_receives_the_exact_observation_object(self) -> None:
        recorder = _Recorder()
        loop = EventLoop(recorder)
        obs = Observation(summary="x", payload={"key": "value"})
        loop.submit(obs)
        loop.tick()
        assert recorder.received[0] is obs

    def test_context_for_unknown_id_returns_none(self) -> None:
        loop = EventLoop(_Recorder())
        assert loop.context_for("never-submitted") is None

"""Tests for the EL-1 Observation model: immutability, defaults, and the
mutable ProcessingContext companion.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.runtime.observations import (
    Observation,
    ObservationSource,
    Priority,
    ProcessingContext,
    ProcessingState,
)


class TestObservationConstruction:
    def test_summary_is_the_only_required_field(self) -> None:
        obs = Observation(summary="something happened")
        assert obs.summary == "something happened"

    def test_empty_summary_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="summary"):
            Observation(summary="")

    def test_whitespace_only_summary_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="summary"):
            Observation(summary="   ")

    def test_observation_id_is_generated_as_a_uuid4_when_omitted(self) -> None:
        obs = Observation(summary="x")
        # UUID4 string form: 36 chars, hyphens at the standard positions.
        assert len(obs.observation_id) == 36
        assert obs.observation_id.count("-") == 4

    def test_observation_id_generation_is_unique_per_instance(self) -> None:
        first = Observation(summary="x")
        second = Observation(summary="x")
        assert first.observation_id != second.observation_id

    def test_explicit_observation_id_is_preserved(self) -> None:
        obs = Observation(summary="x", observation_id="fixed-id")
        assert obs.observation_id == "fixed-id"

    def test_timestamp_defaults_to_a_real_time_value(self) -> None:
        import time

        before = time.time()
        obs = Observation(summary="x")
        after = time.time()
        assert before <= obs.timestamp <= after

    def test_defaults(self) -> None:
        obs = Observation(summary="x")
        assert obs.observation_type == "generic"
        assert obs.source is ObservationSource.INTERNAL
        assert obs.intrinsic_priority is Priority.NORMAL
        assert obs.supporting_signals == ()
        assert dict(obs.payload) == {}


class TestObservationImmutability:
    def test_observation_is_frozen(self) -> None:
        obs = Observation(summary="x")
        with pytest.raises(FrozenInstanceError):
            obs.summary = "changed"  # type: ignore[misc]

    def test_intrinsic_priority_cannot_be_mutated(self) -> None:
        obs = Observation(summary="x", intrinsic_priority=Priority.HIGH)
        with pytest.raises(FrozenInstanceError):
            obs.intrinsic_priority = Priority.LOW  # type: ignore[misc]
        assert obs.intrinsic_priority is Priority.HIGH

    def test_payload_mutation_by_caller_does_not_alter_the_observation(self) -> None:
        original_payload = {"key": "value"}
        obs = Observation(summary="x", payload=original_payload)

        original_payload["key"] = "mutated"
        original_payload["new_key"] = "new_value"

        assert dict(obs.payload) == {"key": "value"}

    def test_payload_is_read_only(self) -> None:
        obs = Observation(summary="x", payload={"key": "value"})
        with pytest.raises(TypeError):
            obs.payload["key"] = "changed"  # type: ignore[index]

    def test_supporting_signals_preserved_exactly(self) -> None:
        obs = Observation(summary="x", supporting_signals=("sig-1", "sig-2"))
        assert obs.supporting_signals == ("sig-1", "sig-2")

    def test_supporting_signals_coerced_to_tuple(self) -> None:
        obs = Observation(summary="x", supporting_signals=["sig-1"])  # type: ignore[arg-type]
        assert obs.supporting_signals == ("sig-1",)
        assert isinstance(obs.supporting_signals, tuple)


class TestObservationSerialization:
    def test_to_dict_renders_enums_as_canonical_values(self) -> None:
        obs = Observation(
            summary="ci finished",
            observation_type="ci_status",
            source=ObservationSource.CLI,
            intrinsic_priority=Priority.CRITICAL,
            supporting_signals=("commit", "push"),
            payload={"repo": "telemachus"},
        )
        data = obs.to_dict()

        assert data["summary"] == "ci finished"
        assert data["observation_type"] == "ci_status"
        assert data["source"] == "cli"
        assert data["intrinsic_priority"] == "CRITICAL"
        assert data["supporting_signals"] == ["commit", "push"]
        assert data["payload"] == {"repo": "telemachus"}
        assert data["observation_id"] == obs.observation_id
        assert data["timestamp"] == obs.timestamp

    def test_to_dict_payload_is_a_plain_dict(self) -> None:
        obs = Observation(summary="x", payload={"a": 1})
        data = obs.to_dict()
        assert type(data["payload"]) is dict


class TestProcessingContext:
    def test_is_mutable(self) -> None:
        ctx = ProcessingContext(observation_id="obs-1", effective_priority=1)
        ctx.state = ProcessingState.PROCESSING
        ctx.attempts = 1
        assert ctx.state is ProcessingState.PROCESSING
        assert ctx.attempts == 1

    def test_defaults(self) -> None:
        ctx = ProcessingContext(observation_id="obs-1", effective_priority=2)
        assert ctx.state is ProcessingState.QUEUED
        assert ctx.attempts == 0
        assert ctx.queued_at is None
        assert ctx.started_at is None
        assert ctx.ended_at is None
        assert ctx.error is None

    def test_effective_priority_starts_from_intrinsic_priority(self) -> None:
        obs = Observation(summary="x", intrinsic_priority=Priority.HIGH)
        ctx = ProcessingContext(
            observation_id=obs.observation_id,
            effective_priority=int(obs.intrinsic_priority),
        )
        assert ctx.effective_priority == int(Priority.HIGH)

    def test_state_transitions_are_freely_assignable(self) -> None:
        ctx = ProcessingContext(observation_id="obs-1", effective_priority=1)
        for state in (
            ProcessingState.QUEUED,
            ProcessingState.PROCESSING,
            ProcessingState.COMPLETED,
            ProcessingState.ARCHIVED,
        ):
            ctx.state = state
            assert ctx.state is state

    def test_error_recorded_on_failure_state(self) -> None:
        ctx = ProcessingContext(observation_id="obs-1", effective_priority=1)
        ctx.state = ProcessingState.FAILED
        ctx.error = "boom"
        assert ctx.state is ProcessingState.FAILED
        assert ctx.error == "boom"


class TestPriorityOrdering:
    def test_priority_values_are_ordered_low_to_critical(self) -> None:
        assert Priority.LOW < Priority.NORMAL < Priority.HIGH < Priority.CRITICAL

    def test_priority_is_int_compatible(self) -> None:
        assert int(Priority.CRITICAL) == 3
        assert int(Priority.LOW) == 0

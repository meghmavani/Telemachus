"""Tests for the Runtime lifecycle state model and transition table."""

from __future__ import annotations

import itertools

import pytest

from telemachus.runtime.states import (
    InvalidTransitionError,
    LifecycleState,
    allowed_transitions,
    validate_transition,
)

# The transition table as data, independent of the implementation, so the
# test asserts the *specification* rather than mirroring the source.
_LEGAL_EDGES: set[tuple[LifecycleState, LifecycleState]] = {
    (LifecycleState.BOOTING, LifecycleState.INSTALLING),
    (LifecycleState.BOOTING, LifecycleState.RECOVERY),
    (LifecycleState.BOOTING, LifecycleState.SHUTTING_DOWN),
    (LifecycleState.INSTALLING, LifecycleState.RECOVERY),
    (LifecycleState.RECOVERY, LifecycleState.RECONCILIATION),
    (LifecycleState.RECOVERY, LifecycleState.FAILED),
    (LifecycleState.RECOVERY, LifecycleState.SHUTTING_DOWN),
    (LifecycleState.RECONCILIATION, LifecycleState.RUNNING),
    (LifecycleState.RECONCILIATION, LifecycleState.SHUTTING_DOWN),
    (LifecycleState.RUNNING, LifecycleState.SHUTTING_DOWN),
    (LifecycleState.FAILED, LifecycleState.SHUTTING_DOWN),
    (LifecycleState.SHUTTING_DOWN, LifecycleState.STOPPED),
}


class TestLegalTransitions:
    """Every edge in the approved transition table must be accepted."""

    @pytest.mark.parametrize("edge", sorted(_LEGAL_EDGES, key=lambda e: (e[0].name, e[1].name)))
    def test_legal_edge_is_accepted(
        self, edge: tuple[LifecycleState, LifecycleState]
    ) -> None:
        from_state, to_state = edge
        validate_transition(from_state, to_state)  # must not raise

    def test_allowed_transitions_matches_table(self) -> None:
        for state in LifecycleState:
            expected = {to for (frm, to) in _LEGAL_EDGES if frm == state}
            assert allowed_transitions(state) == frozenset(expected)


class TestIllegalTransitions:
    """Every edge not in the table must be refused."""

    @pytest.mark.parametrize(
        "edge",
        sorted(
            (
                (a, b)
                for a, b in itertools.product(LifecycleState, LifecycleState)
                if (a, b) not in _LEGAL_EDGES
            ),
            key=lambda e: (e[0].name, e[1].name),
        ),
    )
    def test_illegal_edge_is_refused(
        self, edge: tuple[LifecycleState, LifecycleState]
    ) -> None:
        from_state, to_state = edge
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(from_state, to_state)
        assert exc_info.value.from_state == from_state
        assert exc_info.value.to_state == to_state

    def test_booting_to_running_is_refused(self) -> None:
        """The ADR-002 guarantee: Recovery cannot be skipped."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.BOOTING, LifecycleState.RUNNING)

    def test_recovery_to_running_is_refused(self) -> None:
        """Reconciliation cannot be skipped."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.RECOVERY, LifecycleState.RUNNING)

    def test_running_to_recovery_is_refused(self) -> None:
        """No in-process re-entry into Recovery."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.RUNNING, LifecycleState.RECOVERY)

    def test_shutting_down_to_running_is_refused(self) -> None:
        """Shutdown is not cancellable."""
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.SHUTTING_DOWN, LifecycleState.RUNNING)

    @pytest.mark.parametrize("target", list(LifecycleState))
    def test_stopped_is_terminal(self, target: LifecycleState) -> None:
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.STOPPED, target)

    def test_error_message_names_both_states(self) -> None:
        with pytest.raises(InvalidTransitionError, match="BOOTING -> RUNNING"):
            validate_transition(LifecycleState.BOOTING, LifecycleState.RUNNING)

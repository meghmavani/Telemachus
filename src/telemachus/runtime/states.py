"""Runtime lifecycle states and the transition table that governs them.

This module is the specification, not just a convenience. Every legal
lifecycle transition is enumerated in ``_VALID_TRANSITIONS`` below; anything
not listed is refused. In particular this is what makes ADR-002
("every startup is a recovery") a structural guarantee rather than a
convention: ``BOOTING -> RUNNING`` and ``RECOVERY -> RUNNING`` are simply
absent from the table, so skipping Recovery or Reconciliation cannot happen
by omission elsewhere in the code.
"""

from __future__ import annotations

from enum import Enum


class LifecycleState(Enum):
    """The operational states of the Telemachus Runtime process."""

    BOOTING = "booting"
    INSTALLING = "installing"
    RECOVERY = "recovery"
    RECONCILIATION = "reconciliation"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    FAILED = "failed"
    STOPPED = "stopped"


class RunningMode(Enum):
    """Substate of RUNNING. Does not participate in the transition table."""

    IDLE = "idle"
    ACTIVE = "active"


class PreviousTermination(Enum):
    """How the previous Runtime session ended, as read from persistence."""

    NONE = "none"  # No prior session record exists (first run).
    CLEAN = "clean"
    UNCLEAN = "unclean"


class InvalidTransitionError(RuntimeError):
    """Raised when a lifecycle transition is not permitted.

    Attributes:
        from_state: The state the Runtime was in.
        to_state: The state the transition attempted to reach.
    """

    def __init__(self, from_state: LifecycleState, to_state: LifecycleState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid lifecycle transition: {from_state.name} -> {to_state.name}"
        )


_VALID_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.BOOTING: frozenset(
        {
            LifecycleState.INSTALLING,
            LifecycleState.RECOVERY,
            LifecycleState.SHUTTING_DOWN,
        }
    ),
    LifecycleState.INSTALLING: frozenset(
        {
            LifecycleState.RECOVERY,
        }
    ),
    LifecycleState.RECOVERY: frozenset(
        {
            LifecycleState.RECONCILIATION,
            LifecycleState.FAILED,
            LifecycleState.SHUTTING_DOWN,
        }
    ),
    LifecycleState.RECONCILIATION: frozenset(
        {
            LifecycleState.RUNNING,
            LifecycleState.SHUTTING_DOWN,
        }
    ),
    LifecycleState.RUNNING: frozenset(
        {
            LifecycleState.SHUTTING_DOWN,
        }
    ),
    LifecycleState.FAILED: frozenset(
        {
            LifecycleState.SHUTTING_DOWN,
        }
    ),
    LifecycleState.SHUTTING_DOWN: frozenset(
        {
            LifecycleState.STOPPED,
        }
    ),
    LifecycleState.STOPPED: frozenset(),
}


def allowed_transitions(from_state: LifecycleState) -> frozenset[LifecycleState]:
    """Return the set of states reachable in one step from ``from_state``."""
    return _VALID_TRANSITIONS[from_state]


def validate_transition(from_state: LifecycleState, to_state: LifecycleState) -> None:
    """Raise InvalidTransitionError unless ``from_state -> to_state`` is legal.

    Args:
        from_state: The current lifecycle state.
        to_state: The proposed next state.

    Raises:
        InvalidTransitionError: If the transition is not in the table.
    """
    if to_state not in _VALID_TRANSITIONS[from_state]:
        raise InvalidTransitionError(from_state, to_state)

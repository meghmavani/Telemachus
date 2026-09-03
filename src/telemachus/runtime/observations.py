"""Runtime observation model — immutable facts entering the Event Loop.

An Observation is the Event Loop's unit of intake: a normalized,
immutable statement of something that happened, produced from whatever
raw signal triggered it. Interpretation, prioritization, scheduling, and
reasoning all remain separate from the fact itself (docs/event_loop.md,
"Architectural Principle"; docs/runtime_decisions.md ADR-003 "Universal
Observation Model", ADR-004 "Immutable Observations").

This module implements EL-1 only: the Observation and its mutable
processing companion, ``ProcessingContext``. Signal processing,
aggregation, and dynamic priority recalculation are explicitly deferred
to later milestones — see the Event Loop architectural reconnaissance.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any


class ObservationSource(Enum):
    """Where an Observation originated."""

    INTERNAL = "internal"
    CLI = "cli"


class Priority(IntEnum):
    """Intrinsic priority of an Observation.

    Set once at creation and never recomputed — "Intrinsic Priority
    never changes" (docs/event_loop.md, "Prioritization"). Effective
    priority, which may evolve, lives on ``ProcessingContext`` instead.
    Ordered so a higher value always means higher priority.
    """

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ProcessingState(Enum):
    """Where one Observation sits in its operational lifecycle.

    Mirrors docs/event_loop.md's "Operational Lifecycle": Queued ->
    Processing -> Completed/Failed -> Archived. This milestone does not
    implement archival; ``ARCHIVED`` exists so the state machine matches
    the specification even though nothing transitions into it yet.
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Observation:
    """An immutable fact entering the Event Loop.

    Reality is immutable; interpretation is adaptive (docs/event_loop.md,
    "Architectural Principle"). Everything that evolves while an
    Observation is processed — state, attempts, timestamps, errors —
    lives on the companion ``ProcessingContext`` instead, never here.

    Attributes:
        summary: The normalized fact, in plain text. The only field
            without a sensible default — an Observation that states
            nothing is not an Observation. Also what gets handed to the
            Core as its ``user_input`` equivalent, so it must be
            non-empty for the same reason ``CognitivePipeline.process()``
            requires non-empty input.
        observation_type: A short category label (e.g. "cli_message"),
            free-form in this milestone.
        source: Where the Observation originated.
        payload: Arbitrary structured detail supporting ``summary``.
            Defensively copied into a read-only mapping in
            ``__post_init__`` so mutating the caller's original dict (or
            handing this Observation to multiple consumers) can never
            alter what was recorded. This is a shallow guarantee, the
            same depth ``Tool.sacred_domains_affected`` and similar
            fields in this codebase settle for — nested mutable values
            inside ``payload`` are not independently frozen.
        intrinsic_priority: This Observation's fixed priority. Never
            mutated after construction.
        supporting_signals: Free-form identifiers for whatever raw
            signals produced this Observation, preserved exactly.
            Aggregation (merging multiple signals into one Observation)
            is future work; this field exists so the shape matches the
            specification even though nothing populates it yet.
        observation_id: Stable identifier. Generated as a UUID4 if not
            supplied.
        timestamp: Unix time of creation. Defaulted to ``time.time()``.
    """

    summary: str
    observation_type: str = "generic"
    source: ObservationSource = ObservationSource.INTERNAL
    payload: Mapping[str, Any] = field(default_factory=dict)
    intrinsic_priority: Priority = Priority.NORMAL
    supporting_signals: tuple[str, ...] = ()
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.summary or not self.summary.strip():
            raise ValueError("Observation summary must not be empty")
        # frozen=True forbids plain attribute assignment even from inside
        # __post_init__; object.__setattr__ is the documented escape
        # hatch dataclasses itself uses for this exact situation.
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "supporting_signals", tuple(self.supporting_signals))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the Core invoker / pipeline context.

        Mirrors the ``Tool.to_dict()`` convention elsewhere in this
        codebase: enum members render as their canonical value/name
        rather than the Python enum repr.
        """
        return {
            "observation_id": self.observation_id,
            "timestamp": self.timestamp,
            "source": self.source.value,
            "observation_type": self.observation_type,
            "summary": self.summary,
            "payload": dict(self.payload),
            "intrinsic_priority": self.intrinsic_priority.name,
            "supporting_signals": list(self.supporting_signals),
        }


@dataclass
class ProcessingContext:
    """Mutable Runtime-side processing state for one Observation.

    Unlike ``Observation``, this is expected to evolve throughout
    processing (docs/event_loop.md, "Processing Context"). This
    milestone gives it only what EL-1 actually needs — effective
    priority is seeded from the Observation's intrinsic priority and
    never recomputed here; dynamic recalculation is future work.

    Attributes:
        observation_id: The Observation this context tracks.
        effective_priority: Seeded from ``intrinsic_priority`` at
            submission time. Not recomputed in this milestone.
        state: Where this Observation sits in its operational lifecycle.
        attempts: How many times processing has been attempted.
        queued_at: When this Observation was accepted onto the queue.
        started_at: When the current/most recent attempt began.
        ended_at: When the current/most recent attempt concluded.
        error: The error message from the most recent failed attempt.
    """

    observation_id: str
    effective_priority: int
    state: ProcessingState = ProcessingState.QUEUED
    attempts: int = 0
    queued_at: float | None = None
    started_at: float | None = None
    ended_at: float | None = None
    error: str | None = None

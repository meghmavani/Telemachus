"""The Telemachus Runtime — orchestration layer around the Core.

This package owns process lifetime, lifecycle state, crash detection,
recovery, reconciliation, signal handling, release ordering, and (as of
this milestone) observation intake via the Event Loop. It does not
reason, plan, or hold memory-domain semantics — those remain the Core's
responsibility (docs/runtime.md, ADR-001).

This milestone (EL-1) implements the Event Loop's observation intake:
a bounded in-memory priority queue, ``EventLoop.tick()``, and their
integration with ``RuntimeLifecycle``'s RUNNING wait loop. The Event
Loop dispatches Observations to an opaque invoker supplied by the
composition root — it never constructs or imports whatever runs behind
that callable. Signal processing, aggregation, dependency/resource
scheduling, adaptive backpressure, semantic readiness, and plugins
remain future milestones and are not present here.
"""

from telemachus.runtime.event_loop import CoreInvoker, EventLoop
from telemachus.runtime.lifecycle import RuntimeLifecycle
from telemachus.runtime.observations import (
    Observation,
    ObservationSource,
    Priority,
    ProcessingContext,
    ProcessingState,
)
from telemachus.runtime.records import (
    InstallationRecord,
    LifecycleSnapshot,
    RecoveryBriefing,
    SessionRecord,
)
from telemachus.runtime.signals import SignalHandler
from telemachus.runtime.state_store import RuntimeStateStore
from telemachus.runtime.states import (
    InvalidTransitionError,
    LifecycleState,
    PreviousTermination,
    RunningMode,
)

__all__ = [
    "CoreInvoker",
    "EventLoop",
    "InstallationRecord",
    "InvalidTransitionError",
    "LifecycleSnapshot",
    "LifecycleState",
    "Observation",
    "ObservationSource",
    "PreviousTermination",
    "Priority",
    "ProcessingContext",
    "ProcessingState",
    "RecoveryBriefing",
    "RunningMode",
    "RuntimeLifecycle",
    "RuntimeStateStore",
    "SessionRecord",
    "SignalHandler",
]

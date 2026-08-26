"""The Telemachus Runtime — orchestration layer around the Core.

This package owns process lifetime, lifecycle state, crash detection,
recovery, reconciliation, signal handling, and release ordering. It does
not reason, plan, or hold memory-domain semantics — those remain the
Core's responsibility (docs/runtime.md, ADR-001).

This milestone implements Runtime Lifecycle and Session Continuity only.
The Event Loop, Observation system, scheduling, semantic readiness, and
plugins are future milestones and are not present here.
"""

from telemachus.runtime.lifecycle import RuntimeLifecycle
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
    "InstallationRecord",
    "InvalidTransitionError",
    "LifecycleSnapshot",
    "LifecycleState",
    "PreviousTermination",
    "RecoveryBriefing",
    "RunningMode",
    "RuntimeLifecycle",
    "RuntimeStateStore",
    "SessionRecord",
    "SignalHandler",
]

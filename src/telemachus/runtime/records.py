"""Frozen records crossing the Runtime persistence boundary.

These are the types ``RuntimeStateStore`` returns and ``RuntimeLifecycle``
passes to the CLI. Keeping them as dataclasses rather than raw tuples or
dicts gives the persistence boundary the same typed-and-frozen treatment
the rest of the codebase uses for Core data (see ``core/types.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from telemachus.runtime.states import LifecycleState, PreviousTermination


@dataclass(frozen=True)
class InstallationRecord:
    """The single, write-once record of when this installation began.

    Attributes:
        instance_id: A stable identifier for this installation, generated
            once and never reused.
        installed_at: Unix timestamp of first installation.
        schema_version: The runtime.db schema version active at install time.
    """

    instance_id: str
    installed_at: float
    schema_version: int


@dataclass(frozen=True)
class SessionRecord:
    """One row per Runtime process lifetime.

    Attributes:
        session_id: A stable identifier for this process's run.
        pid: The process ID that owned this session.
        started_at: Unix timestamp when the session was opened, in RECOVERY.
        ended_at: Unix timestamp when the session was closed during a
            graceful shutdown, or None if the session is still open or
            ended without reaching SHUTTING_DOWN.
        clean_shutdown: True only if the full shutdown sequence completed.
        last_state: The name of the last LifecycleState recorded for this
            session, used to report which phase an unclean session died in.
    """

    session_id: str
    pid: int
    started_at: float
    ended_at: float | None
    clean_shutdown: bool
    last_state: str


@dataclass(frozen=True)
class RecoveryBriefing:
    """A plain summary of what Recovery/Reconciliation found.

    Contains no interpretation or generated prose — assembling those is
    Core work and is out of scope for this milestone. The CLI is
    responsible for deciding whether and when to display it.

    Attributes:
        previous_termination: How the previous session ended.
        previous_session: The previous session's record, if one exists.
        offline_seconds: Seconds between the previous session's last known
            activity and this session's start, or None on a first run.
        is_new_installation: True if this run performed first
            installation (i.e. no InstallationRecord existed before it).
    """

    previous_termination: PreviousTermination
    previous_session: SessionRecord | None
    offline_seconds: float | None
    is_new_installation: bool


@dataclass(frozen=True)
class LifecycleSnapshot:
    """A read-only view of the Runtime's current state, for callers like the CLI.

    Attributes:
        state: The current lifecycle state.
        session_id: The active session's identifier.
        instance_id: This installation's identifier.
    """

    state: LifecycleState
    session_id: str
    instance_id: str

"""Runtime lifecycle orchestration.

``RuntimeLifecycle`` owns process lifetime, lifecycle transitions, Runtime
persistence, crash detection, recovery, reconciliation, signal handling,
and release ordering.

It does not own Core reasoning, memory-domain semantics, governance
reasoning, planning, or the internal five-phase bootstrap protocol — those
remain exactly where they are. The Core's ``BootstrapProtocol`` is invoked
here as one indivisible unit; this module never reorders, splits, or
duplicates its five phases (docs/lifecycle.md, docs/runtime_decisions.md
ADR-001, ADR-002).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Callable

from telemachus.bootstrap import BootstrapProtocol, BootstrapResult
from telemachus.config import TelemachusConfig
from telemachus.memory.store import MemoryStore
from telemachus.runtime.records import LifecycleSnapshot, RecoveryBriefing, SessionRecord
from telemachus.runtime.signals import SignalHandler
from telemachus.runtime.state_store import RuntimeStateStore
from telemachus.runtime.states import (
    InvalidTransitionError,
    LifecycleState,
    PreviousTermination,
    RunningMode,
    validate_transition,
)

logger = logging.getLogger("telemachus.runtime.lifecycle")

BootstrapFactory = Callable[[TelemachusConfig, MemoryStore, bool], BootstrapProtocol]

# Poll granularity for wait_for_shutdown_request(), matching the 1-second
# cadence of the `while True: time.sleep(1)` placeholder it replaces.
_SHUTDOWN_POLL_SECONDS = 1.0


def _default_bootstrap_factory(
    config: TelemachusConfig, memory_store: MemoryStore, first_awakening: bool
) -> BootstrapProtocol:
    return BootstrapProtocol(
        config=config, memory_store=memory_store, first_awakening=first_awakening
    )


class RuntimeLifecycle:
    """Coordinates the Telemachus Runtime's operational lifetime.

    Usage::

        lifecycle = RuntimeLifecycle(config, state_store, memory_store_factory)
        bootstrap_result = lifecycle.start()
        ...
        lifecycle.run_until_shutdown()  # blocks until a signal, then shuts down

    Attributes:
        state: The current LifecycleState.
        running_mode: RUNNING's substate. Fixed at IDLE in this milestone —
            nothing yet drives it to ACTIVE, since that requires the Event
            Loop (a future milestone). Present now so the substate exists
            in the model lifecycle.md describes.
    """

    def __init__(
        self,
        config: TelemachusConfig,
        state_store: RuntimeStateStore,
        memory_store_factory: Callable[[], MemoryStore],
        signal_handler: SignalHandler | None = None,
        bootstrap_factory: BootstrapFactory | None = None,
    ) -> None:
        """Initialize the Runtime lifecycle.

        Args:
            config: The system configuration.
            state_store: The (not-yet-connected) Runtime state store over
                runtime.db. ``start()`` connects it.
            memory_store_factory: Builds and connects the Core memory
                store. Supplied by the composition root (``wiring.py``)
                so this module never constructs MemoryStore itself —
                Runtime coordinates Core components, it does not
                duplicate their construction.
            signal_handler: Optional pre-built SignalHandler, primarily
                for tests. A real one is created if omitted.
            bootstrap_factory: Optional factory for BootstrapProtocol,
                primarily for tests that need to inject a failing or
                fake bootstrap without touching real codex files.
        """
        self._config = config
        self._state_store = state_store
        self._memory_store_factory = memory_store_factory
        self._signals = signal_handler or SignalHandler()
        self._bootstrap_factory = bootstrap_factory or _default_bootstrap_factory

        self._state = LifecycleState.BOOTING
        self.running_mode = RunningMode.IDLE

        self._session_id: str | None = None
        self._instance_id: str | None = None
        self._memory_store: MemoryStore | None = None
        self._bootstrap_protocol: BootstrapProtocol | None = None
        self._bootstrap_result: BootstrapResult | None = None
        self._recovery_briefing: RecoveryBriefing | None = None

    # ------------------------------------------------------------------
    # Read-only state
    # ------------------------------------------------------------------

    @property
    def state(self) -> LifecycleState:
        """The current lifecycle state."""
        return self._state

    @property
    def memory_store(self) -> MemoryStore | None:
        """The connected Core memory store, once start() has reached RECOVERY."""
        return self._memory_store

    @property
    def bootstrap_protocol(self) -> BootstrapProtocol | None:
        """The Core BootstrapProtocol instance used by start(), for display purposes.

        Exposed so callers such as the CLI can query
        ``get_first_awakening_questions()`` without the Runtime
        duplicating that data itself.
        """
        return self._bootstrap_protocol

    @property
    def bootstrap_result(self) -> BootstrapResult | None:
        """The Core bootstrap's result, once start() has run it."""
        return self._bootstrap_result

    @property
    def recovery_briefing(self) -> RecoveryBriefing | None:
        """The Recovery/Reconciliation briefing, once start() has assembled it."""
        return self._recovery_briefing

    def snapshot(self) -> LifecycleSnapshot:
        """Return a read-only view of the Runtime's current state.

        Returns:
            A LifecycleSnapshot.

        Raises:
            RuntimeError: If called before start() has opened a session.
        """
        if self._session_id is None or self._instance_id is None:
            raise RuntimeError("RuntimeLifecycle has not started. Call start() first.")
        return LifecycleSnapshot(
            state=self._state,
            session_id=self._session_id,
            instance_id=self._instance_id,
        )

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _transition(self, to_state: LifecycleState) -> None:
        """Move to ``to_state`` if legal, and persist it against the open session.

        Raises:
            InvalidTransitionError: If the transition is not in the table.
        """
        validate_transition(self._state, to_state)
        logger.info("Lifecycle transition: %s -> %s", self._state.name, to_state.name)
        self._state = to_state
        if self._session_id is not None:
            self._state_store.update_session_state(self._session_id, to_state.name)

    def _force_transition_for_shutdown(self, to_state: LifecycleState) -> None:
        """Transition during shutdown, tolerating an out-of-table predecessor.

        Every real startup path only ever reaches shutdown() from a state
        with a legal edge to SHUTTING_DOWN (RUNNING, FAILED, RECOVERY,
        RECONCILIATION, or BOOTING). The one state without a modeled exit
        to SHUTTING_DOWN is INSTALLING, whose only work is a single
        synchronous database write — reachable only if that write itself
        raises. Shutdown must still complete in that case, so this
        fallback logs the anomaly and forces the state directly rather
        than leaving the process unable to release its resources.
        """
        try:
            self._transition(to_state)
        except InvalidTransitionError:
            logger.warning(
                "Forcing lifecycle state %s -> %s outside the transition table "
                "during shutdown (unmodeled predecessor state)",
                self._state.name,
                to_state.name,
            )
            self._state = to_state

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def start(self) -> BootstrapResult:
        """Run the startup sequence through to RUNNING.

        Sequence: install signal handlers, open runtime.db, determine
        whether this is a new installation, classify how the previous
        session ended, open a new session, connect the Core memory store,
        run the Core's five-phase bootstrap protocol exactly once as an
        indivisible unit, reconcile, and reach RUNNING.

        Returns:
            The BootstrapResult from the Core's bootstrap protocol,
            carried through unchanged for the caller to inspect or
            display. The Runtime does not interpret its contents — only
            whether ``result.success`` is true.
        """
        self._signals.install()
        self._state_store.connect()
        self._state_store.initialize_schema()

        existing_installation = self._state_store.read_installation()
        is_new_installation = existing_installation is None

        if is_new_installation:
            self._transition(LifecycleState.INSTALLING)
            installation = self._state_store.create_installation_if_absent(
                str(uuid.uuid4())
            )
            self._transition(LifecycleState.RECOVERY)
        else:
            assert existing_installation is not None  # narrowed by is_new_installation
            installation = existing_installation
            self._transition(LifecycleState.RECOVERY)

        self._instance_id = installation.instance_id

        previous_session = self._state_store.get_most_recent_session()
        previous_termination = self._classify_termination(previous_session)
        if previous_session is not None and previous_session.ended_at is None:
            # The prior session never reached a clean close. Close the
            # stale row now, permanently as unclean — it is never
            # rewritten to look clean.
            self._state_store.close_session(previous_session.session_id, clean_shutdown=False)

        self._session_id = str(uuid.uuid4())
        self._state_store.open_session(
            self._session_id, pid=os.getpid(), initial_state=self._state.name
        )

        self._memory_store = self._memory_store_factory()

        # Runtime supplies the fact (is this installation's first run);
        # the Core's config still grants or withholds permission. Neither
        # rewrites what first awakening means — that remains entirely the
        # Core bootstrap's five-phase protocol.
        first_awakening = is_new_installation and self._config.bootstrap.first_awakening
        bootstrap = self._bootstrap_factory(self._config, self._memory_store, first_awakening)
        self._bootstrap_protocol = bootstrap
        result = bootstrap.bootstrap()
        self._bootstrap_result = result

        if not result.success:
            self._transition(LifecycleState.FAILED)
            self._recovery_briefing = self._build_briefing(
                previous_termination, previous_session, is_new_installation
            )
            return result

        self._transition(LifecycleState.RECONCILIATION)
        # Reconciliation is intentionally thin: without the Event Loop
        # there are no Processing Contexts and no in-flight observations
        # to reconcile. This phase exists as a real seam in the lifecycle
        # and currently does only what it can do honestly — report what
        # changed while the Runtime was offline.
        self._recovery_briefing = self._build_briefing(
            previous_termination, previous_session, is_new_installation
        )

        self._transition(LifecycleState.RUNNING)
        return result

    def _classify_termination(
        self, previous: SessionRecord | None
    ) -> PreviousTermination:
        """Classify how the previous session ended, from its record alone.

        No heartbeats, no timers: a session that never reached a clean
        close simply has ``ended_at IS NULL`` or ``clean_shutdown = 0``.
        """
        if previous is None:
            return PreviousTermination.NONE
        if previous.ended_at is not None and previous.clean_shutdown:
            return PreviousTermination.CLEAN
        return PreviousTermination.UNCLEAN

    def _build_briefing(
        self,
        termination: PreviousTermination,
        previous_session: SessionRecord | None,
        is_new_installation: bool,
    ) -> RecoveryBriefing:
        """Assemble a plain, uninterpreted summary of what Recovery found."""
        offline_seconds: float | None = None
        if previous_session is not None:
            reference = (
                previous_session.ended_at
                if previous_session.ended_at is not None
                else previous_session.started_at
            )
            offline_seconds = max(0.0, time.time() - reference)
        return RecoveryBriefing(
            previous_termination=termination,
            previous_session=previous_session,
            offline_seconds=offline_seconds,
            is_new_installation=is_new_installation,
        )

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def wait_for_shutdown_request(self) -> None:
        """Block in RUNNING until a shutdown is requested.

        Replaces the placeholder ``while True: time.sleep(1)`` with an
        interruptible wait on the signal handler's Event. Polls the Event
        on a short interval rather than blocking on it indefinitely —
        Windows does not reliably interrupt an arbitrary blocking C call
        the instant a console signal arrives, so a bounded wait is used
        to guarantee the request is noticed promptly on every supported
        platform, at the same granularity the placeholder it replaces
        already had.

        Does not itself perform shutdown — this lets a caller (such as
        the CLI) react between the request arriving and shutdown running,
        e.g. to print a message. Call ``shutdown()`` afterward, or use
        ``run_until_shutdown()`` to do both.

        Raises:
            RuntimeError: If called while not in RUNNING.
        """
        if self._state != LifecycleState.RUNNING:
            raise RuntimeError(
                f"wait_for_shutdown_request() requires RUNNING, "
                f"current state is {self._state.name}"
            )
        while not self._signals.shutdown_requested.wait(timeout=_SHUTDOWN_POLL_SECONDS):
            pass

    def run_until_shutdown(self) -> None:
        """Block in RUNNING until a shutdown is requested, then shut down.

        Convenience form of ``wait_for_shutdown_request()`` followed by
        ``shutdown()``, for callers with no need to react in between.

        Raises:
            RuntimeError: If called while not in RUNNING.
        """
        self.wait_for_shutdown_request()
        self.shutdown()

    def request_shutdown(self) -> None:
        """Request shutdown without an OS signal (e.g. from the CLI)."""
        self._signals.request_shutdown()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Run the graceful shutdown sequence.

        Idempotent: a second call once STOPPED is a no-op. Each resource
        release is independently guarded so a failure in one step never
        prevents the others from running — a subsystem that fails to
        release still lets the rest of the process shut down cleanly.

        Order: transition to SHUTTING_DOWN and persist it; close the Core
        memory store; record clean_shutdown as whether that close actually
        succeeded; close the Runtime state store; restore signal handlers
        and flush logging; transition to STOPPED.
        """
        if self._state == LifecycleState.STOPPED:
            return

        if self._state != LifecycleState.SHUTTING_DOWN:
            self._force_transition_for_shutdown(LifecycleState.SHUTTING_DOWN)

        store_closed_cleanly = True
        if self._memory_store is not None:
            try:
                self._memory_store.disconnect()
            except Exception:
                logger.exception("Failed to disconnect memory store during shutdown")
                store_closed_cleanly = False

        if self._session_id is not None:
            try:
                self._state_store.close_session(
                    self._session_id, clean_shutdown=store_closed_cleanly
                )
            except Exception:
                logger.exception("Failed to close runtime session record")

        # The final transition still needs to persist through the state
        # store, so it happens before that connection closes.
        self._force_transition_for_shutdown(LifecycleState.STOPPED)

        try:
            self._state_store.disconnect()
        except Exception:
            logger.exception("Failed to close runtime state store")

        self._signals.restore()
        logging.shutdown()

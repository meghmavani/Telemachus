"""Composition root — builds wired subsystems from configuration.

Both the ``start`` and ``chat`` entry points need the same objects
assembled the same way: a connected memory store, and a pipeline that
writes into it. Before this module existed each call site constructed
them independently, drifted from the real constructor signatures, and
raised ``TypeError`` at startup without any test noticing.

Construction lives here so that there is exactly one place where the
wiring can be wrong, and one place to test.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from telemachus.config import TelemachusConfig
from telemachus.core.constitution import Constitution
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline
from telemachus.runtime.event_loop import EventLoop
from telemachus.runtime.lifecycle import RuntimeLifecycle
from telemachus.runtime.observations import Observation, ObservationSource, Priority
from telemachus.runtime.records import RecoveryBriefing, SessionRecord
from telemachus.runtime.state_store import RuntimeStateStore
from telemachus.runtime.states import PreviousTermination
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry

logger = logging.getLogger("telemachus.wiring")


def build_memory_store(config: TelemachusConfig) -> MemoryStore:
    """Open and initialize the memory store described by ``config``.

    The returned store is connected and has its schema applied, so callers
    can use it immediately.

    Args:
        config: The system configuration.

    Returns:
        A connected MemoryStore.
    """
    db_path = config.paths.data_dir / config.database.path
    store = MemoryStore(db_path)
    store.connect()
    store.initialize_schema()
    logger.debug("Memory store ready at %s", db_path)
    return store


def build_tool_registry() -> ToolRegistry:
    """Build the tool registry with every built-in tool registered.

    This is the only place production code constructs a ToolRegistry.
    Currently registers ``EchoTool`` — the minimal tool proving the
    Stage 6 execution boundary. Real tools land here as they are built;
    nothing about Stage 6 needs to change to add one.

    Returns:
        A ToolRegistry with all built-in tools active.
    """
    registry = ToolRegistry()
    registry.register(EchoTool())
    return registry


def build_pipeline(
    config: TelemachusConfig,
    memory_store: MemoryStore | None = None,
    tool_registry: ToolRegistry | None = None,
    *,
    constitution: Constitution,
) -> CognitivePipeline:
    """Build a cognitive pipeline backed by the configured memory store.

    ``constitution`` is required and keyword-only, with no default and
    no fallback to ``create_default_constitution()`` here: the
    composition root is the one place production code assembles the
    pipeline, so this is what makes an accidentally-Python-default
    Constitution unreachable in production. Callers must supply the
    Codex-derived Constitution from Bootstrap
    (``BootstrapResult.constitution`` / ``RuntimeLifecycle.bootstrap_result``).

    Args:
        config: The system configuration.
        memory_store: An already-connected store. Built from config if None.
        tool_registry: The registry backing Stage 6 execution. Built with
            the built-in tools if None.
        constitution: The authoritative Constitution for the Stage 6
            constitutional gate. Required.

    Returns:
        A CognitivePipeline ready to process input.
    """
    store = memory_store if memory_store is not None else build_memory_store(config)
    registry = tool_registry if tool_registry is not None else build_tool_registry()
    return CognitivePipeline(memory_store=store, tool_registry=registry, constitution=constitution)


def build_observation_invoker(
    pipeline: CognitivePipeline, session_id: str
) -> Callable[[Observation], None]:
    """Build the opaque callable the Event Loop dispatches Observations through.

    Built here rather than in ``runtime/`` because the Event Loop must
    never import ``CognitivePipeline`` — this is the one seam through
    which an Observation reaches Core reasoning
    (tests/test_runtime_boundaries.py enforces the import direction).

    Deliberately places no ``ActionRequest`` in the pipeline context:
    EL-1 observations always reach Stage 6 as
    ``ExecutionOutcome.NO_ACTION``. Candidate-action generation from an
    Observation is future, separately-reviewed work.

    Args:
        pipeline: The Core pipeline built from Bootstrap's Constitution.
        session_id: A stable session id used for every invocation, so
            Observations processed across one Runtime lifetime are
            attributed to one continuous session rather than each
            appearing as an unrelated one-off interaction.

    Returns:
        A callable matching ``telemachus.runtime.event_loop.CoreInvoker``.
    """

    def invoke(observation: Observation) -> None:
        pipeline.process(
            observation.summary,
            context={"observation": observation.to_dict()},
            session_id=session_id,
        )

    return invoke


def build_event_loop(pipeline: CognitivePipeline, session_id: str) -> EventLoop:
    """Build the Runtime's Event Loop, wired to invoke ``pipeline``.

    Args:
        pipeline: The Core pipeline the Event Loop's opaque invoker wraps.
        session_id: Passed through to ``build_observation_invoker``.

    Returns:
        An EventLoop ready for ``RuntimeLifecycle.attach_event_loop()``.
    """
    return EventLoop(build_observation_invoker(pipeline, session_id))


def _session_record_payload(session: SessionRecord | None) -> dict[str, Any] | None:
    """Flatten a SessionRecord into a plain dict, or None if there isn't one.

    ``SessionRecord`` has no serialization method of its own (it is an
    internal Runtime persistence type, not a Core-facing one), so this
    is the smallest faithful translation — every field, unrenamed.
    """
    if session is None:
        return None
    return {
        "session_id": session.session_id,
        "pid": session.pid,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "clean_shutdown": session.clean_shutdown,
        "last_state": session.last_state,
    }


def build_recovery_observation(briefing: RecoveryBriefing) -> Observation:
    """Translate the Runtime's RecoveryBriefing into one Observation.

    ``RecoveryBriefing`` already exists, is already durable-state-backed,
    and today is discarded by every caller except a console print
    (``main.py:_display_recovery_briefing``). This is the first
    production Observation with real content behind it — RS-1's whole
    purpose (see the RS-1 reconnaissance report).

    The summary mirrors the same facts ``_display_recovery_briefing``
    already prints, restated as one plain, factual, non-empty statement
    — never assistant-voiced or interpretive prose.
    ``RecoveryBriefing``'s own docstring is explicit that assembling
    interpretation is Core work and out of scope here; this function
    only restates the record so the Core can decide what it means
    (docs/lifecycle.md, "User Briefings").

    Every outcome — NONE, CLEAN, or UNCLEAN — is submitted at
    ``Priority.NORMAL``. Termination state is preserved in the payload
    rather than encoded as urgency: the Runtime does not get to decide
    that a crash matters more than a clean run — the Core does, once it
    receives the fact.

    Args:
        briefing: The RecoveryBriefing ``RuntimeLifecycle.start()`` produced.

    Returns:
        One Observation, ``ObservationSource.INTERNAL``,
        ``Priority.NORMAL``, ``observation_type="recovery_briefing"``.
    """
    if briefing.is_new_installation:
        summary = "New Runtime installation; no previous session to recover."
    elif briefing.previous_termination == PreviousTermination.UNCLEAN:
        last_state = (
            briefing.previous_session.last_state
            if briefing.previous_session is not None
            else "unknown"
        )
        summary = (
            f"Previous session did not shut down cleanly; "
            f"last recorded state: {last_state}."
        )
    elif briefing.previous_termination == PreviousTermination.CLEAN:
        summary = "Previous session ended cleanly."
    else:
        # PreviousTermination.NONE without is_new_installation: no
        # InstallationRecord existed yet, but a prior session row was
        # also absent — not a path start() actually produces today, but
        # handled explicitly rather than falling through silently.
        summary = "No previous session record was found."

    if not briefing.is_new_installation and briefing.offline_seconds is not None:
        summary += f" Offline for approximately {briefing.offline_seconds:.0f}s."

    payload: dict[str, Any] = {
        "previous_termination": briefing.previous_termination.value,
        "previous_session": _session_record_payload(briefing.previous_session),
        "offline_seconds": briefing.offline_seconds,
        "is_new_installation": briefing.is_new_installation,
    }

    return Observation(
        summary=summary,
        observation_type="recovery_briefing",
        source=ObservationSource.INTERNAL,
        payload=payload,
        intrinsic_priority=Priority.NORMAL,
    )


def build_runtime(config: TelemachusConfig) -> RuntimeLifecycle:
    """Build a Runtime lifecycle ready to start.

    This is the composition root's only construction path for the
    Runtime: the state store it will connect to runtime.db, and the
    factory it will call to obtain the connected Core memory store, are
    both assembled here rather than inside ``RuntimeLifecycle`` itself —
    consistent with ``build_memory_store`` and ``build_pipeline`` above,
    and with the Runtime's role of coordinating Core components rather
    than constructing them independently.

    Args:
        config: The system configuration.

    Returns:
        A RuntimeLifecycle ready for ``start()``. Neither runtime.db nor
        telemachus.db is touched until then.
    """
    state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
    return RuntimeLifecycle(
        config=config,
        state_store=state_store,
        memory_store_factory=lambda: build_memory_store(config),
    )

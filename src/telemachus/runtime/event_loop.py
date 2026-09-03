"""The Runtime Event Loop — main-thread, tick-driven observation intake.

This is Milestone EL-1: a bounded in-memory priority queue and one
``tick()`` that dispatches at most one Observation per call to an opaque
invoker. Signal processing, aggregation, dependency/resource scheduling,
adaptive backpressure, and semantic readiness are explicitly deferred to
later milestones (docs/event_loop.md).

Ownership boundary (docs/runtime.md, "Authority Model"):

    The Event Loop decides *whether and when to ask*.
    It never decides the answer.

This module owns observation intake, queue ordering, and dispatch
bookkeeping only. It does not evaluate whether a candidate action is
permitted, ethical, or authorized — it does not even know those
questions exist. The ``invoker`` supplied at construction is the entire
surface through which an Observation reaches reasoning; this module
holds no reference to, and makes no assumption about, what runs behind
that callable. In EL-1 nothing downstream of it ever requests a tool
execution, so this loop cannot cause one.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import time
from collections.abc import Callable

from telemachus.runtime.observations import Observation, ProcessingContext, ProcessingState

logger = logging.getLogger("telemachus.runtime.event_loop")

# Bounded queue capacity for this milestone. Deliberately not
# configurable yet — see the Event Loop reconnaissance report's "Open
# Architectural Decisions".
DEFAULT_MAX_QUEUE_SIZE = 1000

# The Event Loop's entire reach into reasoning: hand one Observation to
# whatever the composition root wired behind this callable. This module
# never inspects, imports, or assumes anything about what runs inside it.
CoreInvoker = Callable[[Observation], None]


class EventLoop:
    """Owns observation intake: a bounded priority queue and one tick.

    Attributes:
        dropped_count: Observations rejected because the queue was full
            at submission time.
        processed_count: Observations a ``tick()`` call has dispatched
            to the invoker, incremented on both success and failure.
            This counts *attempted* work, mirroring how
            ``Tool.execution_count`` in ``tools/base.py`` increments on
            every call regardless of outcome, with failure tracked
            separately (there, ``failure_count``; here, each
            Observation's own ``ProcessingContext.state`` /
            ``.error`` — there is no separate failure counter on the
            loop itself in this milestone).
    """

    def __init__(
        self,
        invoker: CoreInvoker,
        *,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
    ) -> None:
        """Initialize the Event Loop.

        Args:
            invoker: Opaque callable a submitted Observation is handed
                to during ``tick()``. Exceptions it raises are caught
                and recorded on that Observation's ``ProcessingContext``
                — they never escape ``tick()``.
            max_queue_size: Bounded queue capacity. Submissions beyond
                this are rejected (newest-first) rather than displacing
                queued work.
        """
        self._invoker = invoker
        self._max_queue_size = max_queue_size
        # Min-heap of (-effective_priority, sequence, Observation).
        # Negating priority makes the highest priority pop first; the
        # strictly increasing sequence number breaks ties in FIFO order
        # and guarantees two entries are never equal at that point, so
        # heapq never needs to compare Observation instances directly.
        self._queue: list[tuple[int, int, Observation]] = []
        self._contexts: dict[str, ProcessingContext] = {}
        self._sequence = itertools.count()
        self.dropped_count = 0
        self.processed_count = 0

    @property
    def pending_count(self) -> int:
        """Observations currently queued, awaiting a tick."""
        return len(self._queue)

    def context_for(self, observation_id: str) -> ProcessingContext | None:
        """Return the ProcessingContext for a submitted Observation.

        Returns:
            The ProcessingContext, or None if no Observation with that
            id was ever submitted to this Event Loop.
        """
        return self._contexts.get(observation_id)

    def submit(self, observation: Observation) -> bool:
        """Enqueue an Observation for a future ``tick()``.

        Returns:
            True if accepted onto the queue. False if the queue was
            already at ``max_queue_size`` — the newest Observation
            (this one) is rejected, ``dropped_count`` is incremented,
            and a WARNING is logged. Nothing is ever silently discarded.
        """
        if len(self._queue) >= self._max_queue_size:
            self.dropped_count += 1
            logger.warning(
                "Event Loop queue full (%d); dropping observation %s (%s)",
                self._max_queue_size,
                observation.observation_id,
                observation.observation_type,
            )
            return False

        context = ProcessingContext(
            observation_id=observation.observation_id,
            effective_priority=int(observation.intrinsic_priority),
            state=ProcessingState.QUEUED,
            queued_at=time.time(),
        )
        self._contexts[observation.observation_id] = context

        heapq.heappush(
            self._queue,
            (-context.effective_priority, next(self._sequence), observation),
        )
        return True

    def tick(self) -> int:
        """Process at most one queued Observation.

        A queue poll, not a reasoning timer: an empty queue invokes the
        opaque invoker zero times (docs/runtime_decisions.md ADR-005 —
        reasoning must never be triggered solely because time elapsed).

        A failing invoker is caught here and never allowed to escape —
        one bad Observation must not stop the Event Loop from processing
        the rest of the queue on the next tick.

        Returns:
            1 if an Observation was dispatched this call, 0 if the
            queue was empty.
        """
        if not self._queue:
            return 0

        _, _, observation = heapq.heappop(self._queue)
        context = self._contexts[observation.observation_id]

        context.state = ProcessingState.PROCESSING
        context.attempts += 1
        context.started_at = time.time()

        try:
            self._invoker(observation)
        except Exception as exc:  # never let a single Observation kill the loop
            context.state = ProcessingState.FAILED
            context.error = str(exc)
            logger.exception(
                "Event Loop observation %s failed during dispatch",
                observation.observation_id,
            )
        else:
            context.state = ProcessingState.COMPLETED

        context.ended_at = time.time()
        self.processed_count += 1
        return 1

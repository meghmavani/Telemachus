"""Runtime signal handling — minimal, restorable, platform-aware.

Signal handlers must do the least possible work: record which signal
arrived, set an Event so the Runtime's blocked wait can observe the
request, and return immediately. All real shutdown work — closing stores,
persisting session state, logging — happens later on the main thread once
the Runtime's wait loop notices the Event. This is what keeps a second
Ctrl+C from deadlocking against a handler still doing I/O.

Available signals differ by platform. ``SIGHUP`` does not exist on
Windows; ``SIGBREAK`` exists only on Windows. Handlers are installed only
for signals this platform actually provides, discovered with ``getattr``
rather than assumed.
"""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType
from typing import Any

logger = logging.getLogger("telemachus.runtime.signals")

# Signals that request graceful shutdown, on whichever platforms define them.
_SHUTDOWN_SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP")


class SignalHandler:
    """Installs minimal signal handlers that request graceful shutdown.

    Usage:
        handler = SignalHandler()
        handler.install()
        try:
            handler.shutdown_requested.wait()
        finally:
            handler.restore()

    Attributes:
        shutdown_requested: Set the moment any handled signal is received.
        received_signal: The signal number that triggered the request, or
            None if shutdown was requested programmatically instead.
    """

    def __init__(self) -> None:
        self.shutdown_requested = threading.Event()
        self.received_signal: int | None = None
        self._installed_signals: list[int] = []
        self._previous_handlers: dict[int, Any] = {}

    def available_signals(self) -> list[int]:
        """The shutdown-related signal numbers this platform actually defines.

        Returns:
            Signal numbers for whichever of SIGINT/SIGTERM/SIGBREAK/SIGHUP
            exist on the running platform. Never assumes Unix semantics.
        """
        found = []
        for name in _SHUTDOWN_SIGNAL_NAMES:
            sig = getattr(signal, name, None)
            if sig is not None:
                found.append(sig)
        return found

    def install(self) -> None:
        """Register handlers for every shutdown signal this platform has.

        Must be called from the main thread — ``signal.signal`` requires
        it and raises ``ValueError`` otherwise. Previous handlers are
        captured so ``install()`` is fully reversible via ``restore()``.
        """
        for sig in self.available_signals():
            self._previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._handle)
            self._installed_signals.append(sig)
        logger.debug(
            "Signal handlers installed: %s",
            [signal.Signals(s).name for s in self._installed_signals],
        )

    def _handle(self, signum: int, frame: FrameType | None) -> None:
        """The actual OS-invoked handler.

        Deliberately minimal: no database I/O, no logging, no
        orchestration. Records the signal and unblocks the waiter.
        """
        self.received_signal = signum
        self.shutdown_requested.set()

    def restore(self) -> None:
        """Restore whatever handlers were active before ``install()``.

        Safe to call even if ``install()`` was never called or was
        already restored — leaves no global state behind, which is what
        keeps this safe to use inside tests.
        """
        for sig, previous in self._previous_handlers.items():
            signal.signal(sig, previous)
        self._previous_handlers.clear()
        self._installed_signals.clear()
        logger.debug("Signal handlers restored")

    def request_shutdown(self) -> None:
        """Request shutdown without an OS signal (e.g. a programmatic stop)."""
        self.shutdown_requested.set()

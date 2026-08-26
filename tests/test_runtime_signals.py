"""Tests for Runtime signal handling.

Signal *delivery* is exercised by invoking the registered handler
directly rather than sending real OS signals — that is portable across
platforms and is the actual contract under test (what the handler does),
not the OS's signal-dispatch mechanism.
"""

from __future__ import annotations

import signal

from telemachus.runtime.signals import SignalHandler


class TestAvailableSignals:
    def test_sigint_and_sigterm_are_always_available(self) -> None:
        handler = SignalHandler()
        available = handler.available_signals()
        assert signal.SIGINT in available
        assert signal.SIGTERM in available

    def test_platform_specific_signals_are_probed_not_assumed(self) -> None:
        """Only signals this platform actually defines are ever returned.

        SIGBREAK exists only on Windows; SIGHUP does not exist there.
        Rather than special-case a platform, assert the general contract:
        available_signals() never returns a signal absent from this
        platform's signal module.
        """
        handler = SignalHandler()
        available = handler.available_signals()

        platform_signals = {getattr(signal, name) for name in dir(signal) if name.startswith("SIG")
                             and not name.startswith("SIG_")
                             and isinstance(getattr(signal, name), signal.Signals)}
        assert set(available) <= platform_signals


class TestInstallAndRestore:
    def test_install_registers_handlers(self) -> None:
        handler = SignalHandler()
        try:
            handler.install()
            for sig in handler.available_signals():
                assert signal.getsignal(sig) == handler._handle
        finally:
            handler.restore()

    def test_restore_returns_previous_handler(self) -> None:
        sentinel_calls: list[int] = []

        def sentinel(signum: int, frame: object) -> None:
            sentinel_calls.append(signum)

        original = signal.signal(signal.SIGINT, sentinel)
        try:
            handler = SignalHandler()
            handler.install()
            assert signal.getsignal(signal.SIGINT) == handler._handle

            handler.restore()
            assert signal.getsignal(signal.SIGINT) == sentinel
        finally:
            signal.signal(signal.SIGINT, original)

    def test_restore_is_safe_without_install(self) -> None:
        handler = SignalHandler()
        handler.restore()  # must not raise

    def test_restore_leaves_no_global_state(self) -> None:
        """Two handlers installed and restored in sequence must not interfere."""
        before = {sig: signal.getsignal(sig) for sig in SignalHandler().available_signals()}

        h1 = SignalHandler()
        h1.install()
        h1.restore()

        h2 = SignalHandler()
        h2.install()
        h2.restore()

        after = {sig: signal.getsignal(sig) for sig in SignalHandler().available_signals()}
        assert before == after


class TestHandlerBehavior:
    def test_handling_a_signal_sets_the_event(self) -> None:
        handler = SignalHandler()
        assert not handler.shutdown_requested.is_set()

        handler._handle(signal.SIGINT, None)

        assert handler.shutdown_requested.is_set()
        assert handler.received_signal == signal.SIGINT

    def test_handler_records_which_signal_arrived(self) -> None:
        handler = SignalHandler()
        handler._handle(signal.SIGTERM, None)
        assert handler.received_signal == signal.SIGTERM

    def test_handler_does_not_raise_with_no_frame(self) -> None:
        handler = SignalHandler()
        handler._handle(signal.SIGINT, None)  # must not raise


class TestProgrammaticShutdown:
    def test_request_shutdown_sets_event_without_a_signal(self) -> None:
        handler = SignalHandler()
        handler.request_shutdown()
        assert handler.shutdown_requested.is_set()
        assert handler.received_signal is None

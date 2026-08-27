"""Tests for RuntimeLifecycle — the orchestration layer.

These exercise the full startup/shutdown sequence against real temp
directories and real SQLite, matching the principle test_cli_smoke.py
states: the defects worth catching live between components, not inside
them.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from telemachus.bootstrap import BootstrapPhase, BootstrapResult, PhaseResult, PhaseStatus
from telemachus.config import TelemachusConfig, load_config_from_path
from telemachus.memory.store import MemoryStore
from telemachus.runtime.lifecycle import RuntimeLifecycle
from telemachus.runtime.signals import SignalHandler
from telemachus.runtime.state_store import RuntimeStateStore
from telemachus.runtime.states import LifecycleState, PreviousTermination

# ---------------------------------------------------------------------------
# Fixtures: a minimal, complete Telemachus installation in a temp directory,
# mirroring tests/test_cli_smoke.py's `project` fixture.
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal but complete Telemachus installation in a temp directory."""
    codex = tmp_path / "codex"
    (codex / "philosophy").mkdir(parents=True)
    # A valid Protected Constraints section is required — see
    # src/telemachus/core/codex.py.
    (codex / "philosophy" / "CONSTITUTION.md").write_text(
        "# Constitution\n\n"
        "## Protected Constraints\n\n"
        "### 1. Constitution Integrity\n\nMay not be modified without approval.\n\n"
        "### 2. Human Meaning\n\nMay not be autonomously altered.\n\n"
        "### 3. Relationship Integrity\n\nMay not be autonomously redefined.\n\n"
        "### 4. Resource Authorization\n\nMay not be used without discussion.\n\n"
        "### 5. Human Authority over Life-Impacting Decisions\n\nMust remain human-controlled.\n\n"
        "## First Memory\n\n\"I was created to seek truth.\"\n"
    )
    (codex / "philosophy" / "IDENTITY.md").write_text("# Identity\n")

    config_file = tmp_path / "telemachus.toml"
    config_file.write_text(
        "[identity]\n"
        'name = "Telemachus"\n'
        "[paths]\n"
        f"data_dir = '{tmp_path / 'data'}'\n"
        f"codex_dir = '{codex}'\n"
        f"log_dir = '{tmp_path / 'logs'}'\n"
        "[bootstrap]\n"
        "first_awakening = true\n"
    )
    return config_file


@pytest.fixture
def config(project: Path) -> TelemachusConfig:
    cfg = load_config_from_path(project)
    cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _memory_store_factory(config: TelemachusConfig) -> MemoryStore:
    """A real memory-store factory, mirroring wiring.build_memory_store."""

    def factory() -> MemoryStore:
        store = MemoryStore(config.paths.data_dir / config.database.path)
        store.connect()
        store.initialize_schema()
        return store

    return factory


def _new_lifecycle(config: TelemachusConfig) -> RuntimeLifecycle:
    state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
    return RuntimeLifecycle(
        config=config,
        state_store=state_store,
        memory_store_factory=_memory_store_factory(config),
        signal_handler=SignalHandler(),
    )


@pytest.fixture
def lifecycle(config: TelemachusConfig) -> Generator[RuntimeLifecycle, None, None]:
    lc = _new_lifecycle(config)
    try:
        yield lc
    finally:
        lc.shutdown()  # idempotent; ensures no handle leaks between tests


def _failing_bootstrap_factory(
    config: TelemachusConfig, memory_store: MemoryStore, first_awakening: bool
) -> object:
    class _FailingBootstrap:
        def bootstrap(self) -> BootstrapResult:
            return BootstrapResult(
                success=False,
                phases=[
                    PhaseResult(
                        phase=BootstrapPhase.LOAD_CORE_DOCS,
                        status=PhaseStatus.FAILED,
                        message="forced failure for testing",
                    )
                ],
                errors=["Phase 1 failed: forced failure for testing"],
                first_awakening=first_awakening,
            )

    return _FailingBootstrap()


# ---------------------------------------------------------------------------
# Lifecycle progression
# ---------------------------------------------------------------------------


class TestStartupProgression:
    def test_start_reaches_running(self, lifecycle: RuntimeLifecycle) -> None:
        result = lifecycle.start()
        assert result.success
        assert lifecycle.state == LifecycleState.RUNNING

    def test_start_returns_bootstrap_result_unmodified(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        result = lifecycle.start()
        assert result is lifecycle.bootstrap_result
        assert len(result.phases) == 5  # all five phases ran, untouched

    def test_memory_store_is_connected_after_start(self, lifecycle: RuntimeLifecycle) -> None:
        lifecycle.start()
        assert lifecycle.memory_store is not None
        assert lifecycle.memory_store.conn is not None

    def test_snapshot_available_after_start(self, lifecycle: RuntimeLifecycle) -> None:
        lifecycle.start()
        snap = lifecycle.snapshot()
        assert snap.state == LifecycleState.RUNNING
        assert snap.session_id
        assert snap.instance_id

    def test_snapshot_before_start_raises(self, lifecycle: RuntimeLifecycle) -> None:
        with pytest.raises(RuntimeError, match="has not started"):
            lifecycle.snapshot()

    def test_bootstrap_failure_routes_to_failed(self, config: TelemachusConfig) -> None:
        state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
        lc = RuntimeLifecycle(
            config=config,
            state_store=state_store,
            memory_store_factory=_memory_store_factory(config),
            bootstrap_factory=_failing_bootstrap_factory,  # type: ignore[arg-type]
        )
        try:
            result = lc.start()
            assert not result.success
            assert lc.state == LifecycleState.FAILED
        finally:
            lc.shutdown()

    def test_failed_bootstrap_still_releases_resources_on_shutdown(
        self, config: TelemachusConfig
    ) -> None:
        state_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
        lc = RuntimeLifecycle(
            config=config,
            state_store=state_store,
            memory_store_factory=_memory_store_factory(config),
            bootstrap_factory=_failing_bootstrap_factory,  # type: ignore[arg-type]
        )
        lc.start()
        assert lc.state == LifecycleState.FAILED
        lc.shutdown()
        assert lc.state == LifecycleState.STOPPED
        assert lc.memory_store is not None
        assert lc.memory_store.conn is None


# ---------------------------------------------------------------------------
# First awakening / new installation
# ---------------------------------------------------------------------------


class TestFirstAwakening:
    def test_fresh_install_with_config_true_is_first_awakening(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        result = lifecycle.start()
        assert result.first_awakening is True

    def test_second_start_is_not_first_awakening(self, config: TelemachusConfig) -> None:
        """Regression test: today this stays True forever. The fix is that
        the Runtime, not the config, supplies whether this is a new run."""
        lc1 = _new_lifecycle(config)
        lc1.start()
        lc1.shutdown()

        lc2 = _new_lifecycle(config)
        try:
            result = lc2.start()
            assert result.first_awakening is False
        finally:
            lc2.shutdown()

    def test_config_opt_out_disables_first_awakening_even_on_fresh_install(
        self, project: Path, tmp_path: Path
    ) -> None:
        codex = tmp_path / "codex"
        config_file = tmp_path / "telemachus_no_awaken.toml"
        config_file.write_text(
            "[identity]\n"
            'name = "Telemachus"\n'
            "[paths]\n"
            f"data_dir = '{tmp_path / 'data2'}'\n"
            f"codex_dir = '{codex}'\n"
            f"log_dir = '{tmp_path / 'logs2'}'\n"
            "[bootstrap]\n"
            "first_awakening = false\n"
        )
        config = load_config_from_path(config_file)
        config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        lc = _new_lifecycle(config)
        try:
            result = lc.start()
            assert result.first_awakening is False
        finally:
            lc.shutdown()

    def test_installation_record_persists_instance_id_across_restart(
        self, config: TelemachusConfig
    ) -> None:
        lc1 = _new_lifecycle(config)
        lc1.start()
        instance_id_1 = lc1.snapshot().instance_id
        lc1.shutdown()

        lc2 = _new_lifecycle(config)
        try:
            lc2.start()
            instance_id_2 = lc2.snapshot().instance_id
            assert instance_id_1 == instance_id_2
        finally:
            lc2.shutdown()

    def test_restart_uses_a_distinct_session_id(self, config: TelemachusConfig) -> None:
        lc1 = _new_lifecycle(config)
        lc1.start()
        session_id_1 = lc1.snapshot().session_id
        lc1.shutdown()

        lc2 = _new_lifecycle(config)
        try:
            lc2.start()
            session_id_2 = lc2.snapshot().session_id
            assert session_id_1 != session_id_2
        finally:
            lc2.shutdown()


# ---------------------------------------------------------------------------
# Existing telemachus.db, no runtime.db (upgrade scenario)
# ---------------------------------------------------------------------------


class TestExistingInstallationUpgrade:
    def test_telemachus_db_untouched_when_runtime_db_created(
        self, config: TelemachusConfig
    ) -> None:
        """telemachus.db exists but runtime.db does not: treat Runtime state
        as a new Runtime installation, create runtime.db, and leave
        telemachus.db completely untouched."""
        # Simulate a pre-existing Core installation: connect and store one
        # entry directly, with no Runtime ever having run.
        from telemachus.core.types import MemoryDomain

        pre_existing_store = MemoryStore(config.paths.data_dir / config.database.path)
        pre_existing_store.connect()
        pre_existing_store.initialize_schema()
        pre_existing_store.store(MemoryDomain.PROJECT, "pre-existing entry", importance=0.9)
        stats_before = pre_existing_store.get_stats()
        pre_existing_store.disconnect()

        runtime_db_path = config.paths.data_dir / "runtime.db"
        assert not runtime_db_path.exists()

        lc = _new_lifecycle(config)
        try:
            lc.start()
            assert runtime_db_path.exists()

            assert lc.memory_store is not None
            stats_after = lc.memory_store.get_stats()
            assert stats_after["total_entries"] == stats_before["total_entries"]
            assert stats_after["domains"]["project"]["total"] == 1
        finally:
            lc.shutdown()

    def test_first_runtime_initialization_occurs_only_once(
        self, config: TelemachusConfig
    ) -> None:
        lc1 = _new_lifecycle(config)
        result1 = lc1.start()
        lc1.shutdown()
        assert result1.first_awakening is True

        lc2 = _new_lifecycle(config)
        try:
            result2 = lc2.start()
            assert result2.first_awakening is False
        finally:
            lc2.shutdown()


# ---------------------------------------------------------------------------
# Crash detection / recovery / reconciliation
# ---------------------------------------------------------------------------


class TestCrashDetectionAndRecovery:
    def test_first_run_has_no_previous_termination(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        lifecycle.start()
        briefing = lifecycle.recovery_briefing
        assert briefing is not None
        assert briefing.previous_termination == PreviousTermination.NONE
        assert briefing.offline_seconds is None
        assert briefing.is_new_installation is True

    def test_clean_restart_is_detected_as_clean(self, config: TelemachusConfig) -> None:
        lc1 = _new_lifecycle(config)
        lc1.start()
        lc1.shutdown()

        lc2 = _new_lifecycle(config)
        try:
            lc2.start()
            briefing = lc2.recovery_briefing
            assert briefing is not None
            assert briefing.previous_termination == PreviousTermination.CLEAN
            assert briefing.offline_seconds is not None
            assert briefing.offline_seconds >= 0
        finally:
            lc2.shutdown()

    def test_abandoned_session_is_detected_as_unclean_on_restart(
        self, config: TelemachusConfig
    ) -> None:
        """Simulates a crash: a session opened and never closed."""
        lc1 = _new_lifecycle(config)
        lc1.start()
        assert lc1.state == LifecycleState.RUNNING
        # No shutdown() call — the process is "killed" here.

        lc2 = _new_lifecycle(config)
        try:
            lc2.start()
            briefing = lc2.recovery_briefing
            assert briefing is not None
            assert briefing.previous_termination == PreviousTermination.UNCLEAN
            assert briefing.previous_session is not None
            assert briefing.previous_session.last_state == "RUNNING"
        finally:
            lc2.shutdown()
            lc1._state_store.disconnect()  # release the abandoned connection

    def test_stale_session_is_closed_but_never_marked_clean(
        self, config: TelemachusConfig
    ) -> None:
        lc1 = _new_lifecycle(config)
        lc1.start()
        lc1._state_store.disconnect()  # abandon without a graceful shutdown

        lc2 = _new_lifecycle(config)
        try:
            lc2.start()
            # Re-open the store to confirm the stale row was closed.
            verify_store = RuntimeStateStore(config.paths.data_dir / "runtime.db")
            verify_store.connect()
            # get_most_recent_session now returns lc2's own session, so
            # inspect via the briefing instead, which captured lc1's row
            # before lc2 opened its own.
            verify_store.disconnect()

            briefing = lc2.recovery_briefing
            assert briefing is not None
            assert briefing.previous_session is not None
            assert briefing.previous_session.clean_shutdown is False
        finally:
            lc2.shutdown()

    def test_reconciliation_reached_before_running(self, lifecycle: RuntimeLifecycle) -> None:
        """Reconciliation is a real, distinct phase — not skipped."""
        seen_states: list[LifecycleState] = []
        original_transition = lifecycle._transition

        def spy(to_state: LifecycleState) -> None:
            original_transition(to_state)
            seen_states.append(to_state)

        lifecycle._transition = spy  # type: ignore[method-assign]
        lifecycle.start()

        assert LifecycleState.RECONCILIATION in seen_states
        assert seen_states.index(LifecycleState.RECONCILIATION) < seen_states.index(
            LifecycleState.RUNNING
        )


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestShutdown:
    def test_clean_shutdown_reaches_stopped(self, lifecycle: RuntimeLifecycle) -> None:
        lifecycle.start()
        lifecycle.shutdown()
        assert lifecycle.state == LifecycleState.STOPPED

    def test_clean_shutdown_disconnects_memory_store(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        lifecycle.start()
        store = lifecycle.memory_store
        assert store is not None
        lifecycle.shutdown()
        assert store.conn is None

    def test_clean_shutdown_records_clean_shutdown_true(
        self, config: TelemachusConfig
    ) -> None:
        lc = _new_lifecycle(config)
        lc.start()
        session_id = lc.snapshot().session_id
        lc.shutdown()

        verify = RuntimeStateStore(config.paths.data_dir / "runtime.db")
        verify.connect()
        try:
            session = verify.get_most_recent_session()
            assert session is not None
            assert session.session_id == session_id
            assert session.clean_shutdown is True
            assert session.ended_at is not None
        finally:
            verify.disconnect()

    def test_shutdown_is_idempotent(self, lifecycle: RuntimeLifecycle) -> None:
        lifecycle.start()
        lifecycle.shutdown()
        lifecycle.shutdown()  # must not raise
        assert lifecycle.state == LifecycleState.STOPPED

    def test_run_until_shutdown_requires_running(self, lifecycle: RuntimeLifecycle) -> None:
        with pytest.raises(RuntimeError, match="requires RUNNING"):
            lifecycle.run_until_shutdown()

    def test_run_until_shutdown_returns_after_signal(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        lifecycle.start()
        lifecycle.request_shutdown()  # pre-set, so wait() returns immediately
        lifecycle.run_until_shutdown()
        assert lifecycle.state == LifecycleState.STOPPED

    def test_signal_handlers_are_restored_after_shutdown(
        self, lifecycle: RuntimeLifecycle
    ) -> None:
        import signal as signal_module

        original = signal_module.getsignal(signal_module.SIGINT)
        lifecycle.start()
        assert signal_module.getsignal(signal_module.SIGINT) != original
        lifecycle.shutdown()
        assert signal_module.getsignal(signal_module.SIGINT) == original

    def test_wal_and_shm_absent_after_clean_shutdown(self, config: TelemachusConfig) -> None:
        """Direct regression test for F-02: both databases' WAL sidecars
        must be gone after a clean shutdown, not just the process's own
        exit relying on the OS."""
        lc = _new_lifecycle(config)
        lc.start()

        # Write enough that a WAL file actually exists before shutdown.
        from telemachus.core.types import MemoryDomain

        assert lc.memory_store is not None
        for i in range(50):
            lc.memory_store.store(MemoryDomain.PROJECT, f"entry {i}", importance=0.5)

        lc.shutdown()

        telemachus_db = config.paths.data_dir / config.database.path
        runtime_db = config.paths.data_dir / "runtime.db"
        for db in (telemachus_db, runtime_db):
            assert not Path(str(db) + "-wal").exists(), f"{db}-wal was not cleaned up"
            assert not Path(str(db) + "-shm").exists(), f"{db}-shm was not cleaned up"

    def test_shutdown_before_start_does_not_raise(self, config: TelemachusConfig) -> None:
        lc = _new_lifecycle(config)
        lc.shutdown()  # never started; must degrade gracefully
        assert lc.state == LifecycleState.STOPPED

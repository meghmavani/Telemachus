"""End-to-end smoke tests for the CLI entry points.

These tests exist because ``telemachus start`` and ``telemachus chat`` both
raised ``TypeError`` on their first line of real work while the unit suite
reported 1013 passing tests at 89% coverage. Every one of those failures was
a signature mismatch between a caller and a callee — the kind of defect that
unit tests with hand-built objects cannot see, because each side was tested
against its own assumptions rather than against the other.

They deliberately exercise the real wiring: real config, real SQLite file,
real pipeline. Nothing here is mocked except the interactive prompt.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from typer.testing import CliRunner

import telemachus.main as main_module
from telemachus.config import load_config_from_path
from telemachus.main import app
from telemachus.runtime.states import LifecycleState
from telemachus.wiring import build_memory_store, build_pipeline, build_runtime

runner = CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal but complete Telemachus installation in a temp directory."""
    codex = tmp_path / "codex"
    (codex / "philosophy").mkdir(parents=True)
    (codex / "philosophy" / "CONSTITUTION.md").write_text("# Constitution\n")
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
        "first_awakening = false\n"
    )
    monkeypatch.chdir(tmp_path)
    return config_file


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def test_version_runs():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_config_check_accepts_a_valid_config(project):
    result = runner.invoke(app, ["config-check", "--config", str(project)])
    assert result.exit_code == 0, result.output


def test_config_check_rejects_a_missing_config(tmp_path):
    result = runner.invoke(app, ["config-check", "--config", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Wiring — the composition root each entry point depends on
# ---------------------------------------------------------------------------


def test_build_memory_store_is_usable_immediately(project):
    """A store returned by the wiring must be connected and migrated."""
    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    store = build_memory_store(config)
    try:
        stats = store.get_stats()
        assert stats["total_entries"] == 0
        assert set(stats["domains"]) == {
            "revan",
            "project",
            "world",
            "emotion",
            "reflection",
            "tool",
        }
    finally:
        store.disconnect()


def test_bootstrap_runs_against_a_real_memory_store(project):
    """The exact call main.start() makes — this raised TypeError before."""
    from telemachus.bootstrap import BootstrapProtocol

    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    store = build_memory_store(config)
    try:
        result = BootstrapProtocol(config=config, memory_store=store).bootstrap()
        assert result.success, result.errors
        assert result.memory_available
    finally:
        store.disconnect()


def test_pipeline_processes_input_and_persists_it(project):
    """The exact call cli_chat makes — this raised TypeError before."""
    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    store = build_memory_store(config)
    try:
        pipeline = build_pipeline(config, memory_store=store)
        result = pipeline.process("summarise my open projects", session_id="test")
        assert result.response
        assert store.get_stats()["total_entries"] > 0
    finally:
        store.disconnect()


def test_store_search_finds_stored_content(project):
    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    store = build_memory_store(config)
    try:
        from telemachus.core.types import MemoryDomain

        store.store(MemoryDomain.PROJECT, "ship the runtime skeleton", importance=0.9)
        store.store(MemoryDomain.WORLD, "unrelated fact", importance=0.1)

        hits = store.search("runtime")
        assert len(hits) == 1
        assert hits[0]["domain"] == "project"

        assert store.search("runtime", domain=MemoryDomain.WORLD) == []
        assert len(store.search("", limit=1)) == 1
    finally:
        store.disconnect()


# ---------------------------------------------------------------------------
# Runtime — build_runtime() through the same composition root
# ---------------------------------------------------------------------------


def test_build_runtime_is_usable_immediately(project):
    """The Runtime the composition root builds must actually start and stop."""
    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    runtime = build_runtime(config)
    assert runtime.state == LifecycleState.BOOTING

    result = runtime.start()
    try:
        assert result.success
        assert runtime.state == LifecycleState.RUNNING
        assert runtime.memory_store is not None
        assert runtime.memory_store.conn is not None
    finally:
        runtime.shutdown()

    assert runtime.state == LifecycleState.STOPPED
    assert runtime.memory_store.conn is None


def test_runtime_start_shutdown_leaves_no_wal_sidecars(project):
    """Integration-level regression test for F-02, through the real composition
    root and a real temp project — not just the unit-level runtime tests."""
    config = load_config_from_path(project)
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    runtime = build_runtime(config)
    runtime.start()
    runtime.shutdown()

    telemachus_db = config.paths.data_dir / config.database.path
    runtime_db = config.paths.data_dir / "runtime.db"
    for db in (telemachus_db, runtime_db):
        assert not Path(str(db) + "-wal").exists()
        assert not Path(str(db) + "-shm").exists()


def test_main_start_has_no_placeholder_sleep_loop():
    """Regression guard: `telemachus start` must delegate to the Runtime's
    interruptible wait, not the old `while True: time.sleep(1)` loop."""
    source = Path(inspect.getfile(main_module)).read_text(encoding="utf-8")
    assert "while True" not in source
    assert "time.sleep(1)" not in source

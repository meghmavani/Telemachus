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

import pytest
from typer.testing import CliRunner

from telemachus.config import load_config_from_path
from telemachus.main import app
from telemachus.wiring import build_memory_store, build_pipeline

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

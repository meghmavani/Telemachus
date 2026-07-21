"""Shared pytest fixtures for Telemachus tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from telemachus.config import TelemachusConfig, load_config_from_path


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def _as_posix(p: Path) -> str:
    """Convert a Windows path to POSIX-style with forward slashes for TOML compatibility."""
    return p.as_posix()


@pytest.fixture
def test_config_path(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a minimal valid TOML config file in a temp directory.

    Uses forward-slash paths to avoid TOML escape sequence issues on Windows.
    """
    config_file = temp_dir / "test_config.toml"
    data_dir = _as_posix(temp_dir / "data")
    codex_dir = _as_posix(temp_dir / "codex")
    log_dir = _as_posix(temp_dir / "logs")
    config_file.write_text(
        "[paths]\n"
        f'data_dir = "{data_dir}"\n'
        f'codex_dir = "{codex_dir}"\n'
        f'log_dir = "{log_dir}"\n'
    )
    yield config_file


@pytest.fixture
def test_config(test_config_path: Path) -> TelemachusConfig:
    """Load a TelemachusConfig from the test config file."""
    return load_config_from_path(test_config_path)

"""Tests for configuration loading and validation."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from telemachus.config import (
    ConfigError,
    TelemachusConfig,
    load_config_from_path,
)


def _as_posix(p: Path) -> str:
    """Convert a Windows path to POSIX-style for TOML compatibility."""
    return p.as_posix()


def _write_config(path: Path, sections: str) -> None:
    """Write a TOML config file with required paths section prepended."""
    parent = path.parent
    content = (
        "[paths]\n"
        f'data_dir = "{_as_posix(parent / "data")}"\n'
        f'codex_dir = "{_as_posix(parent / "codex")}"\n'
        f'log_dir = "{_as_posix(parent / "logs")}"\n'
    )
    if sections:
        content += "\n" + sections
    path.write_text(content)


class TestLoadConfig:
    """Tests for load_config_from_path."""

    def test_loads_valid_config(self, test_config: TelemachusConfig) -> None:
        """A valid TOML config should load without errors."""
        assert test_config.identity.name == "Telemachus"
        assert test_config.identity.creator == "Revan"
        assert test_config.logging.level == "INFO"

    def test_default_values_present(self, test_config: TelemachusConfig) -> None:
        """Sections not in the config file should use defaults."""
        assert test_config.governance.default_autonomy_level == 1
        assert test_config.governance.approval_risk_threshold == 3
        assert test_config.communication.default_mode == "collaborative"
        assert test_config.communication.emotional_awareness is True

    def test_paths_are_resolved(self, test_config: TelemachusConfig) -> None:
        """Paths should be resolved to absolute paths."""
        assert test_config.paths.data_dir.is_absolute()
        assert test_config.paths.codex_dir.is_absolute()
        assert test_config.paths.log_dir.is_absolute()

    def test_file_not_found_raises(self) -> None:
        """Loading a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config_from_path(Path("/nonexistent/path/config.toml"))

    def test_invalid_toml_raises(self, temp_dir: Path) -> None:
        """Invalid TOML should raise ConfigError."""
        bad_file = temp_dir / "bad.toml"
        bad_file.write_text("this is not valid toml {{{")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config_from_path(bad_file)

    def test_invalid_autonomy_level_raises(self, temp_dir: Path) -> None:
        """Invalid autonomy level should raise ConfigError."""
        config_file = temp_dir / "bad_autonomy.toml"
        _write_config(
            config_file,
            "[governance]\ndefault_autonomy_level = 99\n",
        )
        with pytest.raises(ConfigError, match="default_autonomy_level"):
            load_config_from_path(config_file)

    def test_invalid_communication_mode_raises(self, temp_dir: Path) -> None:
        """Invalid communication mode should raise ConfigError."""
        config_file = temp_dir / "bad_mode.toml"
        _write_config(
            config_file,
            '[communication]\ndefault_mode = "shouting"\n',
        )
        with pytest.raises(ConfigError, match="default_mode"):
            load_config_from_path(config_file)

    def test_invalid_bootstrap_phase_raises(self, temp_dir: Path) -> None:
        """Unknown bootstrap phase should raise ConfigError."""
        config_file = temp_dir / "bad_bootstrap.toml"
        _write_config(
            config_file,
            '[bootstrap]\nphases = ["load_core_docs", "make_coffee"]\n',
        )
        with pytest.raises(ConfigError, match="Unknown bootstrap phase"):
            load_config_from_path(config_file)

    def test_config_is_frozen(self, test_config: TelemachusConfig) -> None:
        """TelemachusConfig should be immutable (frozen dataclass)."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            test_config.identity.name = "Changed"  # type: ignore[misc]


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_default_config_has_all_sections(self, test_config: TelemachusConfig) -> None:
        """Default config should have all required sections."""
        assert test_config.identity is not None
        assert test_config.paths is not None
        assert test_config.database is not None
        assert test_config.logging is not None
        assert test_config.bootstrap is not None
        assert test_config.pipeline is not None
        assert test_config.governance is not None
        assert test_config.communication is not None
        assert test_config.memory is not None

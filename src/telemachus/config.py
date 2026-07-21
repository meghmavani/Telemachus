"""Configuration loading and validation for Telemachus.

Reads configuration from a TOML file, validates required fields,
and provides a frozen configuration object for the entire application.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATHS: list[str] = [
    "telemachus.toml",
    "~/.config/telemachus/telemachus.toml",
    "/etc/telemachus/telemachus.toml",
]


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""


@dataclass(frozen=True)
class IdentityConfig:
    """Identity-related configuration."""

    name: str = "Telemachus"
    creator: str = "Revan"
    version: str = "0.1.0"


@dataclass(frozen=True)
class PathsConfig:
    """Filesystem path configuration."""

    data_dir: Path = Path("./data")
    codex_dir: Path = Path("./codex")
    log_dir: Path = Path("./logs")


@dataclass(frozen=True)
class DatabaseConfig:
    """Database configuration."""

    path: str = "telemachus.db"


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    max_bytes: int = 10_485_760
    backup_count: int = 5


@dataclass(frozen=True)
class BootstrapConfig:
    """Bootstrap protocol configuration."""

    phases: list[str] = field(
        default_factory=lambda: [
            "load_core_docs",
            "evaluate_state",
            "load_memory",
            "reconnect",
            "resume",
        ]
    )
    first_awakening: bool = True


@dataclass(frozen=True)
class PipelineConfig:
    """Cognitive pipeline configuration."""

    timeout: int = 300
    reflect_on_action: bool = True
    learn_on_action: bool = True


@dataclass(frozen=True)
class GovernanceConfig:
    """Governance subsystem configuration."""

    default_autonomy_level: int = 1
    approval_risk_threshold: int = 3


@dataclass(frozen=True)
class CommunicationConfig:
    """Communication subsystem configuration."""

    default_mode: str = "collaborative"
    emotional_awareness: bool = True


@dataclass(frozen=True)
class MemoryConfig:
    """Memory subsystem configuration."""

    max_entries_per_domain: int = 100_000
    auto_index: bool = True


@dataclass(frozen=True)
class TelemachusConfig:
    """Root configuration for the Telemachus system."""

    identity: IdentityConfig = field(default_factory=IdentityConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bootstrap: BootstrapConfig = field(default_factory=BootstrapConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


def _find_section(
    data: dict[str, object], key: str, default: dict[str, object]
) -> dict[str, object]:
    """Extract a table section from parsed TOML, returning default if missing."""
    section = data.get(key)
    if section is None:
        return default
    if not isinstance(section, dict):
        raise ConfigError(
            f"Configuration section '[{key}]' must be a table, got {type(section).__name__}"
        )
    return section


def _resolve_paths(config: TelemachusConfig) -> TelemachusConfig:
    """Resolve relative paths to absolute paths."""
    data_dir = config.paths.data_dir.resolve()
    return TelemachusConfig(
        identity=config.identity,
        paths=PathsConfig(
            data_dir=data_dir,
            codex_dir=config.paths.codex_dir.resolve(),
            log_dir=config.paths.log_dir.resolve(),
        ),
        database=config.database,
        logging=config.logging,
        bootstrap=config.bootstrap,
        pipeline=config.pipeline,
        governance=config.governance,
        communication=config.communication,
        memory=config.memory,
    )


def _validate_config(config: TelemachusConfig) -> None:
    """Validate configuration values and raise ConfigError on invalid values."""
    if config.governance.default_autonomy_level not in range(5):
        raise ConfigError(
            f"default_autonomy_level must be 0-4, got {config.governance.default_autonomy_level}"
        )
    if config.governance.approval_risk_threshold not in range(5):
        raise ConfigError(
            f"approval_risk_threshold must be 0-4, got {config.governance.approval_risk_threshold}"
        )
    valid_modes = {"direct", "explained", "collaborative"}
    if config.communication.default_mode not in valid_modes:
        raise ConfigError(
            f"default_mode must be one of {valid_modes}, got '{config.communication.default_mode}'"
        )
    valid_phases = {
        "load_core_docs",
        "evaluate_state",
        "load_memory",
        "reconnect",
        "resume",
    }
    for phase in config.bootstrap.phases:
        if phase not in valid_phases:
            raise ConfigError(f"Unknown bootstrap phase '{phase}'. Valid phases: {valid_phases}")


def load_config_from_path(config_path: str | Path | None = None) -> TelemachusConfig:
    """Load and validate Telemachus configuration from a TOML file.

    Args:
        config_path: Path to the configuration file. If None, searches
                     default locations (./telemachus.toml, ~/.config/..., /etc/...).

    Returns:
        A validated, frozen TelemachusConfig instance.

    Raises:
        ConfigError: If the configuration file contains invalid values.
        FileNotFoundError: If no configuration file is found.
    """
    if config_path is None:
        for candidate in DEFAULT_CONFIG_PATHS:
            expanded = Path(candidate).expanduser()
            if expanded.exists():
                config_path = expanded
                break
        else:
            raise FileNotFoundError(
                f"No configuration file found. Searched: {DEFAULT_CONFIG_PATHS}"
            )

    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in configuration file '{path}': {exc}") from exc

    identity_raw = _find_section(data, "identity", {})
    paths_raw = _find_section(data, "paths", {})
    database_raw = _find_section(data, "database", {})
    logging_raw = _find_section(data, "logging", {})
    bootstrap_raw = _find_section(data, "bootstrap", {})
    pipeline_raw = _find_section(data, "pipeline", {})
    governance_raw = _find_section(data, "governance", {})
    communication_raw = _find_section(data, "communication", {})
    memory_raw = _find_section(data, "memory", {})

    config = TelemachusConfig(
        identity=IdentityConfig(
            name=str(identity_raw.get("name", "Telemachus")),
            creator=str(identity_raw.get("creator", "Revan")),
            version=str(identity_raw.get("version", "0.1.0")),
        ),
        paths=PathsConfig(
            data_dir=Path(str(paths_raw.get("data_dir", "./data"))),
            codex_dir=Path(str(paths_raw.get("codex_dir", "./codex"))),
            log_dir=Path(str(paths_raw.get("log_dir", "./logs"))),
        ),
        database=DatabaseConfig(
            path=str(database_raw.get("path", "telemachus.db")),
        ),
        logging=LoggingConfig(
            level=str(logging_raw.get("level", "INFO")),
            format=str(logging_raw.get("format", "json")),
            max_bytes=int(logging_raw.get("max_bytes", 10_485_760)),
            backup_count=int(logging_raw.get("backup_count", 5)),
        ),
        bootstrap=BootstrapConfig(
            phases=list(
                bootstrap_raw.get(
                    "phases",
                    ["load_core_docs", "evaluate_state", "load_memory", "reconnect", "resume"],
                )
            ),
            first_awakening=bool(bootstrap_raw.get("first_awakening", True)),
        ),
        pipeline=PipelineConfig(
            timeout=int(pipeline_raw.get("timeout", 300)),
            reflect_on_action=bool(pipeline_raw.get("reflect_on_action", True)),
            learn_on_action=bool(pipeline_raw.get("learn_on_action", True)),
        ),
        governance=GovernanceConfig(
            default_autonomy_level=int(governance_raw.get("default_autonomy_level", 1)),
            approval_risk_threshold=int(governance_raw.get("approval_risk_threshold", 3)),
        ),
        communication=CommunicationConfig(
            default_mode=str(communication_raw.get("default_mode", "collaborative")),
            emotional_awareness=bool(communication_raw.get("emotional_awareness", True)),
        ),
        memory=MemoryConfig(
            max_entries_per_domain=int(memory_raw.get("max_entries_per_domain", 100_000)),
            auto_index=bool(memory_raw.get("auto_index", True)),
        ),
    )

    config = _resolve_paths(config)
    _validate_config(config)

    return config


def load_config() -> TelemachusConfig:
    """Load configuration from default locations.

    Convenience wrapper that searches default paths and exits on failure.

    Returns:
        A validated TelemachusConfig instance.

    Raises:
        SystemExit: If no config file is found or config is invalid.
    """
    try:
        return load_config_from_path()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except ConfigError as exc:
        print(f"ERROR: Invalid configuration: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

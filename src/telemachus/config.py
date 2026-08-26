"""Configuration loading and validation for Telemachus.

Reads configuration from a TOML file, validates required fields,
and provides a frozen configuration object for the entire application.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field, replace
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
class LLMCandidate:
    """One model endpoint that can serve a role.

    Attributes:
        name: Stable identifier used in logs and cooldown state.
        provider: Transport to use — "openai" (any OpenAI-compatible
            endpoint) or "ollama".
        base_url: Endpoint root, without the path.
        model: Model identifier as the provider names it.
        api_key_env: Environment variable holding the key, if one is needed.
            The key itself is never read from the config file.
        max_tokens: Default token budget for this candidate.
        temperature: Default sampling temperature for this candidate.
        extra_body: Provider-specific request fields merged into the payload.
    """

    name: str
    provider: str
    base_url: str
    model: str
    api_key_env: str = ""
    max_tokens: int = 512
    temperature: float = 0.2
    extra_body: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMConfig:
    """Model access settings.

    Attributes:
        enabled: Master switch. When False Telemachus runs deterministically.
        timeout_sec: Per-request socket timeout.
        candidates: Role name to ordered candidate list. Roles express
            escalation — cheap models triage, expensive models decide.
    """

    enabled: bool = False
    timeout_sec: float = 45.0
    candidates: dict[str, list[LLMCandidate]] = field(default_factory=dict)


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
    llm: LLMConfig = field(default_factory=LLMConfig)

    def with_log_level(self, level: str) -> TelemachusConfig:
        """Return a new config with the logging level overridden.

        Uses dataclasses.replace to create a new frozen instance with only
        the logging section modified. All other sections are preserved.

        Args:
            level: The new log level (e.g. "DEBUG", "INFO", "WARNING").

        Returns:
            A new TelemachusConfig with the specified log level.
        """
        return replace(
            self,
            logging=replace(self.logging, level=level),
        )


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


def _as_str(section: dict[str, object], key: str, default: str, *, table: str) -> str:
    """Read a string setting, reporting the offending key if it is the wrong type."""
    value = section.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(
            f"[{table}] {key} must be a string, got {type(value).__name__}: {value!r}"
        )
    return value


def _as_int(section: dict[str, object], key: str, default: int, *, table: str) -> int:
    """Read an integer setting.

    Booleans are rejected explicitly: ``bool`` is a subclass of ``int`` in
    Python, so ``max_bytes = true`` would otherwise silently become 1.
    """
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"[{table}] {key} must be an integer, got {type(value).__name__}: {value!r}"
        )
    return value


def _as_float(section: dict[str, object], key: str, default: float, *, table: str) -> float:
    """Read a float setting. Integers are accepted and widened."""
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(
            f"[{table}] {key} must be a number, got {type(value).__name__}: {value!r}"
        )
    return float(value)


def _as_bool(section: dict[str, object], key: str, default: bool, *, table: str) -> bool:
    """Read a boolean setting, reporting the offending key if it is the wrong type."""
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(
            f"[{table}] {key} must be a boolean, got {type(value).__name__}: {value!r}"
        )
    return value


def _as_str_list(
    section: dict[str, object], key: str, default: list[str], *, table: str
) -> list[str]:
    """Read a list-of-strings setting, reporting the offending key on mismatch."""
    value = section.get(key, default)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(
            f"[{table}] {key} must be a list of strings, got {value!r}"
        )
    return list(value)


def _parse_llm(section: dict[str, object]) -> LLMConfig:
    """Build the LLM configuration from its raw TOML table.

    Candidates are declared per role as arrays of tables::

        [[llm.candidates.converse]]
        name = "local"
        provider = "ollama"
        base_url = "http://localhost:11434"
        model = "qwen3:8b"

    Args:
        section: The raw ``[llm]`` table.

    Returns:
        A validated LLMConfig.

    Raises:
        ConfigError: If a candidate is malformed or names an unknown provider.
    """
    raw_candidates = section.get("candidates", {})
    if not isinstance(raw_candidates, dict):
        raise ConfigError("[llm] candidates must be a table of roles")

    candidates: dict[str, list[LLMCandidate]] = {}
    for role, entries in raw_candidates.items():
        if not isinstance(entries, list):
            raise ConfigError(f"[llm.candidates.{role}] must be an array of tables")
        parsed: list[LLMCandidate] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ConfigError(f"[llm.candidates.{role}] entry {index} must be a table")
            table = f"llm.candidates.{role}"
            for required in ("name", "provider", "base_url", "model"):
                if required not in entry:
                    raise ConfigError(f"[{table}] entry {index} is missing '{required}'")
            provider = _as_str(entry, "provider", "", table=table)
            if provider not in ("openai", "ollama"):
                raise ConfigError(
                    f"[{table}] unknown provider {provider!r} — expected 'openai' or 'ollama'"
                )
            extra = entry.get("extra_body", {})
            if not isinstance(extra, dict):
                raise ConfigError(f"[{table}] extra_body must be a table")
            parsed.append(
                LLMCandidate(
                    name=_as_str(entry, "name", "", table=table),
                    provider=provider,
                    base_url=_as_str(entry, "base_url", "", table=table),
                    model=_as_str(entry, "model", "", table=table),
                    api_key_env=_as_str(entry, "api_key_env", "", table=table),
                    max_tokens=_as_int(entry, "max_tokens", 512, table=table),
                    temperature=_as_float(entry, "temperature", 0.2, table=table),
                    extra_body=dict(extra),
                )
            )
        candidates[str(role)] = parsed

    return LLMConfig(
        enabled=_as_bool(section, "enabled", False, table="llm"),
        timeout_sec=_as_float(section, "timeout_sec", 45.0, table="llm"),
        candidates=candidates,
    )


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
        llm=config.llm,
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
    llm_raw = _find_section(data, "llm", {})

    config = TelemachusConfig(
        identity=IdentityConfig(
            name=_as_str(identity_raw, "name", "Telemachus", table="identity"),
            creator=_as_str(identity_raw, "creator", "Revan", table="identity"),
            version=_as_str(identity_raw, "version", "0.1.0", table="identity"),
        ),
        paths=PathsConfig(
            data_dir=Path(_as_str(paths_raw, "data_dir", "./data", table="paths")),
            codex_dir=Path(_as_str(paths_raw, "codex_dir", "./codex", table="paths")),
            log_dir=Path(_as_str(paths_raw, "log_dir", "./logs", table="paths")),
        ),
        database=DatabaseConfig(
            path=_as_str(database_raw, "path", "telemachus.db", table="database"),
        ),
        logging=LoggingConfig(
            level=_as_str(logging_raw, "level", "INFO", table="logging"),
            format=_as_str(logging_raw, "format", "json", table="logging"),
            max_bytes=_as_int(logging_raw, "max_bytes", 10_485_760, table="logging"),
            backup_count=_as_int(logging_raw, "backup_count", 5, table="logging"),
        ),
        bootstrap=BootstrapConfig(
            phases=_as_str_list(
                bootstrap_raw,
                "phases",
                ["load_core_docs", "evaluate_state", "load_memory", "reconnect", "resume"],
                table="bootstrap",
            ),
            first_awakening=_as_bool(
                bootstrap_raw, "first_awakening", True, table="bootstrap"
            ),
        ),
        pipeline=PipelineConfig(
            timeout=_as_int(pipeline_raw, "timeout", 300, table="pipeline"),
            reflect_on_action=_as_bool(
                pipeline_raw, "reflect_on_action", True, table="pipeline"
            ),
            learn_on_action=_as_bool(
                pipeline_raw, "learn_on_action", True, table="pipeline"
            ),
        ),
        governance=GovernanceConfig(
            default_autonomy_level=_as_int(
                governance_raw, "default_autonomy_level", 1, table="governance"
            ),
            approval_risk_threshold=_as_int(
                governance_raw, "approval_risk_threshold", 3, table="governance"
            ),
        ),
        communication=CommunicationConfig(
            default_mode=_as_str(
                communication_raw, "default_mode", "collaborative", table="communication"
            ),
            emotional_awareness=_as_bool(
                communication_raw, "emotional_awareness", True, table="communication"
            ),
        ),
        memory=MemoryConfig(
            max_entries_per_domain=_as_int(
                memory_raw, "max_entries_per_domain", 100_000, table="memory"
            ),
            auto_index=_as_bool(memory_raw, "auto_index", True, table="memory"),
        ),
        llm=_parse_llm(llm_raw),
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

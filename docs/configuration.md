# Telemachus Configuration Guide

Telemachus is configured via a single TOML file: `telemachus.toml`. This document describes every configuration section and option.

## Configuration Loading

Telemachus searches for configuration in these locations (in order):

1. Path specified via `--config` CLI flag
2. `./telemachus.toml` (current directory)
3. `~/.config/telemachus/telemachus.toml` (XDG user config)
4. `/etc/telemachus/telemachus.toml` (system-wide)

The first file found is used. All values have sensible defaults.

## Full Configuration Reference

### `[identity]`

Identity metadata for this Telemachus instance.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | `"Telemachus"` | System name |
| `creator` | string | `"Revan"` | Creator name |
| `version` | string | `"0.1.0"` | System version |

### `[paths]`

Filesystem paths for persistent data and documents.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `data_dir` | string | `"./data"` | Directory for persistent data (database, logs) |
| `codex_dir` | string | `"./codex"` | Directory containing the Codex (core documents) |
| `log_dir` | string | `"./logs"` | Directory for log files |

All paths are relative to the working directory unless absolute.

### `[database]`

SQLite database configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `path` | string | `"telemachus.db"` | Database file path (relative to `data_dir`) |

### `[logging]`

Structured logging configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | string | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `format` | string | `"json"` | Log format: `"json"` for structured JSON, `"text"` for human-readable |
| `max_bytes` | int | `10485760` | Max bytes per log file before rotation (10 MB) |
| `backup_count` | int | `5` | Number of rotated log files to retain |

### `[bootstrap]`

Startup bootstrap protocol configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `phases` | list[string] | `["load_core_docs", "evaluate_state", "load_memory", "reconnect", "resume"]` | Bootstrap phases to execute in order |
| `first_awakening` | bool | `true` | Whether to enter First Awakening mode (asks questions before acting) |

**Bootstrap phases**:
1. `load_core_docs` — Load Constitution and Identity from codex directory
2. `evaluate_state` — Assess current system state
3. `load_memory` — Restore memory from persistent storage
4. `reconnect` — Attempt to reconnect with Revan
5. `resume` — Verify system integrity and resume normal operation

### `[pipeline]`

Cognitive pipeline configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `timeout` | int | `300` | Maximum pipeline execution time in seconds |
| `reflect_on_action` | bool | `true` | Run self-reflection after every action |
| `learn_on_action` | bool | `true` | Run learning updates after every action |

### `[governance]`

Governance subsystem configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_autonomy_level` | int | `1` | Default autonomy level for new domains (0-4) |
| `approval_risk_threshold` | int | `3` | Require explicit approval for risk level >= this |

**Autonomy levels**:
- `0` — Observation: observe, analyze, learn — no actions
- `1` — Suggestion: propose, recommend — no execution
- `2` — Limited: low-risk reversible actions
- `3` — Trusted: routine autonomous workflows
- `4` — Stewardship: manage trusted domains

### `[communication]`

Communication subsystem configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_mode` | string | `"collaborative"` | Default communication mode: `"direct"`, `"explained"`, `"collaborative"` |
| `emotional_awareness` | bool | `true` | Enable emotional state tracking and awareness |

### `[memory]`

Memory subsystem configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_entries_per_domain` | int | `100000` | Maximum entries per memory domain before archival |
| `auto_index` | bool | `true` | Enable automatic semantic indexing of new memories |

## Example Configuration

```toml
[identity]
name = "Telemachus"
creator = "Revan"
version = "0.1.0"

[paths]
data_dir = "./data"
codex_dir = "./codex"
log_dir = "./logs"

[database]
path = "telemachus.db"

[logging]
level = "INFO"
format = "json"
max_bytes = 10485760
backup_count = 5

[bootstrap]
phases = ["load_core_docs", "evaluate_state", "load_memory", "reconnect", "resume"]
first_awakening = true

[pipeline]
timeout = 300
reflect_on_action = true
learn_on_action = true

[governance]
default_autonomy_level = 1
approval_risk_threshold = 3

[communication]
default_mode = "collaborative"
emotional_awareness = true

[memory]
max_entries_per_domain = 100000
auto_index = true
```

## Validation

Run `telemachus config-check` to validate your configuration without starting the system. This will report any missing required fields, invalid values, or path issues.
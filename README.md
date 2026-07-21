# Telemachus

A local-first autonomous AI companion — layered cognitive system with structured decision pipelines and controlled evolution.

## Status

✅ **All 12 milestones complete** — 1013 tests passing, 89% code coverage, production-ready.

## Quick Start

```bash
# Clone and install
git clone <repo-url> telemachus
cd telemachus
pip install -e ".[dev]"

# Validate configuration
telemachus config-check

# Start the system (runs 5-phase bootstrap protocol)
telemachus start

# Interactive chat mode
telemachus chat
```

## Architecture Overview

Telemachus implements a **10-stage cognitive pipeline** that processes every input through a structured sequence:

```
Input → Communication → Risk → Ethics → Autonomy → Decision → Execution → Memory → Learning → Reflection → Evolution → Output
```

### Core Subsystems

| Subsystem | Module | Description |
|-----------|--------|-------------|
| **Identity & Constitution** | [`core/`](src/telemachus/core/) | Immutable identity traits, values, fears, and constitutional principles |
| **Memory** | [`memory/`](src/telemachus/memory/) | SQLite-backed 6-domain memory with versioning, semantic index, and retrieval |
| **Governance** | [`governance/`](src/telemachus/governance/) | Risk model (6 dimensions), ethical boundary engine, autonomy charter (5 levels), decision framework |
| **Cognition** | [`cognition/`](src/telemachus/cognition/) | Learning framework, self-reflection, goal system, project management, research framework, long-term evolution |
| **Interaction** | [`interaction/`](src/telemachus/interaction/) | Communication charter (3 modes), emotional model, CLI chat interface |
| **Tools** | [`tools/`](src/telemachus/tools/) | Extensible tool registry with trust tracking and permission checks |
| **Pipeline** | [`pipeline.py`](src/telemachus/pipeline.py) | Orchestrates all stages in the cognitive loop |
| **Bootstrap** | [`bootstrap.py`](src/telemachus/bootstrap.py) | 5-phase startup: Load Core Docs → Evaluate State → Load Memory → Reconnect → Resume |

### Key Design Principles

- **Local-first**: No cloud dependencies. SQLite for persistence. Everything runs on your machine.
- **Immutable core**: Constitution and Identity are frozen dataclasses — they cannot be mutated at runtime.
- **Append-only memory**: All memory changes are events; nothing is ever deleted, only superseded.
- **Identity-preserving evolution**: System changes go through 6 validation checks before being applied.
- **Structured governance**: Every action passes through risk, ethics, and autonomy checks before execution.

## Configuration

Configuration is loaded from [`telemachus.toml`](telemachus.toml) (TOML format). See the file for all available settings including:

- `[identity]` — Name, creator, version
- `[paths]` — Data directory, codex directory, log directory
- `[database]` — SQLite database path
- `[logging]` — Log level, format, rotation
- `[bootstrap]` — Startup phases, first awakening mode
- `[pipeline]` — Timeout, reflection/learning flags
- `[governance]` — Default autonomy level, approval thresholds
- `[communication]` — Default mode, emotional awareness
- `[memory]` — Max entries per domain, auto-indexing

## CLI Commands

| Command | Description |
|---------|-------------|
| `telemachus start` | Full system startup with bootstrap protocol |
| `telemachus chat` | Interactive chat session |
| `telemachus config-check` | Validate configuration without starting |

## Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/telemachus --cov-report=term

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Project Structure

```
telemachus/
├── pyproject.toml              # Project metadata, dependencies, build
├── telemachus.toml             # Default configuration
├── README.md
├── codex/                      # Core documents (Constitution, Identity, charters, protocols)
├── plans/
│   └── ARCHITECTURE.md         # Full architecture and development plan
├── src/
│   └── telemachus/
│       ├── __init__.py
│       ├── main.py             # CLI entry point (Typer)
│       ├── config.py           # Configuration loading & validation
│       ├── logging_config.py   # Structured logging setup
│       ├── bootstrap.py        # Bootstrap protocol
│       ├── pipeline.py         # Cognitive pipeline orchestrator
│       ├── core/               # Identity, Constitution, shared types
│       ├── memory/             # SQLite store, domains, index, versioning, retrieval
│       ├── governance/         # Risk, ethics, autonomy, decision
│       ├── cognition/          # Learning, reflection, goals, projects, research, evolution
│       ├── interaction/        # Communication, emotional model, CLI chat
│       └── tools/              # Tool base class, registry
└── tests/                      # 1013 tests across all subsystems
```

## Test Coverage

**89% overall** (3905 statements, 420 missed). The uncovered code is primarily CLI entry points (`main.py`, `cli_chat.py`) which require interactive terminal sessions and are validated through integration testing rather than unit tests.

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Modern Python, excellent typing |
| CLI | Typer | Rich help, autocompletion |
| Config | TOML (stdlib `tomllib`) | Python ecosystem standard |
| Database | SQLite (stdlib `sqlite3`) | Zero-dependency local persistence |
| Logging | stdlib `logging` + `python-json-logger` | Structured JSON logs |
| Testing | pytest + pytest-cov | Industry standard |
| Linting | ruff | Fast, comprehensive |
| Type checking | mypy (strict mode) | Full type safety |
| Build | hatchling | Modern PEP 621 build system |

## License

MIT
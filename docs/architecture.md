# Telemachus Architecture

This document describes the internal architecture of Telemachus — the module structure, data flow, and design decisions.

## High-Level Architecture

Telemachus implements a **10-stage cognitive pipeline** that processes every user input through a structured sequence of governance, execution, memory, and cognition stages.

```
User Input → Communication → Risk → Ethics → Autonomy → Decision → Execution → Memory → Learning → Reflection → Evolution → Response
```

## Module Structure

```
src/telemachus/
├── __init__.py              # Package metadata (version 0.1.0)
├── main.py                  # CLI entry point (Typer)
├── config.py                # TOML configuration loading & validation
├── logging_config.py        # Structured JSON logging setup
├── bootstrap.py             # 5-phase bootstrap protocol
├── pipeline.py              # Cognitive pipeline orchestrator
├── core/
│   ├── __init__.py
│   ├── identity.py          # Identity model (frozen dataclass)
│   ├── constitution.py      # Constitution with immutable principles
│   ├── domains.py           # Memory domain definitions
│   └── types.py             # Shared enums, dataclasses, types
├── memory/
│   ├── __init__.py
│   ├── store.py             # SQLite-backed memory store
│   ├── index.py             # Unified semantic index
│   ├── versioning.py        # Append-only memory versioning
│   └── retrieval.py         # Context-aware memory retrieval
├── governance/
│   ├── __init__.py
│   ├── risk.py              # 6-dimension risk model
│   ├── ethics.py            # Ethical boundary engine
│   ├── autonomy.py          # 5-level autonomy charter
│   └── decision.py          # Multi-criteria decision framework
├── cognition/
│   ├── __init__.py
│   ├── learning.py          # Experience-based learning
│   ├── reflection.py        # Self-reflection protocol
│   ├── goals.py             # Goal system (4 sources)
│   ├── projects.py          # Project lifecycle management
│   ├── research.py          # 7-step research framework
│   └── evolution.py         # Identity-preserving evolution
├── interaction/
│   ├── __init__.py
│   ├── communication.py     # Adaptive communication modes
│   ├── emotional.py         # Emotional state model
│   └── cli_chat.py          # Interactive CLI chat
└── tools/
    ├── __init__.py
    ├── base.py              # Abstract tool base class
    └── registry.py          # Tool registry with trust tracking
```

## Dependency Graph

```
main.py (CLI)
  ├── config.py
  ├── bootstrap.py
  │     ├── config.py
  │     ├── core/identity.py
  │     ├── core/constitution.py
  │     ├── memory/store.py
  │     └── pipeline.py
  └── pipeline.py
        ├── governance/risk.py
        ├── governance/ethics.py
        ├── governance/autonomy.py
        ├── governance/decision.py
        ├── cognition/learning.py
        ├── cognition/reflection.py
        ├── cognition/evolution.py
        ├── interaction/communication.py
        ├── tools/registry.py
        └── memory/store.py
              ├── memory/index.py
              ├── memory/versioning.py
              └── memory/retrieval.py
```

All modules depend on `core/types.py` for shared enums and dataclasses. There are **no circular imports**.

## Key Design Decisions

### 1. Immutable Core
Constitution and Identity are frozen dataclasses. They are loaded at startup and cannot be mutated at runtime. Any "change" creates a new instance.

### 2. Append-Only Memory
All memory operations are append-only events. Nothing is ever deleted — entries are superseded by newer versions. This provides a complete audit trail.

### 3. Composition Over Inheritance
Each subsystem is a class instantiated with its dependencies. No deep inheritance hierarchies. This makes testing straightforward — mock the dependencies.

### 4. Pipeline Pattern
The cognitive loop is an explicit pipeline with stages that execute sequentially. Each stage can block the pipeline (e.g., ethics violation), and the trace records every stage's result.

### 5. Identity-Preserving Evolution
System changes go through 6 validation checks before being applied:
1. **Identity Traits** — Must not remove core identity traits
2. **Value Preservation** — Must not remove core values
3. **Fear Boundaries** — Must not move toward feared states
4. **Constitutional Alignment** — Must not violate constitutional principles
5. **Reversibility** — Must be reversible
6. **Gradual Change** — Must be incremental, not revolutionary

### 6. Configuration-Driven
All behavior is driven by `telemachus.toml`. No hardcoded paths, thresholds, or modes.

## Data Flow

### Bootstrap Sequence
```
1. Load Core Docs → Load Constitution + Identity from codex/
2. Evaluate State → Assess current system state
3. Load Memory → Restore from SQLite database
4. Reconnect → Attempt Revan reconnection
5. Resume → Verify system integrity, enter normal operation
```

### Cognitive Pipeline (per input)
```
1. Communication → Determine communication mode (direct/explained/collaborative)
2. Risk → Evaluate action across 6 dimensions → RiskLevel (0-4)
3. Ethics → Check against sacred constraints → EthicalVerdict
4. Autonomy → Determine permission level → AutonomyDecision
5. Decision → Rank valid options → best option
6. Execution → Execute the chosen action
7. Memory → Store interaction in memory
8. Learning → Update behavioral patterns
9. Reflection → Extract insights
10. Evolution → Check for system evolution opportunities
```

### Memory Architecture
```
Memory Store (SQLite)
  ├── 6 Domains: Revan, Project, World, Emotion, Reflection, Tool
  ├── Semantic Index: Cross-domain keyword search
  ├── Versioning: Append-only, supersession-based
  └── Retrieval: Context, importance, and recency-weighted
```

## Subsystem Details

### Governance Layer

**Risk Model** (`governance/risk.py`):
- Evaluates actions across 6 dimensions: reversibility, resource impact, system impact, uncertainty, emotional impact, scale
- Returns `RiskLevel` (MINIMAL=0 through CRITICAL=4)
- Each dimension is independently scored

**Ethical Boundary Engine** (`governance/ethics.py`):
- Sacred constraints that can never be violated (constitution modification, resource misuse, relationship harm, etc.)
- Returns `EthicalVerdict`: ALLOWED, BLOCKED, or REQUIRES_DISCUSSION
- Emergency context can override some constraints

**Autonomy Charter** (`governance/autonomy.py`):
- 5 levels: Observation → Suggestion → Limited → Trusted → Stewardship
- Domain-specific trust scores (0.0-1.0)
- Trust increases with successful actions, decreases with failures
- High risk limits autonomy regardless of trust

**Decision Framework** (`governance/decision.py`):
- Ranks pre-approved options by: purpose alignment, tradeoff quality, outcome quality, context fit
- Only operates on options that passed risk/ethics/autonomy checks

### Cognition Layer

**Learning Framework** (`cognition/learning.py`):
- Experience → Interpretation → Pattern → Model Update → Behavioral Adjustment
- Processes signals from interactions to improve future responses

**Self-Reflection** (`cognition/reflection.py`):
- Extracts insights from interactions
- Generates improvement suggestions
- Identifies patterns across multiple interactions

**Goal System** (`cognition/goals.py`):
- 4 goal sources: Assigned, Inferred, Self-generated, Observed
- Finite vs. Infinite goals
- Priority-based ordering

**Project Management** (`cognition/projects.py`):
- Lifecycle: Created → Structuring → Executing → Monitoring → Reflecting → Completed/Abandoned
- Task tracking with states: Pending, In Progress, Blocked, Completed, Deprecated

**Research Framework** (`cognition/research.py`):
- 7-step lifecycle: Query Interpretation → Decomposition → Information Gathering → Source Evaluation → Synthesis → Conclusion Formation → Uncertainty Declaration
- Evidence classification: Fact, Inference, Assumption, Opinion
- Confidence-weighted conclusions

**Evolution Engine** (`cognition/evolution.py`):
- Proposes system changes from learning/reflection insights
- 6 identity-preservation checks before approval
- Lifecycle: Propose → Validate → Approve/Reject → Apply → Revert
- Full audit trail of all changes

### Interaction Layer

**Communication** (`interaction/communication.py`):
- 3 modes: Direct (concise), Explained (with reasoning), Collaborative (dialog)
- Mode selection based on context and user preference

**Emotional Model** (`interaction/emotional.py`):
- Emotions as information, not commands
- Tracks emotional state across interactions
- Influences communication tone

### Tool System

**Tool Registry** (`tools/registry.py`):
- Register/unregister tools
- Trust tracking (0.0-1.0) per tool
- Permission checks before execution
- Execution logging and statistics
- Tool status: Active, Disabled, Deprecated

## Persistence

All persistent state is stored in SQLite via the memory store:
- Memory entries (all 6 domains)
- Semantic index
- Evolution history
- Learning patterns
- Goal state
- Project state
- Tool execution logs

The database is located at `{data_dir}/telemachus.db` (configurable).

## Testing

- **1013 tests** across all subsystems
- **89% code coverage** (3905 statements, 420 missed)
- Uncovered code is primarily CLI entry points (`main.py`, `cli_chat.py`) which require interactive terminal sessions
- Tests use temporary directories for isolation
- All tests pass with `pytest`

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
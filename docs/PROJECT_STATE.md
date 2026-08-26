# Telemachus Project State

> Project-memory index. See [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for the source-authority order and how to use these files.

## Project Identity

Telemachus is a local-first autonomous AI companion — a layered cognitive system intended to act as a trusted "chief-of-staff": preserving context, managing complexity, and helping its creator make consistent progress on long-term goals. No cloud dependencies; SQLite for all persistence. Source: [README.md](../README.md), [codex/vision/CORE_VISION.md](../codex/vision/CORE_VISION.md).

## Architectural Philosophy

Three architectural layers, per [docs/runtime.md](runtime.md):

| Layer | Responsibility | Status |
|---|---|---|
| **Core** | Timeless intelligence — cognition, memory, governance, identity, communication | Implemented |
| **Runtime** | Orchestration — lifecycle, scheduling, recovery, event routing, resource management | Partially implemented (Lifecycle only) |
| **Plugins** | External system interfaces (GitHub, Gmail, Calendar, etc.) | Not started |

Governing principles established in the Codex and ADRs (full register: [DECISIONS.md](DECISIONS.md)):
- Immutable Constitution and Identity; append-only memory; every action gated by Risk → Ethics → Autonomy → Decision.
- "The Core reasons. The Runtime orchestrates." (ADR-001) — Runtime never performs reasoning; Core never depends on Runtime.
- "Every startup is a recovery." (ADR-002) — initialization happens once, at installation, ever.

## Current Milestone

**Runtime Lifecycle and Session Continuity.**

Status: **implemented, tested, and validated — present in the working tree, not yet committed.** The last commit on `main` is `78cd2be` ("fix: handle Windows paths in CLI test fixtures"), which predates this milestone entirely. See [DEVELOPMENT_STATE.md](DEVELOPMENT_STATE.md) for the exact diff and file list.

## Implementation Status

| Subsystem | Status | Notes |
|---|---|---|
| Core (identity, constitution, types) | **Implemented, Tested** | Wired into every entry point |
| Governance (risk, ethics, autonomy, decision) | **Implemented, Tested** | Wired; runs on every pipeline call |
| Memory — store | **Implemented, Tested** | The only memory component reachable from production code |
| Memory — index, retrieval, versioning | Implemented, Tested, **not reachable from production** | Constructed only inside their own unit tests |
| Cognition — learning, reflection, evolution | **Implemented, Tested** | Wired; pipeline stages 8–10 |
| Cognition — goals, projects, research | Implemented, Tested, **not reachable from production** | Constructed only inside their own unit tests |
| Interaction — communication engine | **Implemented, Tested** | Wired in the CLI, but runs *after* the pipeline, not as pipeline stage 1 |
| Tools (base, registry) | Implemented, Tested, **not reachable from production** | Pipeline's Execution stage is a stub — nothing ever calls the registry |
| Configuration | **Implemented, Tested** | `[llm]` section was being silently dropped on load; fixed this session (see DECISIONS.md) |
| Bootstrap (5-phase protocol) | **Implemented, Tested** | Runs correctly as one indivisible unit. Codex markdown files are existence-checked but never parsed — Constitution/Identity always come from hardcoded Python defaults. **Not established in repository** whether this is intentional or a gap. |
| **Runtime / Lifecycle** | **Implemented, Tested — working tree, uncommitted** | State machine, `runtime.db` persistence, signal handling, recovery/reconciliation. Live-validated (see below). |
| Event Loop | **Specified only** | `docs/event_loop.md` fully specifies it; no source exists |
| LLM integration (router) | Implemented, Tested in isolation, **not integrated** | `llm/router.py` exists and is well-tested standalone-fashion, but is constructed nowhere in production and carries 0% coverage from the main suite |
| Plugins | **Specified only** | `docs/runtime.md` names the concept; no source exists |
| Persistence (SQLite/WAL) | **Implemented, Tested** | `telemachus.db` (Core) and `runtime.db` (Runtime) are separate files, separate connections |
| Scheduling / semantic readiness | **Specified only** | `docs/event_loop.md`; depends on the Event Loop |
| Recovery | **Implemented, Tested** | Runtime-level session recovery and crash detection work end-to-end (live-validated). Core-level "recovery" (Bootstrap Phase 3, "Load Memory") is a read-only integrity check, not a restore of prior in-flight work — there is no in-flight work to restore without the Event Loop |

## Current Validation

Most recent run, this session, against the current (uncommitted) working tree:

| Check | Result |
|---|---|
| `pytest` | **1166 passed**, 0 failed |
| Coverage | 87% overall (4567 statements, 610 missed); new `runtime/` package alone: 96% |
| `ruff check .` | All checks passed |
| `mypy --strict src/` | Success, no issues, 43 source files |
| `telemachus start` (live) | Reaches `RUNNING`; 5-phase bootstrap completes; lifecycle transitions logged correctly |
| Clean shutdown (live) | Validated via a programmatic trigger — zero WAL/`-shm` sidecar files remain on either database afterward. **A real OS-delivered Ctrl+C could not be exercised in this execution environment** (isolated to a harness/console limitation via a minimal non-Telemachus repro, not a code defect) |
| Crash recovery (live) | Validated via a real forced process kill + restart — correctly detected as `UNCLEAN`, briefing displayed, `Recovery → Reconciliation → Running` sequence correct |

## Immediate Next Step

1. Review and commit the working-tree changes (Runtime Lifecycle milestone + the `[llm]` config fix). Nothing currently blocks this — all validation above is green.
2. After that: the Event Loop (`docs/event_loop.md`) is the next architecture milestone. It has **not** been started. It was deliberately deferred until Lifecycle landed (see [DECISIONS.md](DECISIONS.md)).

## Explicitly Not Yet Implemented

Do not treat any of the following as complete:

- Event Loop, Observation model, Processing Context, semantic readiness, priority/dependency/resource scheduling
- Plugins and the plugin manager
- LLM router wired into the cognitive pipeline (the router itself exists; nothing calls it)
- Pipeline stage 1 (Communication) and stage 6 (Execution) — both are stubs that pass through unconditionally
- Actual parsing of Codex markdown into Constitution/Identity objects
- A single-instance guard for the Runtime (two concurrent processes sharing one `data_dir` will each misread the other's session as a crash)

## Last Updated

2026-08-26

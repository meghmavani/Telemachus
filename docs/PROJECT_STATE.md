# Telemachus Project State

> Project-memory index. See [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for the source-authority order and how to use these files.

## Project Identity

Telemachus is a local-first autonomous AI companion — a layered cognitive system intended to act as a trusted "chief-of-staff": preserving context, managing complexity, and helping its creator make consistent progress on long-term goals. No cloud dependencies; SQLite for all persistence. Source: [README.md](../README.md), [codex/vision/CORE_VISION.md](../codex/vision/CORE_VISION.md).

## Architectural Philosophy

Three architectural layers, per [docs/runtime.md](runtime.md):

| Layer | Responsibility | Status |
|---|---|---|
| **Core** | Timeless intelligence — cognition, memory, governance, identity, communication | Implemented |
| **Runtime** | Orchestration — lifecycle, scheduling, recovery, event routing, resource management | Partially implemented (Lifecycle + EL-1 Event Loop intake; richer Event Loop stages, scheduling and plugins not started) |
| **Plugins** | External system interfaces (GitHub, Gmail, Calendar, etc.) | Not started |

Governing principles established in the Codex and ADRs (full register: [DECISIONS.md](DECISIONS.md)):
- Immutable Constitution and Identity; append-only memory; every action gated by Risk → Ethics → Autonomy → Decision.
- "The Core reasons. The Runtime orchestrates." (ADR-001) — Runtime never performs reasoning; Core never depends on Runtime.
- "Every startup is a recovery." (ADR-002) — initialization happens once, at installation, ever.

## Current Milestone

**State Documentation Reconciliation** (this update). Committed milestone sequence on `main` (oldest first):

1. `a8464e8` Runtime Lifecycle and Session Continuity
2. `58c3dc1` Core Execution + Trace Persistence (Stage 6, `PipelineTrace`)
3. `7e01a91` Codex documentation: canonical Protected Constraints and authority hierarchy
4. `4176e81` Codex Authority Layer (Constitution loaded from the Codex)
5. `e6df65c` Constitutional action validation wired into Stage 6
6. `c21bee3` Verified Tool capability envelope
7. `3ece69c` EL-1: Runtime Tick + Observation Intake
8. `63a421d` RS-1: Recovery Briefing fed into the Event Loop
9. `00fc421` Observation provenance preserved in `PipelineTrace`

There is no open implementation task. See [DEVELOPMENT_STATE.md](DEVELOPMENT_STATE.md).

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
| Tools (base, registry) | **Implemented, Tested** | Reachable through pipeline Stage 6 via `wiring.build_tool_registry()`; the only registered tool is `EchoTool` (PASSIVE). `Tool.protected_constraints` is a typed, tool-declared set; it is **not verified** against what `execute()` does. No ACTIVE or AUTONOMOUS tool exists. |
| Configuration | **Implemented, Tested** | `[llm]` section was previously dropped silently on load; fixed (see DECISIONS.md) |
| Bootstrap (5-phase protocol) | **Implemented, Tested** | Runs as one indivisible unit. Phase 1 loads the Constitution from the Codex (`core/codex.py`): five Protected Constraints from `codex/philosophy/CONSTITUTION.md`, plus consistency checks on the Autonomy Charter, Ethical Boundary Engine and System Integration documents. A malformed Constitution fails Bootstrap; a missing document falls back softly. |
| **Runtime / Lifecycle** | **Implemented, Tested** | State machine, `runtime.db` persistence, signal handling, recovery/reconciliation (committed at `a8464e8`). |
| Event Loop (EL-1) | **Implemented, Tested** | `runtime/event_loop.py`, `runtime/observations.py`: bounded (1000) in-memory priority queue, FIFO within priority, one dispatch per tick, per-observation failure isolation, main-thread/synchronous, opaque Core invoker (`wiring.build_observation_invoker`). Creates no `ActionRequest`; executes no tool. Queue and `ProcessingContext` are in memory only. |
| Runtime-originated observations (RS-1) | **Implemented, Tested** | `wiring.build_recovery_observation()`; `main.py start` submits one Recovery Observation per successful start at `Priority.NORMAL` for every termination classification. The **only** production Observation source. Result is `NO_ACTION`. |
| Observation provenance | **Implemented, Tested** | `PipelineTrace.observation` (`ObservationProvenance`: `observation_id`, `observation_type`, `source`). Plain synchronous chat records none. |
| Codex authority / constitutional gate | **Implemented, Tested** | Codex-derived `Constitution.validate_action()` runs in Stage 6 before the autonomy gate. Effective impact = `ActionRequest.affects` ∪ `Tool.protected_constraints`. |
| LLM integration (router) | Implemented, Tested in isolation, **not integrated** | `llm/router.py` exists and is well-tested standalone-fashion, but is constructed nowhere in production and carries 0% coverage from the main suite |
| Plugins | **Specified only** | `docs/runtime.md` names the concept; no source exists |
| Event Loop stages beyond EL-1 (Signal Processor, Aggregation, dynamic priority, dependency/resource scheduling, deadlines, Runtime modes) | **Specified only** | `docs/event_loop.md`; no source exists, and there is no second Observation source to justify them |
| Persistence (SQLite/WAL) | **Implemented, Tested** | `telemachus.db` (Core) and `runtime.db` (Runtime) are separate files, separate connections |
| Scheduling / semantic readiness | **Specified only** | `docs/event_loop.md`. Only structural readiness (queue non-empty) exists. |
| Recovery | **Implemented, Tested** | Runtime-level session recovery and crash detection work end-to-end. Core-level "recovery" (Bootstrap Phase 3, "Load Memory") is a read-only integrity check. Queued Observations are in memory only and are not replayed after a crash (reconciliation, not replay). |

## Current Validation

Most recent full run, at `00fc421` plus documentation-only changes:

| Check | Result |
|---|---|
| `pytest` | **1375 passed**, 0 failed |
| Coverage | 88% overall (5135 statements, 620 missed) |
| `ruff check .` | All checks passed |
| `mypy --strict src/telemachus` | Success, no issues, 47 source files |

Live validations (Runtime lifecycle, Event Loop, Recovery Observation including a simulated-crash restart detected as `UNCLEAN`) were performed in isolated temp directories at earlier milestones; they are not part of the automated suite. A real OS-delivered Ctrl+C has still not been exercised in the available environment (see DECISIONS.md, Q7).

## Immediate Next Step

No implementation is in flight. The remaining Event Loop stages (Signal Processor, Aggregation, dynamic priority, dependency/resource scheduling, deadlines) currently have no real production input to act on. Generating an `ActionRequest` from an Observation is blocked on the unresolved items under "Action path" below and needs its own design pass first.

## Action path

**Implemented:**
- The `ActionRequest` type exists (`core/types.py`).
- Constitutional validation exists (`Constitution.validate_action()`), run before the autonomy gate in Stage 6.
- The tool protected-capability floor exists: effective impact is `ActionRequest.affects` ∪ `Tool.protected_constraints`.
- Stage 6 can reject actions (`DENIED_CONSTITUTION`, `DENIED_AUTONOMY`, `DENIED_TOOL`, ...) and its `ExecutionRecord` is persisted.

**Not implemented / unresolved:**
- No production code produces an `ActionRequest`; every Observation ends as `NO_ACTION`.
- `ActionRequest.human_authorized` is declared by whoever constructs the request.
- `ActionRequest.affects` is declared by whoever constructs the request.
- `Tool.protected_constraints` declarations are not verified against `execute()` behaviour.
- `AutonomyCharter.check_initiative()` exists but has no production caller and decides by free-text substring matching.
- No domain is defined for Runtime-originated observations; the autonomy stage falls back to the `"research"` domain.
- Observations enter the pipeline through the existing user-input-shaped path (summary passed as `user_input`) and are stored by Stage 7 as `pipeline_interaction` records.
- Autonomy/action generation is intentionally deferred.

## Explicitly Not Yet Implemented

Do not treat any of the following as complete:

- Signal Processor, Observation aggregation, dynamic/effective priority, dependency analysis, resource/deadline scheduling, Runtime modes, periodic work
- Any Observation source other than the startup Recovery Briefing
- Plugins and the plugin manager
- LLM router wired into the cognitive pipeline (the router itself exists; nothing calls it)
- Pipeline stage 1 (Communication) is a stub that passes through unconditionally
- Generation of `ActionRequest`s; ACTIVE or AUTONOMOUS tools
- Verification of tool protected-capability declarations against `execute()`
- A single-instance guard for the Runtime (two concurrent processes sharing one `data_dir` will each misread the other's session as a crash)

## Last Updated

2026-10-07

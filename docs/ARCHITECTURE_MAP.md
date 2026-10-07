# Telemachus Architecture Map

> Compact index over the architecture. Canonical detail lives in [docs/runtime.md](runtime.md), [docs/architecture.md](architecture.md), [docs/api.md](api.md), and the Codex. This file is a map, not a replacement for those.

## Layers and Ownership

| Component | Responsibility | May depend on | Must NOT depend on | Implemented? |
|---|---|---|---|---|
| **Codex** (`codex/`) | Constitutional/philosophical source documents — identity, values, protocols | nothing (markdown only) | — | Loaded at Bootstrap: `core/codex.py` parses `philosophy/CONSTITUTION.md` into the five Protected Constraints and validates the Autonomy Charter, Ethical Boundary Engine and System Integration documents — see below |
| **Runtime** (`src/telemachus/runtime/`) | Process lifecycle, lifecycle state, crash detection, recovery, reconciliation, signal handling, `runtime.db` | Core, Memory, `config`, `bootstrap` | — | **Implemented**: Lifecycle, plus EL-1 Event Loop intake (`event_loop.py`, `observations.py`). Signal processing, aggregation, dynamic priority, dependency/resource scheduling, deadlines and plugins **not started** |
| **Core** (`core/`) | Identity, Constitution, shared types — frozen, immutable | nothing else in the tree | Runtime | Implemented |
| **Governance** (`governance/`) | Risk, ethics, autonomy, decision — gates every action | `core/` | Runtime, Cognition | Implemented |
| **Memory** (`memory/`) | `telemachus.db` schema, storage, versioning, indexing, retrieval | `core/` | Runtime | `store.py` implemented and wired; `index.py`/`retrieval.py`/`versioning.py` implemented but **unreachable from production** |
| **Cognition** (`cognition/`) | Learning, reflection, evolution, goals, projects, research | `core/`, `memory/`, `governance/` | Runtime | `learning`/`reflection`/`evolution` wired; `goals`/`projects`/`research` implemented but **unreachable from production** |
| **Interaction** (`interaction/`) | `communication.py` (Core: mode selection, tone) + `cli_chat.py` (CLI: REPL) | `core/`; `cli_chat.py` also imports Runtime | `communication.py` must not import Runtime | Both implemented |
| **Tools** (`tools/`) | Tool base class, registry, trust tracking | `core/` | Runtime | Implemented. Reachable through Stage 6 via `wiring.build_tool_registry()`, which registers only `EchoTool` (PASSIVE). `Tool.protected_constraints` is declared per tool; no ACTIVE or AUTONOMOUS tool exists |
| **LLM** (`llm/`) | Multi-provider completion router | `config` | Runtime, Core | Implemented in isolation, **never constructed in production** |
| **Persistence** | Two separate SQLite files: `telemachus.db` (Memory/Core) and `runtime.db` (Runtime) | — | — | Both implemented; deliberately separate so Runtime crash-detection doesn't depend on Core memory health |
| **Plugins** | External system interfaces (GitHub, Gmail, Calendar, …) | Runtime only, never Core directly | Core | **Not started** — no source directory exists |
| **CLI** (`main.py`, `interaction/cli_chat.py`) | Argument parsing, presentation, delegates lifecycle to Runtime | Runtime, Core, `wiring` | — | Implemented |
| **Composition root** (`wiring.py`) | The only place production code constructs `MemoryStore`, `CognitivePipeline`, `RuntimeLifecycle`, `EventLoop`, the observation invoker and the recovery Observation | Core, Memory, Runtime | — | Implemented |

## The Codex Is Loaded

`bootstrap.py` loads the Constitution from `codex/philosophy/CONSTITUTION.md` via `core/codex.py` (`create_constitution_from_codex()`). The five canonical Protected Constraints (Constitution Integrity, Human Meaning, Relationship Integrity, Resource Authorization, Human Authority over Life-Impacting Decisions) come from its `## Protected Constraints` section. A missing document falls back softly; a present but malformed one fails Bootstrap. Identity fields with Codex authority are also read from the Codex. The Runtime transports `BootstrapResult.constitution` but does not parse or interpret the Codex (enforced by `tests/test_runtime_boundaries.py`). Legacy `Constitution.sacred_constraints` and `CorePrinciple.is_sacred` remain for compatibility and are not authoritative; the Python-defined sets in `governance/ethics.py` (`ETHICAL_CONCERNS`) and `governance/autonomy.py` (keyword sets) are not derived from the Codex.

## Dependency Diagram (current, verified)

```
                        ┌─────────────────────┐
                        │        CLI          │
                        │  main.py, cli_chat.py│
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   wiring.py          │   (composition root)
                        │ build_runtime()       │
                        │ build_memory_store()  │
                        │ build_pipeline()       │
                        │ build_event_loop()     │
                        │ build_recovery_observation() │
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                                     ▼
      ┌─────────────────────┐                ┌─────────────────────┐
      │   RUNTIME            │                │       CORE           │
      │  runtime/lifecycle.py │  ── invokes ──▶│  bootstrap.py         │
      │  runtime/state_store  │   (5 phases,   │  (5-phase protocol,   │
      │  runtime/signals      │    opaque      │   indivisible)        │
      │  runtime/event_loop   │    result)     └──────────┬───────────┘
      │  runtime/observations │                            │
      │  runtime/states       │
      └──────────┬───────────┘                            │
                 │ owns                                     │ loads
                 ▼                                            ▼
         runtime.db                                 core/identity.py
      (installation, sessions)                       core/constitution.py
                                                       (Codex-derived Constitution;
                                                        Identity from Codex fields)
                                                                │
                                                                ▼
                                                    ┌─────────────────────┐
                                                    │  pipeline.py          │
                                                    │  (10-stage, sync)     │
                                                    └──────────┬───────────┘
                             ┌─────────────────────────────────┼──────────────────────────┐
                             ▼                                 ▼                             ▼
                  ┌──────────────────┐            ┌──────────────────┐          ┌──────────────────┐
                  │   GOVERNANCE      │            │    COGNITION       │          │     MEMORY          │
                  │ risk/ethics/      │            │ learning/reflection/│          │   store.py           │
                  │ autonomy/decision │            │ evolution wired    │          │  (telemachus.db)     │
                  │  — all wired      │            │ goals/projects/    │          └──────────────────┘
                  └──────────────────┘            │ research: UNWIRED  │
                                                    └──────────────────┘

      interaction/communication.py — Core, wired in CLI AFTER the pipeline
      tools/{base,registry}.py     — Core, wired for Stage 6 (EchoTool only)
      llm/router.py                — standalone, UNWIRED (no production caller)
      Plugins                      — do not exist
```

**Verified boundary:** no module under `core/`, `memory/`, `governance/`, `cognition/`, or `tools/` imports `telemachus.runtime` (enforced by `tests/test_runtime_boundaries.py`, which runs on every test suite invocation). That test also forbids `runtime/` from importing `telemachus.pipeline`, `telemachus.wiring`, `telemachus.tools` or `telemachus.core.codex`, and from naming `Constitution`/`ProtectedConstraint`.

## Reading This Diagram

- The Runtime **invokes** the Core's bootstrap protocol; it does not replace or reorder it, and it only ever reads `result.success` from it (ADR-001).
- `pipeline.py` is a single synchronous call. Synchronous chat (`cli_chat.py`) calls it directly and builds no Event Loop. `main.py`'s `start` command builds a pipeline and an `EventLoop`, submits one Recovery Observation (built by `wiring.build_recovery_observation()` from the startup `RecoveryBriefing`, `Priority.NORMAL`) and ticks the loop once per second from `RuntimeLifecycle.wait_for_shutdown_request()`. That is the **only** production Observation source. Each Observation reaches `pipeline.process()` through the existing user-input-shaped path (summary as `user_input`) with no `ActionRequest`, so Stage 6 yields `NO_ACTION`. `PipelineTrace.observation` (`ObservationProvenance`: id, type, source) records which Observation drove a run; plain chat records none.
- No production code constructs an `ActionRequest`. See PROJECT_STATE.md, "Action path".
- Everything drawn as "UNWIRED" above is real, tested code that is simply never constructed by anything on the path from `main.py` or `cli_chat.py`.

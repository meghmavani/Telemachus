# Telemachus Architecture Map

> Compact index over the architecture. Canonical detail lives in [docs/runtime.md](runtime.md), [docs/architecture.md](architecture.md), [docs/api.md](api.md), and the Codex. This file is a map, not a replacement for those.

## Layers and Ownership

| Component | Responsibility | May depend on | Must NOT depend on | Implemented? |
|---|---|---|---|---|
| **Codex** (`codex/`) | Constitutional/philosophical source documents — identity, values, protocols | nothing (markdown only) | — | Documents exist; **not parsed at runtime** — see below |
| **Runtime** (`src/telemachus/runtime/`) | Process lifecycle, lifecycle state, crash detection, recovery, reconciliation, signal handling, `runtime.db` | Core, Memory, `config`, `bootstrap` | — | **Implemented** (Lifecycle only; Event Loop/scheduling/plugins not started) |
| **Core** (`core/`) | Identity, Constitution, shared types — frozen, immutable | nothing else in the tree | Runtime | Implemented |
| **Governance** (`governance/`) | Risk, ethics, autonomy, decision — gates every action | `core/` | Runtime, Cognition | Implemented |
| **Memory** (`memory/`) | `telemachus.db` schema, storage, versioning, indexing, retrieval | `core/` | Runtime | `store.py` implemented and wired; `index.py`/`retrieval.py`/`versioning.py` implemented but **unreachable from production** |
| **Cognition** (`cognition/`) | Learning, reflection, evolution, goals, projects, research | `core/`, `memory/`, `governance/` | Runtime | `learning`/`reflection`/`evolution` wired; `goals`/`projects`/`research` implemented but **unreachable from production** |
| **Interaction** (`interaction/`) | `communication.py` (Core: mode selection, tone) + `cli_chat.py` (CLI: REPL) | `core/`; `cli_chat.py` also imports Runtime | `communication.py` must not import Runtime | Both implemented |
| **Tools** (`tools/`) | Tool base class, registry, trust tracking | `core/` | Runtime | Implemented, **unreachable from production** (pipeline's Execution stage is a stub) |
| **LLM** (`llm/`) | Multi-provider completion router | `config` | Runtime, Core | Implemented in isolation, **never constructed in production** |
| **Persistence** | Two separate SQLite files: `telemachus.db` (Memory/Core) and `runtime.db` (Runtime) | — | — | Both implemented; deliberately separate so Runtime crash-detection doesn't depend on Core memory health |
| **Plugins** | External system interfaces (GitHub, Gmail, Calendar, …) | Runtime only, never Core directly | Core | **Not started** — no source directory exists |
| **CLI** (`main.py`, `interaction/cli_chat.py`) | Argument parsing, presentation, delegates lifecycle to Runtime | Runtime, Core, `wiring` | — | Implemented |
| **Composition root** (`wiring.py`) | The only place production code constructs `MemoryStore`, `CognitivePipeline`, and `RuntimeLifecycle` | Core, Memory, Runtime | — | Implemented |

## The Codex Is Not Parsed

`bootstrap.py`'s `_load_constitution()` / `_load_identity()` check whether the corresponding markdown file exists (for logging only), then unconditionally return `create_default_constitution()` / `create_default_identity()` — hardcoded Python factories. The 26 Codex documents currently have **no effect on runtime behavior**. **Not established in repository** whether parsing them is planned; `docs/architecture.md` states "the Codex markdown is the source of truth for the default values" as a design comment in `bootstrap.py`, not a committed roadmap item.

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
                        └──────────┬───────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                                     ▼
      ┌─────────────────────┐                ┌─────────────────────┐
      │   RUNTIME            │                │       CORE           │
      │  runtime/lifecycle.py │  ── invokes ──▶│  bootstrap.py         │
      │  runtime/state_store  │   (5 phases,   │  (5-phase protocol,   │
      │  runtime/signals      │    opaque      │   indivisible)        │
      │  runtime/states       │    result)     └──────────┬───────────┘
      └──────────┬───────────┘                            │
                 │ owns                                     │ loads
                 ▼                                            ▼
         runtime.db                                 core/identity.py
      (installation, sessions)                       core/constitution.py
                                                       (hardcoded defaults —
                                                        Codex not parsed)
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
      tools/{base,registry}.py     — Core, UNWIRED (Execution stage is a stub)
      llm/router.py                — standalone, UNWIRED (no production caller)
      Plugins                      — do not exist
```

**Verified boundary:** no module under `core/`, `memory/`, `governance/`, `cognition/`, or `tools/` imports `telemachus.runtime` (enforced by `tests/test_runtime_boundaries.py`, which runs on every test suite invocation).

## Reading This Diagram

- The Runtime **invokes** the Core's bootstrap protocol; it does not replace or reorder it, and it only ever reads `result.success` from it (ADR-001).
- `pipeline.py` is a single synchronous call — there is no Event Loop above it deciding *when* to invoke it. `main.py`'s `start` command reaches `RUNNING` and then just waits for a shutdown signal; it does not yet route external events into the pipeline.
- Everything drawn as "UNWIRED" above is real, tested code that is simply never constructed by anything on the path from `main.py` or `cli_chat.py`.

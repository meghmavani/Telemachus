# Telemachus Session Handoff

> Read this file first. It is the entry point into the other project-memory files, not a replacement for them.

## Source Authority

When sources disagree, the **higher** one wins, and the discrepancy should be reported rather than silently resolved:

1. **Codex / constitutional documents** (`codex/`)
2. **Approved architectural specifications** (`docs/runtime.md`, `docs/lifecycle.md`, `docs/event_loop.md`)
3. **Approved ADRs / runtime decisions** (`docs/runtime_decisions.md`)
4. **Current implementation** (`src/telemachus/`)
5. **Tests** (`tests/`)
6. **Project-memory / state documents** (this file and its siblings, below)
7. **Conversation history** — never authoritative. If something is only "remembered" from a prior conversation and isn't reflected in one of the six sources above, treat it as unverified.

## Read First

In this order, as needed:

1. **This file** — orientation and next action.
2. [PROJECT_STATE.md](PROJECT_STATE.md) — what exists, subsystem by subsystem, and current validation numbers.
3. [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md) — layers, ownership boundaries, dependency diagram.
4. [DECISIONS.md](DECISIONS.md) — approved ADRs, implementation decisions, and open questions. Read before making any architectural choice, to avoid reopening settled questions or silently resolving unsettled ones.
5. [DEVELOPMENT_STATE.md](DEVELOPMENT_STATE.md) — engineering status board: known issues, technical debt, validation baseline, recent git history.

For deep architectural context beyond the index: `docs/runtime.md`, `docs/lifecycle.md`, `docs/event_loop.md`, `docs/runtime_decisions.md`, and the Codex (`codex/`).

## Current State

Telemachus's Core (cognition, memory, governance, identity) is implemented and tested, with a Codex-derived Constitution gating Stage 6 execution. The Runtime has Lifecycle and Session Continuity plus EL-1 Event Loop intake: a bounded in-memory priority queue ticked once per second from `RuntimeLifecycle.wait_for_shutdown_request()`, dispatching to the Core through an opaque invoker. The only production Observation source is the startup Recovery Briefing (RS-1). `PipelineTrace` records Observation provenance. Nothing produces an `ActionRequest`, so every Observation ends as `NO_ACTION`. All of this is committed; HEAD at the time of writing is `00fc421`.

**Before assuming anything about "current state," run `git status` and `git log --oneline -5`.** This file may be stale relative to the actual working tree.

## Current Objective

No open implementation task. The next milestone has not been selected; see [DEVELOPMENT_STATE.md § Next Milestone](DEVELOPMENT_STATE.md#next-milestone).

## What Has Already Been Decided

(Full register: [DECISIONS.md](DECISIONS.md). The essentials, so they aren't reopened:)

- Runtime coordinates the Core; Core never imports Runtime (ADR-001) — mechanically enforced by a test.
- Every startup is a recovery; installation happens exactly once (ADR-002) — structurally enforced by the Lifecycle state machine, not just convention.
- The Runtime persists to a **separate `runtime.db`**, never into `telemachus.db`.
- `BootstrapProtocol`'s five phases run as **one indivisible unit**, invoked by the Runtime but never reordered, split, or duplicated by it.
- First awakening triggers only when **both** the config permits it **and** the Runtime confirms this is a new installation — resolving a real bug where it used to re-trigger on every startup.
- The Event Loop decides *when* reasoning occurs, never what it means; it must not read the Codex, call governance layers, create `ActionRequest`s or execute tools (enforced in part by `tests/test_runtime_boundaries.py`).
- Event Loop stages beyond EL-1 (Signal Processor, Aggregation, dynamic priority, dependency/resource scheduling, deadlines), plugins, and LLM-router integration are **not started** — do not treat them as implemented.
- Synchronous CLI chat stays synchronous and is not routed through the Event Loop.

## What Not To Do

- Do not assume tool protected-capability declarations are verified against `execute()` — they are only type-checked.
- Do not assume an `ActionRequest` producer exists — none does; see PROJECT_STATE.md § Action path.
- Do not assume `llm/router.py` is reachable from the pipeline — it is not.
- Do not assume `cognition/{goals,projects,research}` or `memory/{index,retrieval,versioning}` run in production — they don't; they're tested in isolation only.
- Do not add Event Loop / scheduling / plugin behavior to the Runtime Lifecycle code as a "quick addition" — the Event Loop lives in `runtime/event_loop.py` and is attached through `RuntimeLifecycle.attach_event_loop()`.
- Do not treat the interactive `chat` Ctrl+C behavior change as fixed — it's a known, documented, *unresolved* regression (DECISIONS.md, Q6).
- Do not silently resolve any item listed under DECISIONS.md's "Open Questions" — surface it instead.

## Current Validation

```
pytest:                       1375 passed, 0 failed
coverage:                      88% overall
ruff check .:                  All checks passed
mypy --strict src/telemachus:  Success, 47 files, no issues
```

Full detail: [DEVELOPMENT_STATE.md § Validation Baseline](DEVELOPMENT_STATE.md#validation-baseline).

**These numbers are a snapshot.** If the working tree has changed since this file's "Last Updated" date, re-run the checks before trusting them.

## Next Action

1. Confirm the working tree matches this snapshot (`git status`, `git log --oneline -5`).
2. If it does not, re-derive state from `git log` and the source tree before trusting anything else here.
3. Choose the next milestone from the repository's current state; do not default to the older Event Loop ordering.

## If Something Is Ambiguous

Stop and ask, rather than inventing architecture. In particular: if a specification document and the implementation disagree, or an "Open Question" in DECISIONS.md becomes directly relevant to a task, surface the conflict explicitly rather than picking a resolution silently. This project's own engineering process (see the Runtime Lifecycle implementation) treats that as the correct default.

## Last Updated

2026-10-07

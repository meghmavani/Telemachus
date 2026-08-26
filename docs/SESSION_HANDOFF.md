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

Telemachus's Core (cognition, memory, governance, identity) is fully implemented and tested. A Runtime orchestration layer has just gained its first subsystem — Lifecycle and Session Continuity — implemented, tested, and live-validated, but **sitting uncommitted in the working tree**. The last commit on `main` is `78cd2be`, which predates the Runtime package entirely.

**Before assuming anything about "current state," run `git status` and `git log --oneline -5`.** This file may be stale relative to the actual working tree if a commit, revert, or further changes happened after it was written.

## Current Objective

The Runtime Lifecycle and Session Continuity milestone is **complete**. There is no open implementation task right now. The next objective, once the working tree is committed, is the **Event Loop** (`docs/event_loop.md`) — not started.

## What Has Already Been Decided

(Full register: [DECISIONS.md](DECISIONS.md). The essentials, so they aren't reopened:)

- Runtime coordinates the Core; Core never imports Runtime (ADR-001) — mechanically enforced by a test.
- Every startup is a recovery; installation happens exactly once (ADR-002) — structurally enforced by the Lifecycle state machine, not just convention.
- The Runtime persists to a **separate `runtime.db`**, never into `telemachus.db`.
- `BootstrapProtocol`'s five phases run as **one indivisible unit**, invoked by the Runtime but never reordered, split, or duplicated by it.
- First awakening triggers only when **both** the config permits it **and** the Runtime confirms this is a new installation — resolving a real bug where it used to re-trigger on every startup.
- The Event Loop, Observations, scheduling, plugins, and LLM-router integration are all **deliberately out of scope** for what currently exists — do not treat any of them as started.

## What Not To Do

- Do not assume the Codex markdown files are parsed at runtime — they are not (see PROJECT_STATE.md).
- Do not assume `llm/router.py` is reachable from the pipeline — it is not.
- Do not assume `tools/`, `cognition/{goals,projects,research}`, or `memory/{index,retrieval,versioning}` run in production — they don't; they're tested in isolation only.
- Do not build Event Loop / scheduling / plugin behavior into the Runtime Lifecycle code as a "quick addition" — that boundary was deliberate (see DECISIONS.md, Future Milestones in DEVELOPMENT_STATE.md).
- Do not treat the interactive `chat` Ctrl+C behavior change as fixed — it's a known, documented, *unresolved* regression (DECISIONS.md, Q6).
- Do not silently resolve any item listed under DECISIONS.md's "Open Questions" — surface it instead.

## Current Validation

```
pytest:            1166 passed, 0 failed
coverage:           87% overall; runtime/ package: 96%
ruff check .:        All checks passed
mypy --strict src/:  Success, 43 files, no issues
```

Live-validated this session: `telemachus start` → `RUNNING`; forced-kill + restart → correctly detected `UNCLEAN` → `Recovery → Reconciliation → Running`; clean shutdown → zero WAL/`-shm` sidecars remaining on either database. Full detail: [DEVELOPMENT_STATE.md § Validation Baseline](DEVELOPMENT_STATE.md#validation-baseline).

**These numbers are a snapshot.** If the working tree has changed since this file's "Last Updated" date, re-run the checks before trusting them.

## Next Action

1. Confirm the working tree still matches this snapshot (`git status`, `git diff --stat`).
2. If it matches: review and commit the Runtime Lifecycle milestone + the `[llm]` config fix.
3. If it doesn't match (further work has happened, or the tree was reset): re-derive state from `git log` and the actual source tree before trusting anything else in this file.
4. Only after that: begin scoping the Event Loop milestone, starting from `docs/event_loop.md` and the "Future Milestones" ordering in [DEVELOPMENT_STATE.md](DEVELOPMENT_STATE.md).

## If Something Is Ambiguous

Stop and ask, rather than inventing architecture. In particular: if a specification document and the implementation disagree, or an "Open Question" in DECISIONS.md becomes directly relevant to a task, surface the conflict explicitly rather than picking a resolution silently. This project's own engineering process (see the Runtime Lifecycle implementation) treats that as the correct default.

## Last Updated

2026-08-26

# Telemachus Development State

> Engineering status board. For the "what exists" narrative, see [PROJECT_STATE.md](PROJECT_STATE.md); for "why it exists this way," see [DECISIONS.md](DECISIONS.md).

## Completed Recently

| Item | Where | State |
|---|---|---|
| Config `[llm]` section silently dropped on load (`_resolve_paths()` omitted the `llm=` field) | `src/telemachus/config.py` | Fixed — working tree, uncommitted |
| Runtime Lifecycle and Session Continuity milestone (state machine, `runtime.db`, signal handling, recovery/reconciliation, CLI integration) | `src/telemachus/runtime/`, `main.py`, `wiring.py`, `interaction/cli_chat.py`, `bootstrap.py` | Implemented, tested, validated — working tree, uncommitted |
| Windows path escaping bug in CLI test fixtures (`tests/test_cli_smoke.py` produced invalid TOML on Windows) | `tests/test_cli_smoke.py` | Fixed — **committed** at `78cd2be` |
| Multi-provider LLM router (role-based fallthrough, 429 cooldown, `urllib` transport) | `src/telemachus/llm/router.py` | Implemented, tested in isolation — **committed** at `49c22e5`; **not wired into the pipeline** |
| Composition root (`wiring.py`), fixed both CLI entry points, `MemoryStore.get_stats()`/`.search()` | `src/telemachus/wiring.py`, `memory/store.py` | **Committed** at `2daddce` |

## Current Work

Nothing is currently mid-implementation. The Runtime Lifecycle milestone is complete and fully validated; the only outstanding action is committing it (see [PROJECT_STATE.md § Immediate Next Step](PROJECT_STATE.md#immediate-next-step)).

## Next Milestone

**Event Loop** (`docs/event_loop.md`) — not started. Deliberately deferred until after Lifecycle landed, per the reasoning in the approved Runtime Lifecycle implementation plan: everything the Event Loop needs (Observations, Processing Context, scheduling) assumes a process that already owns its own lifecycle state and can persist across restarts, which this milestone now provides.

## Future Milestones (order established by architecture, not yet scheduled)

1. **Event Loop core** — Signal Processor, Observation Aggregator, immutable Observations, Processing Context (`docs/event_loop.md`, ADR-003/004)
2. **Semantic readiness + scheduling** — Priority Scheduler, Dependency Analyzer, Resource Scheduler, Runtime modes (Normal/High-Load/Critical/Recovery) (ADR-005/007/008)
3. **Plugin system** — plugin manager, isolation boundary, signal-to-Observation translation (ADR-006)
4. **LLM router integration** — wiring `llm/router.py` into the pipeline. Recommended *not* to happen before the pipeline's trace is persisted and stages 1/6 are un-stubbed, since routing nondeterministic model output through a pipeline that can't record what it did undermines the traceability principle in `docs/event_loop.md`.

None of these have implementation dates. This ordering reflects dependency structure in the architecture documents, not a committed schedule.

## Known Issues

| Issue | Severity | Detail |
|---|---|---|
| No single-instance guard | Real gap | Two Runtime processes on one `data_dir` will each read the other's open session as a crash |
| Interactive `chat` Ctrl+C regression | Known, undecided | Runtime's signal handler intercepts SIGINT before it can raise `KeyboardInterrupt`; a blocking `input()` call during chat can no longer be interrupted mid-prompt. Store still closes correctly via `finally`. |
| Codex markdown never parsed | Long-standing, pre-existing | `bootstrap.py` checks file existence for logging only; Constitution/Identity always come from hardcoded Python factories |
| Pipeline stages 1 (Communication) and 6 (Execution) are stubs | Long-standing, pre-existing | Governance runs on every input, but nothing can currently act on its output |
| ~29% of the source tree is unreachable from any entry point | Long-standing, pre-existing | `tools/`, `cognition/{goals,projects,research}`, `memory/{index,retrieval,versioning}`, `llm/router.py` — all implemented and tested in isolation, never constructed in production |
| Real OS Ctrl+C delivery unverified | Environment-specific | Could not be exercised in the harness used for this milestone (no attached console for `GenerateConsoleCtrlEvent`); handler *contract* is fully tested via direct invocation |

## Technical Debt

| Item | Confirmed how |
|---|---|
| `_StageResult.failure` field carries success data in `pipeline.py`, inverting its own name on every read | Present in code (`# following the pipeline convention of using failure for data`) |
| Several `logger.info(msg, {...})` calls in `pipeline.py` pass a dict positionally instead of via `extra=`, silently discarding the data (no `%`-placeholders to consume it) | Present in code |
| `RuntimeLifecycle._force_transition_for_shutdown()` is a documented fallback for one predecessor state (`INSTALLING`) the approved transition table has no legal exit from | Present in code, with an explanatory comment; not a defect, but a deliberate exception to "the table is the single source of truth" |
| Pre-existing unbalanced code fence in `docs/api.md`'s "CLI Commands" section, documenting `--no-bootstrap`/`--skip-phase` flags that don't exist in `main.py` | Confirmed pre-existing via `git diff` before this session's `docs/api.md` edits; not touched |

## Validation Baseline

Most recent, against the current working tree (uncommitted Runtime Lifecycle + config fix included):

```
pytest:            1166 passed, 0 failed
coverage:           87% overall (4567 stmts, 610 missed); runtime/ package: 96%
ruff check .:        All checks passed
mypy --strict src/:  Success, no issues found in 43 source files
```

Live integration validation performed this session (not part of the automated suite):
- `telemachus start` reaches `RUNNING`; all 5 bootstrap phases complete; lifecycle transitions logged in correct order
- Forced-kill + restart correctly detected as `UNCLEAN`; `Recovery → Reconciliation → Running` sequence and briefing display both correct
- Clean shutdown (triggered programmatically, since real signal delivery was unavailable in-harness) leaves zero WAL/`-shm` sidecar files on either database

## Important Recent Git Changes

| Commit | Purpose |
|---|---|
| `78cd2be` (HEAD, committed) | Fix Windows path escaping in a test fixture — unrelated to Runtime |
| `49c22e5` (committed) | Add the LLM router — explicitly noted in its own commit message as "not yet wired into the pipeline" |
| `2daddce` (committed) | Add the composition root (`wiring.py`); fix both CLI entry points, which previously raised `TypeError` on first real use despite 1013 passing tests — the gap unit tests couldn't see because each side of a call was tested against its own assumptions |
| *(uncommitted)* | Runtime Lifecycle milestone + `[llm]` config-drop fix — see [PROJECT_STATE.md](PROJECT_STATE.md) for full scope |

Not listed: earlier Core-only history (`dc64bc9` and before) — see `git log` directly for that if needed; it predates the Runtime work entirely and isn't relevant to picking up from here.

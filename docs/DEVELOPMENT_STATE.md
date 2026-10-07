# Telemachus Development State

> Engineering status board. For the "what exists" narrative, see [PROJECT_STATE.md](PROJECT_STATE.md); for "why it exists this way," see [DECISIONS.md](DECISIONS.md).

## Completed Recently

| Item | Where | State |
|---|---|---|
| Observation provenance in traces (`PipelineTrace.observation`) | `core/types.py`, `pipeline.py` | **Committed** at `00fc421` |
| RS-1: Recovery Briefing → one Observation → Event Loop | `wiring.py`, `main.py` | **Committed** at `63a421d` |
| EL-1: Runtime Tick + Observation Intake (bounded priority queue, tick-driven, opaque Core invoker) | `runtime/event_loop.py`, `runtime/observations.py`, `runtime/lifecycle.py`, `wiring.py`, `main.py` | **Committed** at `3ece69c` |
| Verified Tool capability envelope (`Tool.protected_constraints`, effective impact = action ∪ tool) | `tools/base.py`, `pipeline.py` | **Committed** at `c21bee3` |
| Constitutional action validation in Stage 6 | `core/constitution.py`, `pipeline.py`, `wiring.py` | **Committed** at `e6df65c` |
| Codex Authority Layer (Constitution loaded from the Codex) | `core/codex.py`, `core/constitution.py`, `bootstrap.py` | **Committed** at `4176e81` |
| Codex documentation: Protected Constraints and authority hierarchy | `codex/**` | **Committed** at `7e01a91` |
| Core Execution + Trace Persistence (Stage 6, `PipelineTrace`) | `pipeline.py`, `core/types.py`, `tools/` | **Committed** at `58c3dc1` |
| Runtime Lifecycle and Session Continuity | `runtime/`, `main.py`, `wiring.py`, `interaction/cli_chat.py`, `bootstrap.py` | **Committed** at `a8464e8` |
| Multi-provider LLM router | `llm/router.py` | Committed at `49c22e5`; **not wired into the pipeline** |
| Composition root (`wiring.py`) | `wiring.py`, `memory/store.py` | Committed at `2daddce` |

## Current Work

Nothing is currently mid-implementation. This state-documentation reconciliation is documentation-only.

## Next Milestone

Not selected. Reconnaissance after provenance found no remaining Event Loop stage with a real production input (the Recovery Observation is the only source), and found Observation → `ActionRequest` generation blocked on unresolved authority questions (see [PROJECT_STATE.md § Action path](PROJECT_STATE.md#action-path)). Any next milestone should be chosen from the repository's current state, not from the older ordering below.

## Future Milestones (order established by architecture, not yet scheduled)

1. **Event Loop, remaining stages** — Signal Processor, Observation Aggregator (`docs/event_loop.md`, ADR-003/004). Needs a real signal stream first; EL-1 and RS-1 are done.
2. **Semantic readiness + scheduling** — Priority Scheduler, Dependency Analyzer, Resource Scheduler, Runtime modes (ADR-005/007/008). Dynamic priority and contention need more than one concurrent Observation source.
3. **Plugin system** — plugin manager, isolation boundary, signal-to-Observation translation (ADR-006)
4. **LLM router integration** — wiring `llm/router.py` into the pipeline. The earlier precondition (pipeline trace persisted, Stage 6 un-stubbed) is now met; Stage 1 (Communication) is still a stub.
5. **Observation → `ActionRequest` generation** — needs a design pass first (ownership of `affects` and `human_authorized`, `check_initiative()`, observation domain).

None of these have implementation dates. This ordering reflects dependency structure in the architecture documents, not a committed schedule.

## Known Issues

| Issue | Severity | Detail |
|---|---|---|
| No single-instance guard | Real gap | Two Runtime processes on one `data_dir` will each read the other's open session as a crash |
| Interactive `chat` Ctrl+C regression | Known, undecided | Runtime's signal handler intercepts SIGINT before it can raise `KeyboardInterrupt`; a blocking `input()` call during chat can no longer be interrupted mid-prompt. Store still closes correctly via `finally`. |
| Pipeline stage 1 (Communication) is a stub | Long-standing, pre-existing | Stage 6 (Execution) is implemented, but nothing produces an `ActionRequest`, so nothing acts on governance output |
| No production `ActionRequest` producer; `human_authorized` and `affects` are producer-declared | Open design question | See PROJECT_STATE.md § Action path |
| Tool `protected_constraints` unverified against `execute()` | Accepted residual limitation | Harmless while only `EchoTool` (PASSIVE) exists |
| `AutonomyCharter.check_initiative()` has no production caller and uses substring matching | Open | Must be redesigned before any autonomous initiative |
| Runtime Observations enter the pipeline as user-input-shaped text, under the default `"research"` autonomy domain | Open | Stage 7 stores them as `pipeline_interaction` records |
| Only one production Observation source | By design for now | Startup Recovery Briefing |
| Part of the source tree is unreachable from any entry point | Long-standing, pre-existing | `cognition/{goals,projects,research}`, `memory/{index,retrieval,versioning}`, `llm/router.py` — implemented and tested in isolation, never constructed in production |
| Real OS Ctrl+C delivery unverified | Environment-specific | Could not be exercised in the harness used for this milestone (no attached console for `GenerateConsoleCtrlEvent`); handler *contract* is fully tested via direct invocation |

## Technical Debt

| Item | Confirmed how |
|---|---|
| `_StageResult.failure` field carries success data in `pipeline.py`, inverting its own name on every read | Present in code (`# following the pipeline convention of using failure for data`) |
| Several `logger.info(msg, {...})` calls in `pipeline.py` pass a dict positionally instead of via `extra=`, silently discarding the data (no `%`-placeholders to consume it) | Present in code |
| `RuntimeLifecycle._force_transition_for_shutdown()` is a documented fallback for one predecessor state (`INSTALLING`) the approved transition table has no legal exit from | Present in code, with an explanatory comment; not a defect, but a deliberate exception to "the table is the single source of truth" |
| Pre-existing unbalanced code fence in `docs/api.md`'s "CLI Commands" section, documenting `--no-bootstrap`/`--skip-phase` flags that don't exist in `main.py` | Confirmed pre-existing via `git diff` before this session's `docs/api.md` edits; not touched |

## Validation Baseline

Most recent, at `00fc421` plus documentation-only changes:

```
pytest:                       1375 passed, 0 failed
coverage:                      88% overall (5135 stmts, 620 missed)
ruff check .:                  All checks passed
mypy --strict src/telemachus:  Success, no issues found in 47 source files
```

Live integration validations (Runtime start/shutdown, Event Loop dispatch, Recovery Observation including simulated-crash restart detected as `UNCLEAN`) were run against isolated temp directories at earlier milestones, outside the automated suite. Real OS Ctrl+C delivery remains unverified in the available environment.

## Important Recent Git Changes

| Commit | Purpose |
|---|---|
| `00fc421` (HEAD) | Preserve Observation provenance in `PipelineTrace` |
| `63a421d` | RS-1: feed the Recovery Briefing into the Event Loop |
| `3ece69c` | EL-1: Runtime Event Loop intake |
| `c21bee3` | Verified Tool protected capabilities |
| `e6df65c` | Constitutional action validation |
| `4176e81` | Codex authority loading |
| `7e01a91` | Codex documentation: Protected Constraints and authority |
| `58c3dc1` | Core execution and trace persistence |
| `a8464e8` | Runtime Lifecycle and Session Continuity |

Earlier history (`78cd2be` and before) predates this work; see `git log`.

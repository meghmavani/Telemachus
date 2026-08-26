# Telemachus Decision Register

> Index over architectural decisions. The full rationale for each ADR lives in [docs/runtime_decisions.md](runtime_decisions.md) — this table is a lookup, not a replacement. Implementation-level decisions made while building the Runtime Lifecycle milestone are recorded separately below, since they aren't formal ADRs but are now load-bearing facts about the codebase.

## Approved Decisions (ADRs, `docs/runtime_decisions.md`)

| ID | Decision | Status | Rationale (compressed) | Implemented? |
|---|---|---|---|---|
| ADR-001 | Runtime and Core Separation — Runtime coordinates, Core reasons | Approved | Reasoning should stay deterministic and independent of operational concerns | **Yes** — enforced by `tests/test_runtime_boundaries.py` |
| ADR-002 | Recovery-First Lifecycle — every startup is a recovery; initialization happens once, at installation | Approved | Telemachus is a persistent system, not a repeatedly-launched app | **Yes** — `LifecycleState` transition table structurally forbids skipping `RECOVERY`; `installed_at` is written once and never rewritten |
| ADR-003 | Universal Observation Model — normalize all external signals into one Observation type | Approved | Lets the Core reason independently of external integrations | **No** — no Observation type exists; depends on the Event Loop |
| ADR-004 | Immutable Observations — facts vs. interpretation stay separate | Approved | Reality is immutable; interpretation is adaptive | **No** — depends on the Event Loop |
| ADR-005 | Semantic Readiness — invoke the Core when meaningful, not on a timer | Approved | Avoid unnecessary reasoning cycles | **No** — depends on the Event Loop |
| ADR-006 | Plugin Isolation — plugins translate to Observations, stay isolated from Core | Approved | Stable Core architecture, independent plugin evolution | **No** — no plugin system exists |
| ADR-007 | Resource-Based Concurrency — schedule resource ownership, not threads | Approved | Correctness over raw throughput | **No** — no scheduler exists; the pipeline is single-threaded and synchronous |
| ADR-008 | Adaptive Runtime Regulation — the Runtime regulates conditions, never reasons | Approved | Keep the Event Loop non-cognitive | Partially — the Lifecycle state machine itself performs no reasoning (consistent with the principle), but the regulating behavior it describes (load-based backpressure) doesn't exist yet |
| ADR-009 | Graceful Degradation — aggregate/batch/delay/throttle before discarding | Approved | Resilience over catastrophic failure | Partially — the LLM router's fall-through/cooldown design follows this principle, but the router itself is unwired; Runtime shutdown degrades independently per resource (memory store failing to close doesn't block the rest of shutdown) |
| ADR-010 | Immutable Architectural History — accepted ADRs are never rewritten, only superseded | Approved | Preserve architectural intent over time | Process decision, not a code decision — followed by not editing this file's ADR table content, only adding to it |

## Implementation Decisions (established this session, not formal ADRs)

These are real, load-bearing facts about the current codebase. They resolve ambiguity ADR-001/002 left open at the implementation level.

| Decision | Status | Rationale | Source |
|---|---|---|---|
| Runtime persists to a **separate `runtime.db`**, never into `telemachus.db` | **Existing** (implemented) | Crash detection must not depend on Core memory-store health; a shared file made a leaked handle able to silently reintroduce unclosed-WAL bugs | `src/telemachus/runtime/state_store.py` |
| `BootstrapProtocol` gained an **additive, optional** `first_awakening` parameter (type `bool` or `None`, defaulting to `None`); every existing caller is unaffected | **Existing** (implemented) | The Runtime knows whether an installation is new; the Core config only grants *permission* for first awakening — neither should silently override the other | `src/telemachus/bootstrap.py`; preserves all 44 pre-existing bootstrap tests unmodified |
| First awakening triggers only when **both** are true: this is a new Runtime installation, and `config.bootstrap.first_awakening` is `true` | **Existing** (implemented) | Fixes a real defect: previously, `first_awakening = true` in config caused *every* startup to re-trigger first awakening, forever | `runtime/lifecycle.py: start()` |
| The five bootstrap phases are invoked as **one indivisible unit** inside the Runtime's `RECOVERY` state; the Runtime never reorders, splits, or inspects phase-level data — only `result.success` | **Existing** (implemented) | `codex/bootstrap/BOOTSTRAP_PROTOCOL.md`: "Each stage should complete before the next begins" | `runtime/lifecycle.py: start()` |
| The Lifecycle transition table (`runtime/states.py`) is the **single source of truth** for what state changes are legal; every transition — including inside `shutdown()` — goes through it | **Existing** (implemented) | Makes ADR-002's "no skipping Recovery" guarantee structural, not conventional | Enforced by `InvalidTransitionError`; verified by exhaustive tests over every legal and illegal state pair |
| Signal handlers do the minimum possible work (record + set an `Event` + return); no I/O or database writes occur inside a handler | **Existing** (implemented) | Matches the milestone's explicit requirement and avoids re-entrancy hazards on a second signal | `runtime/signals.py` |

## Open Questions / Unresolved Issues

Not established in repository. Do not silently resolve these — surface them if they become relevant.

| # | Issue | Notes |
|---|---|---|
| Q1 | `docs/lifecycle.md` lists **Installation** and **First Initialization** as separate steps but never defines the difference. The implementation collapsed them into one `INSTALLING` state. | If they're meant to differ, the state model needs a second state. |
| Q2 | ADR-002 permits a user-triggered reset ("unless the user explicitly resets the system") but specifies no reset mechanism. | Currently the de facto reset is deleting `runtime.db` by hand. No command exists for this. |
| Q3 | `FIRST_AWAKENING.md` defines completion as reaching sufficient *understanding*, not as a boolean flag — but no persistence mechanism for "understanding is complete" exists anywhere. | The Runtime resolves only "is this a new installation," not "has awakening concluded." These are treated as genuinely distinct, unresolved concepts. |
| Q4 | **No single-instance guard.** Two Runtime processes sharing one `data_dir` will each treat the other's open session as a crash. | Flagged as the sharpest correctness gap left by this milestone. |
| Q5 | Whether Codex markdown documents are meant to be parsed at runtime, or whether the hardcoded Python factories (`create_default_constitution()`, `create_default_identity()`) are the intended permanent behavior. | `bootstrap.py`'s own comment says "the Codex markdown is the source of truth for the default values," which the code does not currently do. |
| Q6 | Interactive `chat`'s Ctrl+C behavior changed: the Runtime's signal handler intercepts SIGINT before Python's default `KeyboardInterrupt` can, and since the handler never raises, it cannot unblock a synchronous `input()` call the REPL is waiting on. | The memory store still closes correctly (via a `finally` block), but Ctrl+C no longer interrupts an in-progress prompt the way it did before this milestone. Not resolved; documented as a known regression, not fixed, since a proper fix is Event-Loop-shaped work. |
| Q7 | Whether real OS-delivered Ctrl+C reaches the Runtime's installed handler in the actual deployment environment could not be verified in the environment used to build this milestone (isolated to a console-attachment limitation of that specific harness via a minimal, non-Telemachus repro). | The handler *contract* is fully tested (Event set → graceful shutdown completes); only genuine OS signal delivery is unverified here. |

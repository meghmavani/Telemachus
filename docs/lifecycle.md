# Runtime Lifecycle

## Purpose

This document defines the lifecycle of the Telemachus Runtime from installation through normal operation, recovery, and shutdown.

Where `runtime.md` defines the Runtime's responsibilities and philosophy, this document specifies how the Runtime behaves throughout its lifetime.

The lifecycle is designed around one core principle:

> Telemachus is a persistent system. Every execution is a continuation of the same long-lived instance rather than a new application launch.

---

# Lifecycle Overview

The Runtime progresses through a series of well-defined operational states.

```text
Installation
      │
      ▼
First Initialization
      │
      ▼
Booting
      │
      ▼
Recovery
      │
      ▼
Reconciliation
      │
      ▼
Running
 ┌────┴────┐
 │         │
 ▼         ▼
Active    Idle
 │         │
 └────┬────┘
      ▼
Shutdown
```

Unexpected failures or extended offline periods always return to the Recovery phase before normal operation resumes.

---

# Installation

Installation is the only time Telemachus performs true initialization.

During installation the Runtime creates the persistent environment required for future operation.

Typical responsibilities include:

- Creating the Runtime identity
- Initializing persistent storage
- Creating configuration files
- Preparing internal directories
- Initializing security material
- Registering required services
- Performing first-time validation

Once installation completes, initialization should never occur again unless the user explicitly resets the system.

Every future startup is treated as recovery.

---

# Boot Process

When the operating system starts, Telemachus should launch automatically.

Availability is considered part of its identity.

The user should not need to manually prepare or initialize the Runtime before interacting with it.

The boot process is intentionally lightweight.

---

## Essential Initialization

Only Runtime-critical components are initialized immediately.

Examples include:

- Configuration
- Identity
- Governance
- Memory infrastructure
- Scheduler
- Runtime services
- Event routing
- Plugin manager

These components establish a functioning Runtime capable of serving requests.

---

## Lazy Initialization

Resource-intensive components should be initialized only when first required.

Examples include:

- Large language models
- Vision models
- Speech models
- Heavy reasoning engines
- Rarely used plugins

This minimizes startup latency while preserving full capability.

---

# Recovery

Recovery occurs after every startup.

This includes:

- Normal shutdowns
- Unexpected crashes
- Operating system restarts
- Power failures
- Sleep or hibernation
- Extended offline periods

Recovery is not considered an exceptional state.

It is a normal phase of the Runtime lifecycle.

---

## Recovery Responsibilities

Recovery restores operational continuity by reconstructing Runtime state.

Typical restoration includes:

- Identity
- Memory indexes
- Active projects
- Long-term goals
- Pending reminders
- Scheduler state
- Runtime configuration
- Plugin state (where supported)
- Interrupted operations

Recovery should restore the Runtime to the most recent safe checkpoint.

---

# Reconciliation

Recovery restores the previous state.

Reconciliation aligns that restored state with the current reality.

This distinction is intentional.

Instead of replaying every event that occurred while the Runtime was offline, Telemachus determines what information remains relevant now.

Typical reconciliation tasks include:

- Removing expired reminders
- Detecting newly available deadlines
- Resuming ongoing projects
- Identifying outdated tasks
- Synchronizing plugin state
- Rebuilding scheduler queues
- Detecting external changes
- Recording missed scheduled activities

The objective is not historical replay.

The objective is operational correctness.

---

# Running

Once recovery and reconciliation complete, the Runtime enters normal operation.

Running consists of two behavioral modes.

---

## Active

The Runtime is actively processing work.

Examples include:

- Responding to the user
- Executing scheduled jobs
- Coordinating plugins
- Performing reasoning
- Processing observations

Active periods may temporarily consume significant computational resources.

---

## Idle

Idle does not mean inactive.

During idle periods the Runtime remains fully available while minimizing resource usage.

Responsibilities include:

- Listening for events
- Maintaining scheduler timers
- Monitoring plugin activity
- Waiting for user interaction

Heavy reasoning should not occur during idle periods unless meaningful events require it.

---

# Offline Periods

The Runtime may become unavailable because of:

- Operating system shutdown
- Sleep
- Hibernate
- Power loss
- Device restart

During offline periods no processing occurs.

When execution resumes, the Runtime always performs Recovery followed by Reconciliation before returning to Running.

Offline duration alone does not determine Runtime behavior.

Instead, behavior is determined by the amount of meaningful change that accumulated while Telemachus was unavailable.

---

# Failure Handling

Failures should degrade functionality rather than terminate the Runtime whenever possible.

If an individual subsystem fails:

1. Continue operating with reduced functionality.
2. Isolate the failure.
3. Attempt safe self-repair when supported.
4. Protect persistent user state.
5. Record diagnostic information.
6. Inform the user only if the failure affects them.

Failures should never silently corrupt Runtime state.

---

# Persistence Strategy

The Runtime uses hybrid persistence.

State should not be written exclusively during shutdown.

Likewise, every minor change should not immediately trigger disk writes.

Instead:

- Persist meaningful state changes incrementally.
- Create periodic Runtime checkpoints.
- Perform a final checkpoint during graceful shutdown.

This strategy minimizes data loss while avoiding unnecessary storage overhead.

---

# Shutdown

## Graceful Shutdown

During normal shutdown the Runtime should:

- Complete active operations where practical
- Persist outstanding state
- Flush event queues
- Save Runtime checkpoints
- Disconnect plugins cleanly
- Release system resources

A successful graceful shutdown requires no acknowledgement on the next startup.

---

## Unexpected Shutdown

Unexpected shutdowns include:

- Process termination
- Operating system crashes
- Power failures
- Forced termination

These situations bypass the normal shutdown sequence.

The next startup should acknowledge that recovery occurred.

Example:

> "I recovered from an unexpected shutdown. Your state has been restored and reconciliation is complete."

This acknowledgement improves transparency without unnecessarily interrupting the user.

---

# User Briefings

Recovery information should be presented only when it provides value.

The Runtime should avoid interrupting the user immediately after startup.

Instead, recovery summaries should normally be delivered during the first natural interaction.

For example:

> User: "Good morning."

> Telemachus: "Good morning. While you were away, two reminders expired, one project deadline passed, and your GitHub repositories received new commits. Everything else has been reconciled."

Immediate notifications should be reserved for genuinely urgent situations.

Examples include:

- An imminent meeting
- A critical deadline
- A failed recovery requiring user intervention

---

# Long Absence

A long absence is defined semantically rather than by elapsed time.

It represents any offline period during which meaningful changes accumulated.

Examples include:

- Deadlines passed
- Reminders expired
- Projects changed
- External systems updated
- Scheduled activities were missed

The Runtime should summarize these changes rather than replay every missed event.

The objective is to restore situational awareness, not reconstruct history.

---

# Lifecycle Principles

The Runtime lifecycle follows several guiding principles.

- Installation occurs exactly once.
- Every future startup is a recovery.
- Recovery restores continuity.
- Reconciliation restores correctness.
- Idle should consume minimal resources.
- Failures should degrade gracefully.
- Persistence should balance durability and efficiency.
- User interruptions should always provide meaningful value.
- Continuity should be preserved across sessions whenever possible.

---

# Relationship to Other Documents

This document defines **when** Runtime phases occur.

Related documents define the remaining aspects of Runtime behavior:

- `runtime.md` — Runtime philosophy and responsibilities
- `event_loop.md` — Event processing and scheduling
- `runtime_decisions.md` — Architectural decision records and rationale
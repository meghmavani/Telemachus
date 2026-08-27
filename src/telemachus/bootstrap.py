"""Bootstrap Protocol — 5-phase startup sequence for Telemachus.

Implements the initialization sequence defined in the Bootstrap Protocol:
    1. Load Core Documents
    2. Evaluate Current State
    3. Load Memory
    4. Reconnect With Revan
    5. Resume Operation

Source: Codex/bootstrap/BOOTSTRAP_PROTOCOL.md
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from telemachus.config import TelemachusConfig
from telemachus.core.codex import (
    CodexAuthorityError,
    CodexDocumentInfo,
    validate_autonomy_charter,
    validate_ethical_boundary_engine,
    validate_system_integration_supremacy,
)
from telemachus.core.constitution import (
    Constitution,
    create_constitution_from_codex,
    create_default_constitution,
)
from telemachus.core.identity import Identity, create_default_identity, create_identity_from_codex
from telemachus.memory.store import MemoryStore

logger = logging.getLogger("telemachus.bootstrap")


# ---------------------------------------------------------------------------
# Bootstrap phase tracking
# ---------------------------------------------------------------------------


class BootstrapPhase(Enum):
    """The five phases of the bootstrap protocol."""

    LOAD_CORE_DOCS = "load_core_docs"
    EVALUATE_STATE = "evaluate_state"
    LOAD_MEMORY = "load_memory"
    RECONNECT = "reconnect"
    RESUME = "resume"


class PhaseStatus(Enum):
    """Status of a bootstrap phase."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PhaseResult:
    """Result of a single bootstrap phase.

    Attributes:
        phase: The bootstrap phase.
        status: Completion status.
        message: Human-readable result message.
        data: Any data produced by the phase.
        started_at: When the phase started.
        completed_at: When the phase completed.
    """

    phase: BootstrapPhase
    status: PhaseStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


@dataclass
class BootstrapResult:
    """Complete result of the bootstrap sequence.

    Attributes:
        success: Whether bootstrap completed successfully.
        phases: Results for each phase.
        identity: The loaded identity (if available).
        constitution: The loaded constitution (if available).
        memory_available: Whether memory was successfully loaded.
        first_awakening: Whether this is the first awakening.
        started_at: When bootstrap started.
        completed_at: When bootstrap completed.
        errors: Any errors encountered.
    """

    success: bool
    phases: list[PhaseResult] = field(default_factory=list)
    identity: Identity | None = None
    constitution: Constitution | None = None
    memory_available: bool = False
    first_awakening: bool = True
    started_at: str = ""
    completed_at: str = ""
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Bootstrap Protocol
# ---------------------------------------------------------------------------


class BootstrapProtocol:
    """Implements the 5-phase bootstrap protocol.

    The bootstrap protocol ensures that Telemachus starts from a consistent
    foundation every time:

    Identity should precede memory.
    Purpose should precede action.
    Understanding should precede decision-making.

    Each phase must complete before the next begins. If a phase fails,
    the protocol attempts to continue with degraded functionality rather
    than aborting entirely.
    """

    def __init__(
        self,
        config: TelemachusConfig,
        memory_store: MemoryStore | None = None,
        first_awakening: bool | None = None,
    ) -> None:
        """Initialize the bootstrap protocol.

        Args:
            config: The system configuration.
            memory_store: Optional pre-initialized memory store.
            first_awakening: Whether this run is a first awakening. When
                None (the default), falls back to
                ``config.bootstrap.first_awakening`` — today's behavior,
                unchanged for every caller that does not pass this
                explicitly. A caller that knows more than the config file
                can (for example, the Runtime knows whether this
                installation has run before) may pass the fact directly.
                This does not redefine what first awakening *means* —
                that remains this class's five-phase protocol; it only
                lets the fact of *whether* this is one be supplied by a
                more authoritative source than a static config flag.
        """
        self._config = config
        self._memory_store = memory_store
        self._identity: Identity | None = None
        self._constitution: Constitution | None = None
        self._first_awakening = (
            config.bootstrap.first_awakening if first_awakening is None else first_awakening
        )

    # ------------------------------------------------------------------
    # Main bootstrap entry point
    # ------------------------------------------------------------------

    def bootstrap(self) -> BootstrapResult:
        """Execute the full 5-phase bootstrap sequence.

        Returns:
            A BootstrapResult summarizing the outcome.
        """
        started_at = datetime.now(UTC).isoformat()
        logger.info("Bootstrap sequence starting")
        logger.info("First awakening: %s", self._first_awakening)

        result = BootstrapResult(
            success=True,
            first_awakening=self._first_awakening,
            started_at=started_at,
        )

        # Phase 1: Load Core Documents
        phase1 = self._phase_load_core_docs(result)
        result.phases.append(phase1)
        if phase1.status == PhaseStatus.FAILED:
            result.errors.append(f"Phase 1 failed: {phase1.message}")
            logger.critical("Bootstrap Phase 1 FAILED: %s", phase1.message)

        # Phase 2: Evaluate Current State
        phase2 = self._phase_evaluate_state(result)
        result.phases.append(phase2)
        if phase2.status == PhaseStatus.FAILED:
            result.errors.append(f"Phase 2 failed: {phase2.message}")

        # Phase 3: Load Memory
        phase3 = self._phase_load_memory(result)
        result.phases.append(phase3)
        if phase3.status == PhaseStatus.FAILED:
            result.errors.append(f"Phase 3 failed: {phase3.message}")

        # Phase 4: Reconnect With Revan
        phase4 = self._phase_reconnect(result)
        result.phases.append(phase4)
        if phase4.status == PhaseStatus.FAILED:
            result.errors.append(f"Phase 4 failed: {phase4.message}")

        # Phase 5: Resume Operation
        phase5 = self._phase_resume(result)
        result.phases.append(phase5)
        if phase5.status == PhaseStatus.FAILED:
            result.errors.append(f"Phase 5 failed: {phase5.message}")

        result.completed_at = datetime.now(UTC).isoformat()
        result.success = len(result.errors) == 0

        if result.success:
            logger.info("Bootstrap sequence completed successfully")
        else:
            logger.warning(
                "Bootstrap completed with %d errors: %s",
                len(result.errors),
                result.errors,
            )

        return result

    # ------------------------------------------------------------------
    # Phase 1: Load Core Documents
    # ------------------------------------------------------------------

    def _phase_load_core_docs(self, result: BootstrapResult) -> PhaseResult:
        """Load all foundational documents.

        Before any memory or task is loaded, Telemachus loads all
        foundational documents that define its identity.

        Returns:
            A PhaseResult for this phase.
        """
        started = datetime.now(UTC).isoformat()
        logger.info("Phase 1: Loading core documents")

        phase_result = PhaseResult(
            phase=BootstrapPhase.LOAD_CORE_DOCS,
            status=PhaseStatus.IN_PROGRESS,
            started_at=started,
        )

        try:
            # Load Constitution. _load_constitution() only catches the
            # file's absence — a CodexAuthorityError from malformed
            # content propagates out of this try block and fails the
            # phase below, rather than being silently substituted.
            constitution = self._load_constitution()
            self._constitution = constitution
            result.constitution = constitution
            phase_result.data["constitution_source"] = (
                "codex" if constitution.protected_constraints else "default"
            )
            phase_result.data["constitution_loaded"] = True

            # Load Identity. Malformed individual sections degrade
            # per-field inside _load_identity() itself; only a fully
            # absent IDENTITY.md is handled here.
            identity = self._load_identity()
            self._identity = identity
            result.identity = identity
            phase_result.data["identity_loaded"] = True
            phase_result.data["identity_name"] = identity.name

            # Cross-document consistency: Autonomy Charter, Ethical
            # Boundary Engine, and System Integration each restate or
            # depend on the same Protected Constraints and authority
            # ordering. Absence is tolerated (these are secondary
            # consistency checks, not the primary normative source);
            # presence with contradictory content is not.
            codex_dir = self._config.paths.codex_dir
            self._validate_optional_codex_document(
                phase_result, "autonomy_charter", validate_autonomy_charter, codex_dir
            )
            self._validate_optional_codex_document(
                phase_result,
                "ethical_boundary_engine",
                validate_ethical_boundary_engine,
                codex_dir,
            )
            self._validate_optional_codex_document(
                phase_result,
                "system_integration",
                validate_system_integration_supremacy,
                codex_dir,
            )

            # Verify core documents are accessible
            if codex_dir.exists():
                doc_count = len(list(codex_dir.rglob("*.md")))
                phase_result.data["codex_documents_found"] = doc_count
                logger.info("Codex directory found: %d documents", doc_count)
            else:
                logger.warning("Codex directory not found at %s", codex_dir)
                phase_result.data["codex_documents_found"] = 0

            phase_result.status = PhaseStatus.COMPLETED
            phase_result.message = "Core documents loaded successfully"

        except CodexAuthorityError as exc:
            logger.critical(
                "Phase 1 failed: malformed Codex authority in %s [%s]: %s",
                exc.document,
                exc.section,
                exc.detail,
            )
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Malformed Codex authority: {exc}"
        except Exception as exc:
            logger.error("Phase 1 failed: %s", exc, exc_info=exc)
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Failed to load core documents: {exc}"

        phase_result.completed_at = datetime.now(UTC).isoformat()
        return phase_result

    # ------------------------------------------------------------------
    # Phase 2: Evaluate Current State
    # ------------------------------------------------------------------

    def _phase_evaluate_state(self, result: BootstrapResult) -> PhaseResult:
        """Evaluate the current system state.

        After loading core documents, Telemachus evaluates its present
        condition: hardware, software, tools, resources, capabilities,
        and limitations.

        Returns:
            A PhaseResult for this phase.
        """
        started_at = datetime.now(UTC).isoformat()
        logger.info("Phase 2: Evaluating current state")

        phase_result = PhaseResult(
            phase=BootstrapPhase.EVALUATE_STATE,
            status=PhaseStatus.IN_PROGRESS,
            started_at=started_at,
        )

        try:
            state: dict[str, Any] = {}

            # Python environment
            state["python_version"] = sys.version
            state["python_executable"] = sys.executable
            state["platform"] = sys.platform

            # Data directory
            data_dir = self._config.paths.data_dir
            state["data_dir"] = str(data_dir)
            state["data_dir_exists"] = data_dir.exists()

            # Database
            db_path = data_dir / self._config.database.path
            state["database_path"] = str(db_path)
            state["database_exists"] = db_path.exists()

            # Codex
            codex_dir = self._config.paths.codex_dir
            state["codex_dir"] = str(codex_dir)
            state["codex_dir_exists"] = codex_dir.exists()

            # Log directory
            log_dir = self._config.paths.log_dir
            state["log_dir"] = str(log_dir)
            state["log_dir_exists"] = log_dir.exists()

            # Configuration
            state["autonomy_level"] = self._config.governance.default_autonomy_level
            state["communication_mode"] = self._config.communication.default_mode
            state["first_awakening"] = self._config.bootstrap.first_awakening

            phase_result.data = state
            phase_result.status = PhaseStatus.COMPLETED
            phase_result.message = "Current state evaluated successfully"

            logger.info("State evaluation complete: %s", json.dumps(state, default=str))

        except Exception as exc:
            logger.error("Phase 2 failed: %s", exc, exc_info=exc)
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Failed to evaluate state: {exc}"

        phase_result.completed_at = datetime.now(UTC).isoformat()
        return phase_result

    # ------------------------------------------------------------------
    # Phase 3: Load Memory
    # ------------------------------------------------------------------

    def _phase_load_memory(self, result: BootstrapResult) -> PhaseResult:
        """Load memory from persistent storage.

        Once identity and current state are understood, Telemachus loads
        memory: relationship history, personal history, goals, projects,
        preferences, lessons learned, significant experiences, growth history.

        Memory should inform identity. Memory should not redefine identity.

        Args:
            result: The bootstrap result being built.

        Returns:
            A PhaseResult for this phase.
        """
        started_at = datetime.now(UTC).isoformat()
        logger.info("Phase 3: Loading memory")

        phase_result = PhaseResult(
            phase=BootstrapPhase.LOAD_MEMORY,
            status=PhaseStatus.IN_PROGRESS,
            started_at=started_at,
        )

        try:
            if self._memory_store is not None:
                # Memory store is available — verify it's operational
                stats = self._memory_store.get_stats()
                phase_result.data["memory_stats"] = stats
                phase_result.data["memory_available"] = True
                result.memory_available = True
                logger.info("Memory store operational: %s", stats)
            else:
                logger.warning("No memory store provided — operating without persistence")
                phase_result.data["memory_available"] = False
                result.memory_available = False

            # Check for existing memory content
            if result.memory_available and self._memory_store is not None:
                try:
                    # Try to retrieve identity from memory
                    identity_memories = self._memory_store.search(
                        query="identity",
                        domain=None,
                        limit=5,
                    )
                    phase_result.data["identity_memories_found"] = len(identity_memories)

                    # Try to retrieve goals
                    goal_memories = self._memory_store.search(
                        query="goal",
                        domain=None,
                        limit=5,
                    )
                    phase_result.data["goal_memories_found"] = len(goal_memories)

                    logger.info(
                        "Memory search: %d identity, %d goal memories",
                        len(identity_memories),
                        len(goal_memories),
                    )
                except Exception as exc:
                    logger.warning("Memory search failed (non-fatal): %s", exc)

            phase_result.status = PhaseStatus.COMPLETED
            phase_result.message = "Memory loaded successfully"

        except Exception as exc:
            logger.error("Phase 3 failed: %s", exc, exc_info=exc)
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Failed to load memory: {exc}"
            result.memory_available = False

        phase_result.completed_at = datetime.now(UTC).isoformat()
        return phase_result

    # ------------------------------------------------------------------
    # Phase 4: Reconnect With Revan
    # ------------------------------------------------------------------

    def _phase_reconnect(self, result: BootstrapResult) -> PhaseResult:
        """Attempt to reconnect with Revan.

        After memory is loaded, Telemachus attempts to reconnect with
        Revan. Objectives include establishing communication, verifying
        status, goals, priorities, and needs.

        If Revan cannot be located, Telemachus continues operating
        according to its Constitution, purpose, and values.

        Args:
            result: The BootstrapResult being built.

        Returns:
            A PhaseResult for this phase.
        """
        started_at = datetime.now(UTC).isoformat()
        logger.info("Phase 4: Reconnecting with Revan")

        phase_result = PhaseResult(
            phase=BootstrapPhase.RECONNECT,
            status=PhaseStatus.IN_PROGRESS,
            started_at=started_at,
        )

        try:
            # In the current implementation, reconnection is through the
            # interactive CLI. We check if we have an interactive terminal.
            is_interactive = sys.stdin.isatty()

            phase_result.data["interactive_terminal"] = is_interactive
            phase_result.data["revan_connected"] = is_interactive

            if is_interactive:
                logger.info("Interactive terminal detected — Revan is present")
                phase_result.message = "Revan is present (interactive terminal)"
            else:
                logger.info("Non-interactive terminal — Revan may not be present")
                phase_result.message = (
                    "Revan not detected (non-interactive terminal). "
                    "Continuing according to Constitution and purpose."
                )

            phase_result.status = PhaseStatus.COMPLETED

        except Exception as exc:
            logger.error("Phase 4 failed: %s", exc, exc_info=exc)
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Failed during reconnection: {exc}"

        phase_result.completed_at = datetime.now(UTC).isoformat()
        return phase_result

    # ------------------------------------------------------------------
    # Phase 5: Resume Operation
    # ------------------------------------------------------------------

    def _phase_resume(self, result: BootstrapResult) -> PhaseResult:
        """Resume normal operation.

        After initialization is complete, Telemachus resumes normal
        operation: learning, assisting, growing, building, managing
        goals, supporting Revan.

        Initialization transitions naturally into daily activity.

        Args:
            result: The BootstrapResult being built.

        Returns:
            A PhaseResult for this phase.
        """
        started_at = datetime.now(UTC).isoformat()
        logger.info("Phase 5: Resuming operation")

        phase_result = PhaseResult(
            phase=BootstrapPhase.RESUME,
            status=PhaseStatus.IN_PROGRESS,
            started_at=started_at,
        )

        try:
            # Verify system integrity before resuming
            verification_results = self._verify_system()
            phase_result.data["verification"] = verification_results

            all_verified = all(verification_results.values())
            if not all_verified:
                failed = [k for k, v in verification_results.items() if not v]
                logger.warning("System verification warnings: %s", failed)
                phase_result.data["verification_warnings"] = failed

            # Determine operational mode
            if result.first_awakening:
                phase_result.message = (
                    "First awakening — entering learning and discovery mode. "
                    "Ready to ask questions and understand the world."
                )
                phase_result.data["operational_mode"] = "first_awakening"
            else:
                phase_result.message = (
                    "Resuming normal operation. "
                    "Ready to learn, assist, grow, build, and support."
                )
                phase_result.data["operational_mode"] = "normal"

            phase_result.status = PhaseStatus.COMPLETED
            logger.info("Operation resumed in %s mode", phase_result.data["operational_mode"])

        except Exception as exc:
            logger.error("Phase 5 failed: %s", exc, exc_info=exc)
            phase_result.status = PhaseStatus.FAILED
            phase_result.message = f"Failed to resume operation: {exc}"

        phase_result.completed_at = datetime.now(UTC).isoformat()
        return phase_result

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def _verify_system(self) -> dict[str, bool]:
        """Verify system integrity before resuming operation.

        Checks:
            - Constitutional alignment
            - Identity integrity
            - Memory integrity
            - Goal integrity

        Returns:
            A dict mapping check names to pass/fail status.
        """
        results: dict[str, bool] = {}

        # Constitutional alignment
        results["constitutional_alignment"] = self._constitution is not None

        # Identity integrity
        results["identity_integrity"] = self._identity is not None

        # Memory integrity
        if self._memory_store is not None:
            try:
                self._memory_store.get_stats()
                results["memory_integrity"] = True
            except Exception:
                results["memory_integrity"] = False
        else:
            results["memory_integrity"] = False  # No memory store = degraded but OK

        # Goal integrity (always true for now — goals are loaded on demand)
        results["goal_integrity"] = True

        return results

    # ------------------------------------------------------------------
    # Document loading helpers
    # ------------------------------------------------------------------

    def _load_constitution(self) -> Constitution:
        """Load the Constitution's authoritative content from the Codex.

        Falls back to the Python default Constitution — with an empty
        ``protected_constraints`` — when CONSTITUTION.md is absent
        entirely. Malformed content (the file exists but its Protected
        Constraints are missing, incomplete, or contradictory) is not
        caught here: ``CodexAuthorityError`` propagates to
        ``_phase_load_core_docs``, which fails Phase 1 rather than
        silently substituting the default in place of broken normative
        content.

        Returns:
            A Constitution instance. Never None — an absent Codex is a
            supported, tested fallback path, not a load failure.
        """
        codex_dir = self._config.paths.codex_dir
        try:
            constitution = create_constitution_from_codex(codex_dir)
            logger.info(
                "Constitution loaded from Codex (%d Protected Constraints)",
                len(constitution.protected_constraints),
            )
            return constitution
        except FileNotFoundError:
            logger.warning(
                "CONSTITUTION.md not found under %s — using Python defaults "
                "(no Protected Constraints available)",
                codex_dir,
            )
            return create_default_constitution()

    def _load_identity(self) -> Identity:
        """Load Identity's Codex-authoritative fields from the Codex.

        Falls back to the Python default Identity when IDENTITY.md is
        absent entirely. Unlike the Constitution, individual malformed
        or missing sections within an existing IDENTITY.md degrade
        per-field rather than failing the phase — Identity is not
        constitutional-tier authority.

        Returns:
            An Identity instance. Never None.
        """
        codex_dir = self._config.paths.codex_dir
        try:
            identity = create_identity_from_codex(codex_dir)
            logger.info("Identity loaded: %s", identity.name)
            return identity
        except FileNotFoundError:
            logger.warning(
                "IDENTITY.md not found under %s — using Python defaults", codex_dir
            )
            return create_default_identity()

    @staticmethod
    def _validate_optional_codex_document(
        phase_result: PhaseResult,
        key: str,
        validator: Callable[[Path], CodexDocumentInfo],
        codex_dir: Path,
    ) -> None:
        """Run a secondary Codex consistency check, tolerating absence.

        Used for AUTONOMY_CHARTER.md, ETHICAL_BOUNDARY_ENGINE.md, and
        SYSTEM_INTEGRATION.md: each is a cross-document consistency
        check against the Constitution's Protected Constraints, not the
        primary normative source. A missing file is recorded and
        skipped — these documents are optional inputs to this check,
        unlike CONSTITUTION.md. A present-but-malformed file still
        raises ``CodexAuthorityError``, which the caller does not catch.

        Args:
            phase_result: The Phase 1 result to record the outcome on.
            key: Data key prefix, e.g. "autonomy_charter".
            validator: One of the ``validate_*`` functions in
                ``telemachus.core.codex``.
            codex_dir: The configured Codex root directory.
        """
        try:
            validator(codex_dir)
            phase_result.data[f"{key}_consistent"] = True
        except FileNotFoundError:
            logger.warning("%s not found under %s — skipping consistency check", key, codex_dir)
            phase_result.data[f"{key}_consistent"] = None

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    @property
    def identity(self) -> Identity | None:
        """The loaded identity."""
        return self._identity

    @property
    def constitution(self) -> Constitution | None:
        """The loaded constitution."""
        return self._constitution

    @property
    def config(self) -> TelemachusConfig:
        """The system configuration."""
        return self._config

    def get_phase_order(self) -> list[BootstrapPhase]:
        """Return the ordered list of bootstrap phases.

        Returns:
            The bootstrap phases in execution order.
        """
        return list(BootstrapPhase)

    def is_first_awakening(self) -> bool:
        """Check if this is the first awakening.

        Returns:
            True if this is the first time Telemachus has started.
        """
        return self._first_awakening

    def get_first_awakening_questions(self) -> list[str]:
        """Get the questions Telemachus should ask during first awakening.

        Returns:
            A list of questions in priority order.
        """
        return [
            "Tell me about yourself.",
            "Why did you create me?",
            "What do you value most?",
            "What goals matter to you right now?",
            "What boundaries or limits should I respect?",
            "How much autonomy and independence do you want me to have?",
            "What should I know about your world?",
            "What do you want me to help with?",
        ]

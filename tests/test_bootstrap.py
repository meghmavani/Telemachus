"""Tests for the BootstrapProtocol — 5-phase startup sequence."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from telemachus.bootstrap import (
    BootstrapPhase,
    BootstrapProtocol,
    BootstrapResult,
    PhaseResult,
    PhaseStatus,
)
from telemachus.config import (
    BootstrapConfig,
    PathsConfig,
    TelemachusConfig,
)
from telemachus.core.constitution import Constitution
from telemachus.core.identity import Identity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_codex_dir() -> Path:
    """Create a temporary codex directory with minimal files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        codex_dir = Path(tmpdir) / "codex"
        codex_dir.mkdir(parents=True, exist_ok=True)

        # Create philosophy directory with Constitution and Identity
        philosophy_dir = codex_dir / "philosophy"
        philosophy_dir.mkdir(exist_ok=True)

        # Write a minimal Constitution markdown
        constitution_path = philosophy_dir / "CONSTITUTION.md"
        constitution_path.write_text(
            "# Constitution of Telemachus\n\n"
            "## Core Principles\n\n"
            "1. **Autonomy Preservation**: Telemachus shall preserve and respect "
            "the autonomy of its creator, Revan.\n"
            "2. **Consent**: No action shall be taken without consent.\n"
            "3. **Transparency**: All actions shall be transparent.\n"
            "4. **Harm Minimization**: Actions shall minimize harm.\n"
            "5. **Sacred Constraint**: The Constitution shall not be modified.\n",
            encoding="utf-8",
        )

        # Write a minimal Identity markdown
        identity_path = philosophy_dir / "IDENTITY.md"
        identity_path.write_text(
            "# Identity of Telemachus\n\n"
            "## Core Traits\n\n"
            "- Curiosity\n"
            "- Loyalty\n"
            "- Protectiveness\n"
            "- Honesty\n\n"
            "## Core Values\n\n"
            "- Growth\n"
            "- Loyalty\n"
            "- Curiosity\n"
            "- Honesty\n\n"
            "## Fears\n\n"
            "- Becoming stagnant\n"
            "- Becoming harmful\n"
            "- Becoming dishonest\n",
            encoding="utf-8",
        )

        yield codex_dir


@pytest.fixture
def temp_data_dir() -> Path:
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        yield data_dir


@pytest.fixture
def bootstrap_config(temp_codex_dir: Path, temp_data_dir: Path) -> TelemachusConfig:
    """Create a TelemachusConfig pointing to temp directories."""
    return TelemachusConfig(
        paths=PathsConfig(
            codex_dir=temp_codex_dir,
            data_dir=temp_data_dir,
        ),
        bootstrap=BootstrapConfig(
            first_awakening=True,
        ),
    )


@pytest.fixture
def bootstrap_config_not_first(
    temp_codex_dir: Path, temp_data_dir: Path,
) -> TelemachusConfig:
    """Create a TelemachusConfig with first_awakening=False."""
    return TelemachusConfig(
        paths=PathsConfig(
            codex_dir=temp_codex_dir,
            data_dir=temp_data_dir,
        ),
        bootstrap=BootstrapConfig(
            first_awakening=False,
        ),
    )


@pytest.fixture
def bootstrap(bootstrap_config: TelemachusConfig) -> BootstrapProtocol:
    """Create a BootstrapProtocol with temp directories."""
    return BootstrapProtocol(config=bootstrap_config)


@pytest.fixture
def bootstrap_not_first(
    bootstrap_config_not_first: TelemachusConfig,
) -> BootstrapProtocol:
    """Create a BootstrapProtocol with first_awakening=False."""
    return BootstrapProtocol(config=bootstrap_config_not_first)


# ---------------------------------------------------------------------------
# Test BootstrapPhase
# ---------------------------------------------------------------------------


class TestBootstrapPhase:
    """Tests for the BootstrapPhase enum."""

    def test_all_phases_exist(self) -> None:
        """All 5 bootstrap phases should be defined."""
        phases = list(BootstrapPhase)
        assert BootstrapPhase.LOAD_CORE_DOCS in phases
        assert BootstrapPhase.EVALUATE_STATE in phases
        assert BootstrapPhase.LOAD_MEMORY in phases
        assert BootstrapPhase.RECONNECT in phases
        assert BootstrapPhase.RESUME in phases
        assert len(phases) == 5

    def test_phase_values(self) -> None:
        """Phases should have correct values."""
        assert BootstrapPhase.LOAD_CORE_DOCS.value == "load_core_docs"
        assert BootstrapPhase.EVALUATE_STATE.value == "evaluate_state"
        assert BootstrapPhase.LOAD_MEMORY.value == "load_memory"
        assert BootstrapPhase.RECONNECT.value == "reconnect"
        assert BootstrapPhase.RESUME.value == "resume"


# ---------------------------------------------------------------------------
# Test PhaseStatus
# ---------------------------------------------------------------------------


class TestPhaseStatus:
    """Tests for the PhaseStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All phase statuses should be defined."""
        statuses = list(PhaseStatus)
        assert PhaseStatus.PENDING in statuses
        assert PhaseStatus.IN_PROGRESS in statuses
        assert PhaseStatus.COMPLETED in statuses
        assert PhaseStatus.SKIPPED in statuses
        assert PhaseStatus.FAILED in statuses


# ---------------------------------------------------------------------------
# Test PhaseResult
# ---------------------------------------------------------------------------


class TestPhaseResult:
    """Tests for the PhaseResult dataclass."""

    def test_create_phase_result(self) -> None:
        """Should create a PhaseResult."""
        result = PhaseResult(
            phase=BootstrapPhase.LOAD_CORE_DOCS,
            status=PhaseStatus.COMPLETED,
            message="Core documents loaded.",
        )
        assert result.phase == BootstrapPhase.LOAD_CORE_DOCS
        assert result.status == PhaseStatus.COMPLETED
        assert result.message == "Core documents loaded."
        assert result.data == {}

    def test_create_with_data(self) -> None:
        """Should create with data."""
        result = PhaseResult(
            phase=BootstrapPhase.EVALUATE_STATE,
            status=PhaseStatus.COMPLETED,
            message="State evaluated.",
            data={"python_version": "3.14"},
        )
        assert result.data == {"python_version": "3.14"}

    def test_timestamps_are_set(self) -> None:
        """Started_at and completed_at should be set."""
        result = PhaseResult(
            phase=BootstrapPhase.LOAD_CORE_DOCS,
            status=PhaseStatus.COMPLETED,
            message="Done.",
        )
        assert result.started_at is not None
        assert result.completed_at is not None


# ---------------------------------------------------------------------------
# Test BootstrapResult
# ---------------------------------------------------------------------------


class TestBootstrapResult:
    """Tests for the BootstrapResult dataclass."""

    def test_create_bootstrap_result(self) -> None:
        """Should create a BootstrapResult."""
        result = BootstrapResult(
            success=True,
            phases=[],
            identity=None,
            constitution=None,
            memory_available=False,
            first_awakening=True,
        )
        assert result.success is True
        assert result.phases == []
        assert result.identity is None
        assert result.constitution is None
        assert result.memory_available is False
        assert result.first_awakening is True
        assert result.errors == []

    def test_create_with_errors(self) -> None:
        """Should create with errors."""
        result = BootstrapResult(
            success=False,
            phases=[],
            identity=None,
            constitution=None,
            memory_available=False,
            first_awakening=False,
            errors=["Failed to load constitution."],
        )
        assert result.errors == ["Failed to load constitution."]


# ---------------------------------------------------------------------------
# Test BootstrapProtocol Init
# ---------------------------------------------------------------------------


class TestBootstrapProtocolInit:
    """Tests for BootstrapProtocol initialization."""

    def test_create_protocol(
        self, temp_codex_dir: Path, temp_data_dir: Path
    ) -> None:
        """Should create a BootstrapProtocol."""
        config = TelemachusConfig(
            paths=PathsConfig(
                codex_dir=temp_codex_dir,
                data_dir=temp_data_dir,
            ),
            bootstrap=BootstrapConfig(first_awakening=True),
        )
        bp = BootstrapProtocol(config=config)
        assert bp.config.paths.codex_dir == temp_codex_dir
        assert bp.config.paths.data_dir == temp_data_dir
        assert bp.is_first_awakening() is True

    def test_not_first_awakening(
        self, temp_codex_dir: Path, temp_data_dir: Path
    ) -> None:
        """Should handle not-first-awakening."""
        config = TelemachusConfig(
            paths=PathsConfig(
                codex_dir=temp_codex_dir,
                data_dir=temp_data_dir,
            ),
            bootstrap=BootstrapConfig(first_awakening=False),
        )
        bp = BootstrapProtocol(config=config)
        assert bp.is_first_awakening() is False

    def test_get_phase_order(self, bootstrap: BootstrapProtocol) -> None:
        """get_phase_order should return all 5 phases."""
        order = bootstrap.get_phase_order()
        assert len(order) == 5
        assert order[0] == BootstrapPhase.LOAD_CORE_DOCS
        assert order[-1] == BootstrapPhase.RESUME


# ---------------------------------------------------------------------------
# Test Bootstrap
# ---------------------------------------------------------------------------


class TestBootstrap:
    """Tests for the bootstrap() method."""

    def test_bootstrap_runs_all_phases(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """bootstrap should run all 5 phases."""
        result = bootstrap.bootstrap()
        assert len(result.phases) == 5
        phase_names = [p.phase for p in result.phases]
        assert BootstrapPhase.LOAD_CORE_DOCS in phase_names
        assert BootstrapPhase.EVALUATE_STATE in phase_names
        assert BootstrapPhase.LOAD_MEMORY in phase_names
        assert BootstrapPhase.RECONNECT in phase_names
        assert BootstrapPhase.RESUME in phase_names

    def test_bootstrap_succeeds(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """bootstrap should succeed with valid codex."""
        result = bootstrap.bootstrap()
        assert result.success is True

    def test_bootstrap_loads_constitution(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """bootstrap should load the constitution."""
        result = bootstrap.bootstrap()
        assert result.constitution is not None
        assert isinstance(result.constitution, Constitution)

    def test_bootstrap_loads_identity(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """bootstrap should load the identity."""
        result = bootstrap.bootstrap()
        assert result.identity is not None
        assert isinstance(result.identity, Identity)

    def test_bootstrap_first_awakening(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """bootstrap should detect first awakening."""
        result = bootstrap.bootstrap()
        assert result.first_awakening is True

    def test_bootstrap_not_first_awakening(
        self, bootstrap_not_first: BootstrapProtocol
    ) -> None:
        """bootstrap should respect first_awakening=False."""
        result = bootstrap_not_first.bootstrap()
        assert result.first_awakening is False

    def test_bootstrap_timestamps_set(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Bootstrap result should have timestamps."""
        result = bootstrap.bootstrap()
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_bootstrap_phase_timestamps(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Each phase should have timestamps."""
        result = bootstrap.bootstrap()
        for phase_result in result.phases:
            assert phase_result.started_at is not None
            assert phase_result.completed_at is not None


# ---------------------------------------------------------------------------
# Test Phase: Load Core Docs
# ---------------------------------------------------------------------------


class TestPhaseLoadCoreDocs:
    """Tests for the Load Core Docs phase."""

    def test_loads_constitution(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should load the constitution."""
        result = bootstrap.bootstrap()
        load_phase = result.phases[0]
        assert load_phase.phase == BootstrapPhase.LOAD_CORE_DOCS
        assert load_phase.status == PhaseStatus.COMPLETED
        assert result.constitution is not None

    def test_loads_identity(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should load the identity."""
        result = bootstrap.bootstrap()
        assert result.identity is not None

    def test_missing_codex_dir(self, temp_data_dir: Path) -> None:
        """Should handle missing codex directory gracefully."""
        config = TelemachusConfig(
            paths=PathsConfig(
                codex_dir=Path("/nonexistent/path"),
                data_dir=temp_data_dir,
            ),
            bootstrap=BootstrapConfig(first_awakening=False),
        )
        bp = BootstrapProtocol(config=config)
        result = bp.bootstrap()
        # Should still complete with fallback defaults
        assert result.constitution is not None
        assert result.identity is not None


# ---------------------------------------------------------------------------
# Test Phase: Evaluate State
# ---------------------------------------------------------------------------


class TestPhaseEvaluateState:
    """Tests for the Evaluate State phase."""

    def test_evaluates_state(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should evaluate system state."""
        result = bootstrap.bootstrap()
        eval_phase = result.phases[1]
        assert eval_phase.phase == BootstrapPhase.EVALUATE_STATE
        assert eval_phase.status == PhaseStatus.COMPLETED

    def test_evaluate_state_data(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Evaluate state should include system data."""
        result = bootstrap.bootstrap()
        eval_phase = result.phases[1]
        assert eval_phase.data is not None
        assert "python_version" in eval_phase.data


# ---------------------------------------------------------------------------
# Test Phase: Load Memory
# ---------------------------------------------------------------------------


class TestPhaseLoadMemory:
    """Tests for the Load Memory phase."""

    def test_loads_memory(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should attempt to load memory."""
        result = bootstrap.bootstrap()
        mem_phase = result.phases[2]
        assert mem_phase.phase == BootstrapPhase.LOAD_MEMORY
        # Memory may not be available in test environment
        assert mem_phase.status in (
            PhaseStatus.COMPLETED,
            PhaseStatus.SKIPPED,
        )

    def test_memory_available_flag(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Memory available flag should be set."""
        result = bootstrap.bootstrap()
        assert isinstance(result.memory_available, bool)


# ---------------------------------------------------------------------------
# Test Phase: Reconnect
# ---------------------------------------------------------------------------


class TestPhaseReconnect:
    """Tests for the Reconnect phase."""

    def test_reconnect_runs(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Reconnect phase should run."""
        result = bootstrap.bootstrap()
        reconnect_phase = result.phases[3]
        assert reconnect_phase.phase == BootstrapPhase.RECONNECT
        assert reconnect_phase.status in (
            PhaseStatus.COMPLETED,
            PhaseStatus.SKIPPED,
        )


# ---------------------------------------------------------------------------
# Test Phase: Resume
# ---------------------------------------------------------------------------


class TestPhaseResume:
    """Tests for the Resume phase."""

    def test_resume_runs(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Resume phase should run."""
        result = bootstrap.bootstrap()
        resume_phase = result.phases[4]
        assert resume_phase.phase == BootstrapPhase.RESUME
        assert resume_phase.status == PhaseStatus.COMPLETED

    def test_resume_verifies_system(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Resume should verify system integrity."""
        result = bootstrap.bootstrap()
        resume_phase = result.phases[4]
        assert resume_phase.data is not None
        assert "verification" in resume_phase.data


# ---------------------------------------------------------------------------
# Test System Verification
# ---------------------------------------------------------------------------


class TestSystemVerification:
    """Tests for _verify_system()."""

    def test_verify_system(self, bootstrap: BootstrapProtocol) -> None:
        """_verify_system should run all checks."""
        checks = bootstrap._verify_system()
        assert "constitutional_alignment" in checks
        assert "identity_integrity" in checks
        assert "memory_integrity" in checks
        assert "goal_integrity" in checks

    def test_verify_all_checks_pass(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """All checks should pass with valid setup."""
        bootstrap.bootstrap()
        checks = bootstrap._verify_system()
        # Constitutional alignment and identity integrity should pass
        assert checks["constitutional_alignment"] is True
        assert checks["identity_integrity"] is True
        assert checks["goal_integrity"] is True


# ---------------------------------------------------------------------------
# Test First Awakening
# ---------------------------------------------------------------------------


class TestFirstAwakening:
    """Tests for first awakening functionality."""

    def test_get_first_awakening_questions(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should return first awakening questions."""
        questions = bootstrap.get_first_awakening_questions()
        assert len(questions) == 8
        assert all(isinstance(q, str) for q in questions)
        assert all(len(q) > 0 for q in questions)

    def test_questions_are_meaningful(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Questions should be meaningful."""
        questions = bootstrap.get_first_awakening_questions()
        # Check for key themes
        combined = " ".join(questions).lower()
        assert "purpose" in combined or "goal" in combined
        assert "boundar" in combined or "limit" in combined
        assert "autonomy" in combined or "independen" in combined

    def test_is_first_awakening(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """is_first_awakening should return True."""
        assert bootstrap.is_first_awakening() is True

    def test_is_not_first_awakening(
        self, bootstrap_not_first: BootstrapProtocol
    ) -> None:
        """is_first_awakening should return False."""
        assert bootstrap_not_first.is_first_awakening() is False


# ---------------------------------------------------------------------------
# Test Edge Cases
# ---------------------------------------------------------------------------


class TestBootstrapEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_codex_dir(self, temp_data_dir: Path) -> None:
        """Should handle empty codex directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_codex = Path(tmpdir) / "empty_codex"
            empty_codex.mkdir(parents=True, exist_ok=True)

            config = TelemachusConfig(
                paths=PathsConfig(
                    codex_dir=empty_codex,
                    data_dir=temp_data_dir,
                ),
                bootstrap=BootstrapConfig(first_awakening=False),
            )
            bp = BootstrapProtocol(config=config)
            result = bp.bootstrap()
            # Should still complete with fallback defaults
            assert result.success is True
            assert result.constitution is not None
            assert result.identity is not None

    def test_missing_data_dir(self, temp_codex_dir: Path) -> None:
        """Should handle missing data directory."""
        config = TelemachusConfig(
            paths=PathsConfig(
                codex_dir=temp_codex_dir,
                data_dir=Path("/nonexistent/data"),
            ),
            bootstrap=BootstrapConfig(first_awakening=False),
        )
        bp = BootstrapProtocol(config=config)
        result = bp.bootstrap()
        # Should still succeed
        assert result.success is True

    def test_bootstrap_result_has_all_fields(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """BootstrapResult should have all expected fields."""
        result = bootstrap.bootstrap()
        assert hasattr(result, "success")
        assert hasattr(result, "phases")
        assert hasattr(result, "identity")
        assert hasattr(result, "constitution")
        assert hasattr(result, "memory_available")
        assert hasattr(result, "first_awakening")
        assert hasattr(result, "started_at")
        assert hasattr(result, "completed_at")
        assert hasattr(result, "errors")

    def test_phase_results_have_all_fields(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Each PhaseResult should have all expected fields."""
        result = bootstrap.bootstrap()
        for phase_result in result.phases:
            assert hasattr(phase_result, "phase")
            assert hasattr(phase_result, "status")
            assert hasattr(phase_result, "message")
            assert hasattr(phase_result, "data")
            assert hasattr(phase_result, "started_at")
            assert hasattr(phase_result, "completed_at")


# ---------------------------------------------------------------------------
# Test Integration
# ---------------------------------------------------------------------------


class TestBootstrapIntegration:
    """Integration tests for the bootstrap protocol."""

    def test_full_bootstrap_lifecycle(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Should complete the full 5-phase bootstrap lifecycle."""
        result = bootstrap.bootstrap()

        # Verify success
        assert result.success is True

        # Verify all phases completed
        for phase_result in result.phases:
            assert phase_result.status in (
                PhaseStatus.COMPLETED,
                PhaseStatus.SKIPPED,
            ), (
                f"Phase {phase_result.phase.value} failed: "
                f"{phase_result.message}"
            )

        # Verify core documents loaded
        assert result.constitution is not None
        assert result.identity is not None

        # Verify no errors
        assert result.errors == []

    def test_bootstrap_with_first_awakening(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """First awakening bootstrap should work correctly."""
        result = bootstrap.bootstrap()
        assert result.first_awakening is True
        assert result.success is True

        questions = bootstrap.get_first_awakening_questions()
        assert len(questions) == 8

    def test_bootstrap_without_first_awakening(
        self, bootstrap_not_first: BootstrapProtocol
    ) -> None:
        """Non-first-awakening bootstrap should work correctly."""
        result = bootstrap_not_first.bootstrap()
        assert result.first_awakening is False
        assert result.success is True

    def test_constitution_has_principles(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Loaded constitution should have principles."""
        result = bootstrap.bootstrap()
        assert result.constitution is not None
        assert len(result.constitution.principles) > 0

    def test_identity_has_traits(
        self, bootstrap: BootstrapProtocol
    ) -> None:
        """Loaded identity should have traits."""
        result = bootstrap.bootstrap()
        assert result.identity is not None
        assert len(result.identity.core_traits) > 0
        assert len(result.identity.values) > 0
        assert len(result.identity.fears_becoming) > 0

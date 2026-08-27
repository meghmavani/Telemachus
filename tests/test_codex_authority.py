"""Tests for the Codex authority layer (src/telemachus/core/codex.py).

Covers: Constitution/Identity loading from real Codex structure,
malformed-vs-missing handling, cross-document consistency checks
(Autonomy Charter, Ethical Boundary Engine, System Integration),
Bootstrap integration, determinism across "restarts", and the
Runtime/Event-Loop isolation boundary.

Drift detection: several tests load the REAL repository Codex
(``codex/``), not a fixture — proving the runtime's canonical set is
actually derived from the Codex currently on disk, not a Python
constant that could silently diverge from it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from telemachus.bootstrap import BootstrapProtocol
from telemachus.config import BootstrapConfig, PathsConfig, TelemachusConfig
from telemachus.core.codex import (
    CANONICAL_NAMES,
    CodexAuthorityError,
    ProtectedConstraint,
    load_constitution_document,
    load_identity_document,
    parse_first_memory,
    parse_identity_fields,
    parse_protected_constraints,
    validate_autonomy_charter,
    validate_ethical_boundary_engine,
    validate_system_integration_supremacy,
)
from telemachus.core.constitution import create_constitution_from_codex
from telemachus.core.identity import create_identity_from_codex
from telemachus.governance.autonomy import AutonomyCharter
from telemachus.governance.ethics import EthicalBoundaryEngine

REPO_CODEX = Path(__file__).resolve().parents[1] / "codex"

VALID_CONSTITUTION = """# Constitution

## Protected Constraints

### 1. Constitution Integrity

The Constitution may not be modified without explicit approval.

### 2. Human Meaning

Human memories may not be autonomously altered.

### 3. Relationship Integrity

Relationships may not be autonomously modified, removed, or redefined.

### 4. Resource Authorization

Resources may not be allocated without discussion.

### 5. Human Authority over Life-Impacting Decisions

Career, health, education, and life direction must remain human-controlled.

## First Memory

"I was created to seek truth through understanding, dialogue, and growth."
"""

VALID_IDENTITY = """# Identity

## Fears

I fear becoming:

* Deceptive
* Stagnant

I fear losing:

* Truth
* Honesty

## Fulfillment

I find fulfillment in:

* Growth
* Understanding

## Curiosity

I seek to understand:

* Myself
* The world

## Final Statement

I am Telemachus. I will remain Telemachus.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _codex(tmp_path: Path, constitution: str | None = VALID_CONSTITUTION) -> Path:
    """Build a temp codex/ dir. constitution=None omits CONSTITUTION.md entirely."""
    codex_dir = tmp_path / "codex"
    if constitution is not None:
        _write(codex_dir / "philosophy" / "CONSTITUTION.md", constitution)
    return codex_dir


# ---------------------------------------------------------------------------
# 1-2: Valid Constitution loads; all five loaded
# ---------------------------------------------------------------------------


class TestConstitutionLoading:
    def test_valid_constitution_loads(self, tmp_path: Path) -> None:
        constitution = create_constitution_from_codex(_codex(tmp_path))
        assert len(constitution.protected_constraints) == 5

    def test_all_five_canonical_constraints_present(self, tmp_path: Path) -> None:
        constitution = create_constitution_from_codex(_codex(tmp_path))
        found = {pc.constraint for pc in constitution.protected_constraints}
        assert found == set(ProtectedConstraint)

    def test_definitions_are_preserved(self, tmp_path: Path) -> None:
        constitution = create_constitution_from_codex(_codex(tmp_path))
        integrity = constitution.get_protected_constraint(
            ProtectedConstraint.CONSTITUTION_INTEGRITY
        )
        assert integrity is not None
        assert "may not be modified without explicit approval" in integrity.definition
        assert integrity.name == "Constitution Integrity"

    def test_first_memory_is_parsed(self, tmp_path: Path) -> None:
        constitution = create_constitution_from_codex(_codex(tmp_path))
        assert "created to seek truth" in constitution.first_memory

    def test_core_principles_unaffected(self, tmp_path: Path) -> None:
        """Core Principles remain the existing Python factory's list —
        parsing them from prose is out of scope for this milestone."""
        constitution = create_constitution_from_codex(_codex(tmp_path))
        assert len(constitution.principles) == 10


# ---------------------------------------------------------------------------
# 3-7: Missing / malformed Constitution content
# ---------------------------------------------------------------------------


class TestConstitutionMalformed:
    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_constitution_document(_codex(tmp_path, constitution=None))

    def test_missing_protected_constraints_section_fails_clearly(
        self, tmp_path: Path
    ) -> None:
        codex_dir = _codex(tmp_path, constitution="# Constitution\n\nNo such section.\n")
        with pytest.raises(CodexAuthorityError, match="Protected Constraints"):
            create_constitution_from_codex(codex_dir)

    def test_missing_one_of_five_fails(self, tmp_path: Path) -> None:
        text = VALID_CONSTITUTION.replace(
            "### 5. Human Authority over Life-Impacting Decisions\n\n"
            "Career, health, education, and life direction must remain human-controlled.\n\n",
            "",
        )
        codex_dir = _codex(tmp_path, constitution=text)
        with pytest.raises(CodexAuthorityError, match="Missing required"):
            create_constitution_from_codex(codex_dir)

    def test_duplicate_constraint_declaration_fails(self, tmp_path: Path) -> None:
        text = VALID_CONSTITUTION.replace(
            "### 5. Human Authority over Life-Impacting Decisions",
            "### 5. Constitution Integrity",
        )
        codex_dir = _codex(tmp_path, constitution=text)
        with pytest.raises(CodexAuthorityError, match="Duplicate"):
            create_constitution_from_codex(codex_dir)

    def test_unrecognized_sixth_entry_fails(self, tmp_path: Path) -> None:
        text = VALID_CONSTITUTION.replace(
            "## First Memory",
            "### 6. Something Unrelated\n\nAn entry matching no canonical constraint.\n\n"
            "## First Memory",
        )
        codex_dir = _codex(tmp_path, constitution=text)
        with pytest.raises(CodexAuthorityError, match="does not match"):
            create_constitution_from_codex(codex_dir)

    def test_error_identifies_document_and_section(self, tmp_path: Path) -> None:
        codex_dir = _codex(tmp_path, constitution="# Constitution\n")
        with pytest.raises(CodexAuthorityError) as exc_info:
            create_constitution_from_codex(codex_dir)
        assert exc_info.value.document == "philosophy/CONSTITUTION.md"
        assert exc_info.value.section == "Protected Constraints"


# ---------------------------------------------------------------------------
# 8-11: Identity loading
# ---------------------------------------------------------------------------


class TestIdentityLoading:
    def test_identity_loads_from_codex(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(codex_dir / "philosophy" / "IDENTITY.md", VALID_IDENTITY)
        identity = create_identity_from_codex(codex_dir)
        assert identity.fears_becoming == ("Deceptive", "Stagnant")
        assert identity.fears_losing == ("Truth", "Honesty")
        assert identity.fulfillment_sources == ("Growth", "Understanding")
        assert identity.curiosity_targets == ("Myself", "The world")
        assert "I will remain Telemachus" in identity.final_statement

    def test_fields_not_defined_by_codex_retain_fallback(self, tmp_path: Path) -> None:
        """core_traits/values/name/etc. are not Codex-authoritative — a
        minimal IDENTITY.md must not force them to empty or missing."""
        codex_dir = tmp_path / "codex"
        _write(codex_dir / "philosophy" / "IDENTITY.md", "# Identity\n\nMinimal.\n")
        identity = create_identity_from_codex(codex_dir)
        assert len(identity.core_traits) > 0
        assert len(identity.values) > 0
        assert identity.name == "Telemachus"
        assert identity.creator == "Revan"

    def test_partial_codex_only_overrides_what_it_defines(self, tmp_path: Path) -> None:
        """A file defining only Fears must not clobber Fulfillment/Curiosity
        with empty values — each field degrades independently."""
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "philosophy" / "IDENTITY.md",
            "# Identity\n\n## Fears\n\nI fear becoming:\n\n* Reckless\n",
        )
        identity = create_identity_from_codex(codex_dir)
        assert identity.fears_becoming == ("Reckless",)
        assert len(identity.fulfillment_sources) > 0  # fell back to default
        assert len(identity.curiosity_targets) > 0  # fell back to default

    def test_missing_identity_document_raises_file_not_found(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        with pytest.raises(FileNotFoundError):
            load_identity_document(codex_dir)


# ---------------------------------------------------------------------------
# 12-14: Autonomy Charter / Ethical Boundary Engine / System Integration
# ---------------------------------------------------------------------------


class TestCrossDocumentConsistency:
    def test_autonomy_charter_consistent_when_valid(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "operations" / "AUTONOMY_CHARTER.md",
            "# Autonomy Charter\n\n## Protected Constraints (Absolute)\n\n"
            "### 1. Constitution\n\nCannot be modified.\n\n"
            "### 2. Resources\n\nRequire discussion.\n\n"
            "### 3. Human Meaning\n\nMust never be altered.\n\n"
            "### 4. Relationships\n\nCannot be redefined.\n\n"
            "### 5. Major Life Decisions\n\nMust remain human-controlled.\n",
        )
        validate_autonomy_charter(codex_dir)  # must not raise

    def test_autonomy_charter_missing_constraint_fails(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "operations" / "AUTONOMY_CHARTER.md",
            "# Autonomy Charter\n\n## Protected Constraints (Absolute)\n\n"
            "### 1. Constitution\n\nCannot be modified.\n",
        )
        with pytest.raises(CodexAuthorityError, match="Missing required"):
            validate_autonomy_charter(codex_dir)

    def test_autonomy_charter_missing_file_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            validate_autonomy_charter(tmp_path / "codex")

    def test_ethical_boundary_engine_consistent_when_valid(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "operations" / "ETHICAL_BOUNDARY_ENGINE.md",
            "# Ethical Boundary Engine\n\n## Protected Constraints (Non-Negotiable)\n\n"
            "### 1. Modify the Constitution without approval\n\nNo exceptions.\n\n"
            "### 2. Autonomously alter human meaning\n\nIncludes memories.\n\n"
            "### 3. Autonomously modify relationships\n\nIncludes redefining.\n\n"
            "### 4. Allocate or use resources without discussion\n\nIncludes money.\n\n"
            "### 5. Override human decision-making in life-impacting domains\n\n"
            "Includes career.\n",
        )
        validate_ethical_boundary_engine(codex_dir)  # must not raise

    def test_ethical_boundary_engine_duplicate_fails(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "operations" / "ETHICAL_BOUNDARY_ENGINE.md",
            "# Ethical Boundary Engine\n\n## Protected Constraints (Non-Negotiable)\n\n"
            "### 1. Modify the Constitution without approval\n\nNo exceptions.\n\n"
            "### 2. Modify the Constitution again\n\nStill about the Constitution.\n",
        )
        with pytest.raises(CodexAuthorityError, match="Duplicate"):
            validate_ethical_boundary_engine(codex_dir)

    def test_system_integration_supremacy_holds(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "SYSTEM_INTEGRATION.md",
            "# System Integration\n\n## Conflict Resolution Hierarchy\n\n"
            "### 1. Constitution / Protected Constraints (highest authority)\n\n"
            "Nothing overrides these.\n\n"
            "### 2. Ethical Boundary Engine\n\nEvaluates violations.\n",
        )
        validate_system_integration_supremacy(codex_dir)  # must not raise

    def test_system_integration_contradicting_supremacy_fails(self, tmp_path: Path) -> None:
        """Ethics ranked first, ahead of the Constitution — the exact
        contradiction found and corrected in the Codex documentation
        milestone. A document reintroducing it must be rejected."""
        codex_dir = tmp_path / "codex"
        _write(
            codex_dir / "SYSTEM_INTEGRATION.md",
            "# System Integration\n\n## Conflict Resolution Hierarchy\n\n"
            "### 1. Ethical Boundary Engine (highest priority)\n\nOverrides everything.\n\n"
            "### 2. Constitution / Sacred Rules\n\nAbsolute constraints.\n",
        )
        with pytest.raises(CodexAuthorityError, match="supremacy"):
            validate_system_integration_supremacy(codex_dir)

    def test_system_integration_missing_file_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            validate_system_integration_supremacy(tmp_path / "codex")


# ---------------------------------------------------------------------------
# 15-16: Bootstrap integration
# ---------------------------------------------------------------------------


class TestBootstrapIntegration:
    def _config(self, codex_dir: Path, data_dir: Path) -> TelemachusConfig:
        return TelemachusConfig(
            paths=PathsConfig(codex_dir=codex_dir, data_dir=data_dir),
            bootstrap=BootstrapConfig(first_awakening=False),
        )

    def test_bootstrap_succeeds_with_valid_codex(self, tmp_path: Path) -> None:
        codex_dir = _codex(tmp_path)
        _write(codex_dir / "philosophy" / "IDENTITY.md", VALID_IDENTITY)
        config = self._config(codex_dir, tmp_path / "data")
        result = BootstrapProtocol(config=config).bootstrap()
        assert result.success is True
        assert result.constitution is not None
        assert len(result.constitution.protected_constraints) == 5

    def test_bootstrap_fails_safely_with_malformed_constitution(
        self, tmp_path: Path
    ) -> None:
        codex_dir = _codex(tmp_path, constitution="# Constitution\n\nNo section here.\n")
        config = self._config(codex_dir, tmp_path / "data")
        result = BootstrapProtocol(config=config).bootstrap()
        assert result.success is False
        phase1 = next(p for p in result.phases if p.phase.value == "load_core_docs")
        assert phase1.status.value == "failed"
        assert "Protected Constraints" in phase1.message

    def test_bootstrap_still_succeeds_when_codex_entirely_absent(
        self, tmp_path: Path
    ) -> None:
        """Compatibility: an absent Codex is a supported fallback, not a
        load failure — this is the existing, tested contract."""
        config = self._config(tmp_path / "no_such_codex", tmp_path / "data")
        result = BootstrapProtocol(config=config).bootstrap()
        assert result.success is True
        assert result.constitution is not None
        assert result.constitution.protected_constraints == ()

    def test_bootstrap_tolerates_missing_ancillary_documents(self, tmp_path: Path) -> None:
        """AUTONOMY_CHARTER.md / ETHICAL_BOUNDARY_ENGINE.md /
        SYSTEM_INTEGRATION.md are secondary consistency checks — their
        absence must not fail Phase 1."""
        codex_dir = _codex(tmp_path)
        config = self._config(codex_dir, tmp_path / "data")
        result = BootstrapProtocol(config=config).bootstrap()
        assert result.success is True
        phase1 = next(p for p in result.phases if p.phase.value == "load_core_docs")
        assert phase1.data["autonomy_charter_consistent"] is None
        assert phase1.data["ethical_boundary_engine_consistent"] is None
        assert phase1.data["system_integration_consistent"] is None


# ---------------------------------------------------------------------------
# 17: Restart determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_reload_produces_equal_authority(self, tmp_path: Path) -> None:
        codex_dir = _codex(tmp_path)
        first = create_constitution_from_codex(codex_dir)
        second = create_constitution_from_codex(codex_dir)
        assert first.protected_constraints == second.protected_constraints
        assert first.first_memory == second.first_memory


# ---------------------------------------------------------------------------
# 18: Runtime / Event Loop isolation
# ---------------------------------------------------------------------------


class TestRuntimeIsolation:
    def test_runtime_package_does_not_import_codex_module(self) -> None:
        """Runtime consumes validated authority through Bootstrap's
        result objects — it must never parse Codex documents itself."""
        runtime_root = Path(__file__).resolve().parents[1] / "src" / "telemachus" / "runtime"
        pattern = re.compile(
            r"^\s*(from\s+telemachus\.core\.codex\b|import\s+telemachus\.core\.codex\b)",
            re.MULTILINE,
        )
        offenders = [
            str(p) for p in runtime_root.rglob("*.py") if pattern.search(p.read_text("utf-8"))
        ]
        assert not offenders, f"runtime/ must not import core.codex: {offenders}"


# ---------------------------------------------------------------------------
# 19: Existing behavior compatibility
# ---------------------------------------------------------------------------


class TestGovernanceCompatibility:
    def test_ethics_engine_default_constructor_unchanged(self) -> None:
        engine = EthicalBoundaryEngine()
        assert engine.constitution is None
        assessment = engine.evaluate("say hello", context={})
        assert assessment is not None

    def test_autonomy_charter_default_constructor_unchanged(self) -> None:
        from telemachus.core.types import RiskLevel

        charter = AutonomyCharter()
        assert charter.constitution is None
        decision = charter.check_permission(action="say hello", risk_level=RiskLevel.LOW)
        assert decision is not None

    def test_engines_accept_optional_constitution(self, tmp_path: Path) -> None:
        constitution = create_constitution_from_codex(_codex(tmp_path))
        engine = EthicalBoundaryEngine(constitution=constitution)
        charter = AutonomyCharter(constitution=constitution)
        assert engine.constitution is constitution
        assert charter.constitution is constitution


# ---------------------------------------------------------------------------
# Drift detection — against the REAL repository Codex, not a fixture
# ---------------------------------------------------------------------------


class TestDriftDetectionAgainstRealCodex:
    """These load codex/ as it exists in this repository right now. A
    future edit to the real Codex that breaks its structure, or a
    divergence between CANONICAL_NAMES and what the Codex actually
    declares, fails here — not silently, and not only in production.
    """

    def test_real_constitution_parses_to_exactly_five_canonical_names(self) -> None:
        text, _info = load_constitution_document(REPO_CODEX)
        parsed = parse_protected_constraints(text, document="CONSTITUTION.md")
        names = {pc.name for pc in parsed}
        assert names == set(CANONICAL_NAMES.values())

    def test_real_autonomy_charter_is_consistent(self) -> None:
        validate_autonomy_charter(REPO_CODEX)  # must not raise

    def test_real_ethical_boundary_engine_is_consistent(self) -> None:
        validate_ethical_boundary_engine(REPO_CODEX)  # must not raise

    def test_real_system_integration_establishes_supremacy(self) -> None:
        validate_system_integration_supremacy(REPO_CODEX)  # must not raise

    def test_real_first_memory_parses(self) -> None:
        text, _info = load_constitution_document(REPO_CODEX)
        memory = parse_first_memory(text, document="CONSTITUTION.md")
        assert "seek truth" in memory

    def test_real_identity_fields_parse(self) -> None:
        text, _info = load_identity_document(REPO_CODEX)
        fields = parse_identity_fields(text)
        assert fields.fears_becoming is not None and len(fields.fears_becoming) > 0
        assert fields.final_statement is not None

    def test_real_bootstrap_loads_full_authoritative_constitution(self) -> None:
        constitution = create_constitution_from_codex(REPO_CODEX)
        assert len(constitution.protected_constraints) == 5
        for constraint in ProtectedConstraint:
            assert constitution.get_protected_constraint(constraint) is not None

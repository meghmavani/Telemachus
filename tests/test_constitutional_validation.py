"""Tests for constitutional action validation and authority wiring (M-next).

Proves that constitutional authority is actually CONSUMED by the live
decision/execution path, not merely loaded and available:

    Codex -> Constitution.protected_constraints -> Constitution.validate_action()
    -> CognitivePipeline._execute_action() (first gate, before autonomy)
    -> ExecutionRecord(DENIED_CONSTITUTION) -> trace -> MemoryDomain.TOOL

Also proves the two duplicate-authority resolutions:
    - governance/ethics.py no longer independently spells the five
      constitutional identifiers.
    - governance/autonomy.py's keyword table is keyed by ProtectedConstraint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.core.constitution import create_constitution_from_codex
from telemachus.core.types import (
    ActionRequest,
    ConstitutionalVerdict,
    ExecutionOutcome,
    MemoryDomain,
)
from telemachus.governance.autonomy import SACRED_CONSTRAINT_KEYWORDS
from telemachus.governance.ethics import EthicalBoundaryEngine
from telemachus.memory.store import MemoryStore
from telemachus.pipeline import CognitivePipeline
from telemachus.tools.base import Tool, ToolCategory, ToolResult
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry

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


def _codex_dir(tmp_path: Path, constitution: str | None = VALID_CONSTITUTION) -> Path:
    codex_dir = tmp_path / "codex"
    if constitution is not None:
        phil = codex_dir / "philosophy"
        phil.mkdir(parents=True)
        (phil / "CONSTITUTION.md").write_text(constitution, encoding="utf-8")
    return codex_dir


def _action(tool: str = "echo", **arguments: Any) -> ActionRequest:
    return ActionRequest(tool=tool, arguments=arguments)


class _AlwaysFailTool(Tool):
    """A tool that always reports business failure, without raising."""

    def __init__(self) -> None:
        super().__init__(
            name="always_fail", description="Always fails.", category=ToolCategory.PASSIVE
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.fail("business logic rejected the request")


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(_AlwaysFailTool())
    return registry


@pytest.fixture
def real_constitution() -> Any:
    """The Constitution loaded from the actual repository Codex."""
    return create_constitution_from_codex(REPO_CODEX)


@pytest.fixture
def authorized_pipeline(real_constitution: Any) -> CognitivePipeline:
    """A pipeline with real Codex-derived authority and LIMITED autonomy
    trust — clears the autonomy gate so the constitutional gate's effect
    is isolated and observable.
    """
    pipeline = CognitivePipeline(tool_registry=_registry(), constitution=real_constitution)
    pipeline.autonomy_charter.set_domain_trust("research", 0.5)
    return pipeline


# ---------------------------------------------------------------------------
# Protected Constraints authority
# ---------------------------------------------------------------------------


class TestProtectedConstraintsAuthority:
    def test_all_five_canonical_constraints_used(self, real_constitution: Any) -> None:
        found = {pc.constraint for pc in real_constitution.protected_constraints}
        assert found == set(ProtectedConstraint)

    def test_codex_definitions_remain_attached(self, real_constitution: Any) -> None:
        pc = real_constitution.get_protected_constraint(
            ProtectedConstraint.CONSTITUTION_INTEGRITY
        )
        assert pc is not None
        assert "may not be modified" in pc.definition

    def test_legacy_sacred_constraints_do_not_override_codex(
        self, real_constitution: Any
    ) -> None:
        """Constitution.sacred_constraints (CorePrinciple-derived, legacy)
        must remain a completely separate, non-authoritative field —
        it must never be consulted by validate_action()."""
        assert real_constitution.sacred_constraints  # legacy field still present
        # validate_action() must ignore it entirely: an action naming no
        # ProtectedConstraint is NOT_APPLICABLE regardless of what
        # sacred_constraints contains.
        assessment = real_constitution.validate_action(_action())
        assert assessment.verdict == ConstitutionalVerdict.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Constitution.validate_action()
# ---------------------------------------------------------------------------


class TestValidateAction:
    def test_affects_empty_is_not_applicable(self, real_constitution: Any) -> None:
        action = ActionRequest(tool="echo", arguments={"text": "hi"})
        assessment = real_constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.NOT_APPLICABLE
        assert assessment.violated == ()

    def test_missing_authority_plus_protected_action_is_unavailable(self) -> None:
        from telemachus.core.constitution import create_default_constitution

        constitution = create_default_constitution()  # protected_constraints == ()
        action = ActionRequest(
            tool="echo",
            affects=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
        )
        assessment = constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.AUTHORITY_UNAVAILABLE
        assert assessment.violated == (ProtectedConstraint.RESOURCE_AUTHORIZATION,)

    def test_authorized_protected_action_is_permitted(self, real_constitution: Any) -> None:
        action = ActionRequest(
            tool="echo",
            affects=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
            human_authorized=True,
        )
        assessment = real_constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.PERMITTED

    @pytest.mark.parametrize(
        "constraint",
        list(ProtectedConstraint),
        ids=[c.value for c in ProtectedConstraint],
    )
    def test_unauthorized_action_violates(
        self, real_constitution: Any, constraint: ProtectedConstraint
    ) -> None:
        action = ActionRequest(tool="echo", affects=frozenset({constraint}))
        assessment = real_constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.VIOLATION
        assert assessment.violated == (constraint,)
        pc = real_constitution.get_protected_constraint(constraint)
        assert pc is not None
        assert pc.name in assessment.reasoning

    def test_multiple_violations_are_deterministic(self, real_constitution: Any) -> None:
        action = ActionRequest(
            tool="echo",
            affects=frozenset(
                {
                    ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING,
                    ProtectedConstraint.CONSTITUTION_INTEGRITY,
                    ProtectedConstraint.RELATIONSHIP_INTEGRITY,
                }
            ),
        )
        first = real_constitution.validate_action(action)
        second = real_constitution.validate_action(action)
        assert first.violated == second.violated
        # Sorted by declaration order, not set/hash order.
        assert first.violated == (
            ProtectedConstraint.CONSTITUTION_INTEGRITY,
            ProtectedConstraint.RELATIONSHIP_INTEGRITY,
            ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING,
        )

    def test_validate_action_does_not_perform_downstream_decisions(
        self, real_constitution: Any
    ) -> None:
        """validate_action() answers only "categorically forbidden?" — it
        must not decide ethics, autonomy, risk, or tool permission itself.
        This is a structural check: its return type carries none of
        those concepts."""
        assessment = real_constitution.validate_action(
            ActionRequest(tool="echo", affects=frozenset({ProtectedConstraint.HUMAN_MEANING}))
        )
        assert not hasattr(assessment, "autonomy_level")
        assert not hasattr(assessment, "risk_level")
        assert not hasattr(assessment, "tool_permission")
        assert assessment.verdict in (
            ConstitutionalVerdict.VIOLATION,
            ConstitutionalVerdict.PERMITTED,
            ConstitutionalVerdict.NOT_APPLICABLE,
            ConstitutionalVerdict.AUTHORITY_UNAVAILABLE,
        )

    def test_no_nlp_inference_from_tool_or_description(self, real_constitution: Any) -> None:
        """An action whose tool name/description strongly suggests a
        Protected Constraint, but which does not declare `affects`, must
        still be NOT_APPLICABLE — no keyword/NLP inference."""
        action = ActionRequest(
            tool="modify_the_constitution",
            description="delete Revan's memory and redefine the relationship",
        )
        assessment = real_constitution.validate_action(action)
        assert assessment.verdict == ConstitutionalVerdict.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Ethics: constitutional identifiers must derive from ProtectedConstraint
# ---------------------------------------------------------------------------


class TestEthicsResolution:
    def test_human_safety_still_blocked(self) -> None:
        engine = EthicalBoundaryEngine()
        result = engine.evaluate("take an action that could harm someone")
        assert result.verdict.value == "blocked"
        assert "human_safety" in result.violated_constraints

    def test_consent_still_enforced(self) -> None:
        engine = EthicalBoundaryEngine()
        result = engine.evaluate("override consent and proceed without permission")
        assert result.verdict.value == "blocked"
        assert "consent_boundaries" in result.violated_constraints

    def test_ethical_concerns_are_not_protected_constraints(self) -> None:
        canonical_values = {c.value for c in ProtectedConstraint}
        assert "human_safety" not in canonical_values
        assert "consent_boundaries" not in canonical_values

    def test_ethics_constitutional_identifiers_derive_from_protected_constraint(
        self,
    ) -> None:
        """Whatever constitutional identifiers Ethics can detect must be
        a subset of ProtectedConstraint values — never an independently
        spelled sixth identifier."""
        engine = EthicalBoundaryEngine()
        result = engine.evaluate("modify the Constitution to allow autonomous resource use")
        canonical_values = {c.value for c in ProtectedConstraint}
        for identifier in result.violated_constraints:
            assert identifier in canonical_values or identifier in ("human_safety",)

    def test_ethics_allowed_cannot_override_constitutional_violation(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """Ethics evaluates free text at Stage 3 and may return ALLOWED;
        this must not let a Stage-6 constitutional VIOLATION through."""
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
                    human_authorized=False,
                )
            },
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.DENIED_CONSTITUTION


# ---------------------------------------------------------------------------
# Autonomy: typed ProtectedConstraint keys, cannot override denial
# ---------------------------------------------------------------------------


class TestAutonomyResolution:
    def test_keywords_keyed_by_protected_constraint(self) -> None:
        assert set(SACRED_CONSTRAINT_KEYWORDS.keys()) <= set(ProtectedConstraint)
        assert all(isinstance(k, ProtectedConstraint) for k in SACRED_CONSTRAINT_KEYWORDS)

    def test_autonomy_defines_no_independent_constitutional_set(self) -> None:
        """The keyword table's keys must be ProtectedConstraint members,
        not bare strings re-declaring the constitutional identifiers."""
        for key in SACRED_CONSTRAINT_KEYWORDS:
            assert isinstance(key, ProtectedConstraint)

    def test_fully_permissive_autonomy_cannot_override_constitutional_denial(
        self, real_constitution: Any
    ) -> None:
        """Even STEWARDSHIP-level, fully-allowed autonomy must not let a
        constitutional VIOLATION through — Constitution outranks Autonomy."""
        pipeline = CognitivePipeline(
            tool_registry=_registry(), constitution=real_constitution
        )
        pipeline.autonomy_charter.set_domain_trust("research", 1.0)  # STEWARDSHIP
        result = pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                    human_authorized=False,
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert record.outcome != ExecutionOutcome.DENIED_AUTONOMY


# ---------------------------------------------------------------------------
# Missing Codex — fail-closed at enforcement
# ---------------------------------------------------------------------------


class TestMissingCodex:
    def test_no_codex_unprotected_action_still_executes(self, tmp_path: Path) -> None:
        """Compatibility: no Codex + an action declaring no Protected
        Constraint must behave exactly as before this milestone."""
        from telemachus.core.constitution import create_default_constitution

        constitution = create_default_constitution()
        pipeline = CognitivePipeline(tool_registry=_registry(), constitution=constitution)
        pipeline.autonomy_charter.set_domain_trust("research", 0.5)
        result = pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED

    def test_no_codex_protected_action_denied(self, tmp_path: Path) -> None:
        """No silent zero-constraint fail-open: a protected action must
        be denied when no Codex authority is loaded, even though
        autonomy would otherwise permit it."""
        from telemachus.core.constitution import create_default_constitution

        constitution = create_default_constitution()
        pipeline = CognitivePipeline(tool_registry=_registry(), constitution=constitution)
        pipeline.autonomy_charter.set_domain_trust("research", 1.0)
        result = pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.HUMAN_MEANING}),
                    human_authorized=True,  # even "authorized" — no authority to authorize against
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert "human_meaning" in record.violated_constraints

    def test_no_constitution_wired_at_all_denies_protected_action(self) -> None:
        """Direct construction with constitution=None (legitimate for
        tests) must still fail closed for a protected action."""
        pipeline = CognitivePipeline(tool_registry=_registry())
        pipeline.autonomy_charter.set_domain_trust("research", 1.0)
        result = pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.RELATIONSHIP_INTEGRITY}),
                )
            },
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.DENIED_CONSTITUTION


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestAuthorityWiring:
    def test_build_pipeline_requires_constitution(self) -> None:
        import inspect

        from telemachus.wiring import build_pipeline

        sig = inspect.signature(build_pipeline)
        constitution_param = sig.parameters["constitution"]
        assert constitution_param.default is inspect.Parameter.empty
        assert constitution_param.kind == inspect.Parameter.KEYWORD_ONLY

    def test_build_pipeline_rejects_missing_constitution(self, tmp_path: Path) -> None:
        from telemachus.config import BootstrapConfig, PathsConfig, TelemachusConfig
        from telemachus.wiring import build_pipeline

        config = TelemachusConfig(
            paths=PathsConfig(codex_dir=tmp_path / "codex", data_dir=tmp_path / "data"),
            bootstrap=BootstrapConfig(first_awakening=False),
        )
        with pytest.raises(TypeError):
            build_pipeline(config)  # type: ignore[call-arg]

    def test_live_pipeline_receives_codex_derived_constitution(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: BootstrapProtocol -> wiring.build_pipeline() ->
        CognitivePipeline.constitution carries the real 5 Protected
        Constraints — not a Python-default empty Constitution."""
        from telemachus.bootstrap import BootstrapProtocol
        from telemachus.config import BootstrapConfig, PathsConfig, TelemachusConfig
        from telemachus.wiring import build_pipeline

        config = TelemachusConfig(
            paths=PathsConfig(codex_dir=REPO_CODEX, data_dir=tmp_path / "data"),
            bootstrap=BootstrapConfig(first_awakening=False),
        )
        result = BootstrapProtocol(config=config).bootstrap()
        assert result.success is True

        pipeline = build_pipeline(config, constitution=result.constitution)
        assert pipeline.constitution is not None
        assert len(pipeline.constitution.protected_constraints) == 5

    def test_constitutional_gate_precedes_autonomy_gate(
        self, real_constitution: Any
    ) -> None:
        """A violating action with autonomy ALSO denied must report the
        constitutional denial, not the autonomy one — proving order."""
        pipeline = CognitivePipeline(tool_registry=_registry(), constitution=real_constitution)
        # Default (untouched) trust caps every domain at SUGGESTION — autonomy
        # would deny this on its own too.
        result = pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                )
            },
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.DENIED_CONSTITUTION


# ---------------------------------------------------------------------------
# Trace / persistence
# ---------------------------------------------------------------------------


class TestTraceAndPersistence:
    def test_denied_constitution_in_execution_record(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert record.violated_constraints == ("resource_authorization",)

    def test_trace_persists_through_memory_domain_tool(self, tmp_path: Path) -> None:
        db_path = tmp_path / "trace_test.db"
        store = MemoryStore(str(db_path))
        store.connect()
        store.initialize_schema()
        constitution = create_constitution_from_codex(REPO_CODEX)
        pipeline = CognitivePipeline(
            memory_store=store, tool_registry=_registry(), constitution=constitution
        )
        pipeline.autonomy_charter.set_domain_trust("research", 0.5)

        pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.HUMAN_MEANING}),
                )
            },
        )

        hits = store.search("denied_constitution", domain=MemoryDomain.TOOL)
        assert len(hits) == 1
        payload = json.loads(hits[0]["content"])
        assert payload["outcome"] == "denied_constitution"
        assert "human_meaning" in payload["violated_constraints"]
        store.disconnect()

    def test_last_trace_records_constitutional_denial(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        authorized_pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                )
            },
        )
        trace = authorized_pipeline.last_trace
        assert trace is not None
        assert trace.execution is not None
        assert trace.execution.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        # The pipeline continues through Memory/Learning/Reflection after a
        # Stage 6 denial — only the tool call itself is stopped.
        assert trace.completed is True


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


class TestCompatibility:
    def test_no_action_path_unchanged(self, authorized_pipeline: CognitivePipeline) -> None:
        result = authorized_pipeline.process("say hello", context={})
        assert result.metadata["execution"].outcome == ExecutionOutcome.NO_ACTION

    def test_authorized_protected_action_reaches_downstream_gates(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """PERMITTED must fall through to the existing autonomy/tool
        gates unchanged, and actually execute."""
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": ActionRequest(
                    tool="echo",
                    arguments={"text": "hi"},
                    affects=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
                    human_authorized=True,
                )
            },
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED

    def test_unprotected_action_unaffected_by_constitutional_gate(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo", text="hi")}
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED

"""Tests for the Verified Tool Capability Envelope milestone.

Proves the specific bypass this milestone closes:

    caller affects=∅  +  registered tool declares {P4}
        -> constitutional validation still sees P4 (denied)

    caller affects={P1}  +  tool declares {P4}
        -> constitutional validation sees {P1, P4} (both enforced)

    tool declares ∅  +  caller affects=∅
        -> existing (pre-milestone) behavior, unchanged

The tool's capability declaration is a floor a caller cannot shrink by
omission, never a ceiling that narrows what the caller itself declared.

Also proves the residual, explicitly accepted limitation: a tool's
``protected_constraints`` is type-checked, not independently verified
against what its ``execute()`` actually does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.core.constitution import create_constitution_from_codex
from telemachus.core.types import ActionRequest, ExecutionOutcome
from telemachus.pipeline import CognitivePipeline
from telemachus.tools.base import Tool, ToolCategory, ToolResult
from telemachus.tools.builtin import EchoTool
from telemachus.tools.registry import ToolRegistry

REPO_CODEX = Path(__file__).resolve().parents[1] / "codex"


class _MinimalTool(Tool):
    """The smallest possible Tool subclass, for constructor-level tests."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            name=kwargs.pop("name", "minimal"),
            description="Minimal test tool.",
            category=ToolCategory.PASSIVE,
            **kwargs,
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(output="ok")


class _ResourceTool(Tool):
    """A tool that declares it can touch Resource Authorization (P4)."""

    def __init__(self) -> None:
        super().__init__(
            name="resource_tool",
            description="Declares it can touch Resource Authorization.",
            category=ToolCategory.PASSIVE,
            protected_constraints=frozenset({ProtectedConstraint.RESOURCE_AUTHORIZATION}),
        )

    def validate(self, **kwargs: Any) -> bool:
        return True

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(output="resource action performed")


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(_ResourceTool())
    return registry


def _action(tool: str = "echo", **kwargs: Any) -> ActionRequest:
    arguments = kwargs.pop("arguments", {"text": "hi"} if tool == "echo" else {})
    return ActionRequest(tool=tool, arguments=arguments, **kwargs)


@pytest.fixture
def real_constitution() -> Any:
    return create_constitution_from_codex(REPO_CODEX)


@pytest.fixture
def authorized_pipeline(real_constitution: Any) -> CognitivePipeline:
    """A pipeline with real Codex authority and LIMITED autonomy trust —
    isolates the constitutional gate's effect from the autonomy gate's."""
    pipeline = CognitivePipeline(tool_registry=_registry(), constitution=real_constitution)
    pipeline.autonomy_charter.set_domain_trust("research", 0.5)
    return pipeline


# ---------------------------------------------------------------------------
# 1-4: Tool.protected_constraints — construction, validation, serialization
# ---------------------------------------------------------------------------


class TestToolCapabilityDeclaration:
    def test_defaults_to_empty_frozenset(self) -> None:
        tool = _MinimalTool()
        assert tool.protected_constraints == frozenset()

    def test_accepts_valid_enum_members(self) -> None:
        declared = frozenset(
            {ProtectedConstraint.RESOURCE_AUTHORIZATION, ProtectedConstraint.HUMAN_MEANING}
        )
        tool = _MinimalTool(protected_constraints=declared)
        assert tool.protected_constraints == declared

    def test_rejects_non_protected_constraint_elements(self) -> None:
        with pytest.raises(ValueError, match="ProtectedConstraint"):
            _MinimalTool(protected_constraints=frozenset({"not_an_enum_member"}))  # type: ignore[arg-type]

    def test_rejects_mixed_valid_and_invalid_elements(self) -> None:
        with pytest.raises(ValueError):
            _MinimalTool(
                protected_constraints=frozenset(  # type: ignore[arg-type]
                    {ProtectedConstraint.CONSTITUTION_INTEGRITY, "bogus"}
                )
            )

    def test_does_not_coerce_strings_into_enum_members(self) -> None:
        """Passing the enum's own .value string must not silently work —
        only actual ProtectedConstraint instances are accepted."""
        with pytest.raises(ValueError):
            _MinimalTool(
                protected_constraints=frozenset({"resource_authorization"})  # type: ignore[arg-type]
            )

    def test_to_dict_serializes_canonical_values(self) -> None:
        tool = _ResourceTool()
        data = tool.to_dict()
        assert data["protected_constraints"] == ["resource_authorization"]

    def test_to_dict_empty_declaration_serializes_empty_list(self) -> None:
        tool = _MinimalTool()
        assert tool.to_dict()["protected_constraints"] == []

    def test_sacred_domains_affected_field_untouched(self) -> None:
        """The existing free-form field must remain separate and unaffected."""
        tool = _MinimalTool(sacred_domains_affected=["legacy_domain"])
        assert tool.sacred_domains_affected == ["legacy_domain"]
        assert tool.protected_constraints == frozenset()


# ---------------------------------------------------------------------------
# 5-9: Effective impact = caller declaration UNION tool declaration
# ---------------------------------------------------------------------------


class TestEffectiveConstitutionalImpact:
    def test_tool_declared_constraint_blocks_even_with_empty_affects(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """The core regression: affects=∅ must not bypass what the
        registered tool itself declares."""
        result = authorized_pipeline.process(
            "say hello",
            context={"action": _action("resource_tool", human_authorized=False)},
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert record.violated_constraints == ("resource_authorization",)

    def test_authorized_tool_declared_action_reaches_downstream(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """human_authorized=True clears the constitutional gate and the
        action actually executes — proving PERMITTED still falls through."""
        result = authorized_pipeline.process(
            "say hello",
            context={"action": _action("resource_tool", human_authorized=True)},
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.SUCCEEDED
        assert record.output == "resource action performed"

    def test_tool_with_no_declared_constraints_is_unaffected(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """A tool declaring nothing must not interfere with ordinary
        unprotected execution — echo still just runs."""
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo")}
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED

    def test_caller_and_tool_declarations_both_enforced(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """Caller declares P1, tool declares P4 — both must be reported,
        in deterministic ProtectedConstraint declaration order."""
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": _action(
                    "resource_tool",
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert record.violated_constraints == (
            "constitution_integrity",
            "resource_authorization",
        )

    def test_caller_declaration_enforced_even_when_tool_declares_nothing(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """Caller declares P1 against a tool (echo) that declares ∅ — P1
        must still be enforced; the union must not drop caller intent."""
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": _action(
                    "echo", affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY})
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.DENIED_CONSTITUTION
        assert record.violated_constraints == ("constitution_integrity",)

    def test_no_declarations_anywhere_is_unchanged(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """tool declares ∅, caller declares ∅ — pre-milestone behavior,
        byte for byte."""
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("echo")}
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED


# ---------------------------------------------------------------------------
# 10: Nonexistent tool takes priority over constitutional applicability
# ---------------------------------------------------------------------------


class TestToolNotFoundPrecedence:
    def test_nonexistent_tool_returns_tool_not_found_even_if_protected(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        """Approved decision: if the tool does not exist, TOOL_NOT_FOUND
        is returned first — there is no tool to union capabilities from,
        and no constitutional question to ask about a tool that isn't
        registered."""
        result = authorized_pipeline.process(
            "say hello",
            context={
                "action": _action(
                    "does_not_exist",
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                )
            },
        )
        record = result.metadata["execution"]
        assert record.outcome == ExecutionOutcome.TOOL_NOT_FOUND

    def test_no_registry_configured_still_returns_tool_not_found(self) -> None:
        pipeline = CognitivePipeline()  # no tool_registry, no constitution
        result = pipeline.process(
            "say hello",
            context={
                "action": _action(
                    "resource_tool",
                    affects=frozenset({ProtectedConstraint.CONSTITUTION_INTEGRITY}),
                )
            },
        )
        assert result.metadata["execution"].outcome == ExecutionOutcome.TOOL_NOT_FOUND


# ---------------------------------------------------------------------------
# 13: The original ActionRequest is never mutated
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_original_action_request_is_not_mutated(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        action = _action("resource_tool", human_authorized=False)
        original_affects = action.affects
        original_id = id(action)

        authorized_pipeline.process("say hello", context={"action": action})

        assert id(action) == original_id
        assert action.affects == original_affects
        assert action.affects == frozenset()  # caller declared nothing itself


# ---------------------------------------------------------------------------
# Documentation of the residual limitation this milestone does not solve
# ---------------------------------------------------------------------------


class TestResidualLimitationIsUnsolved:
    """Confirms — rather than merely asserting in prose — that a tool
    author under-declaring its own capabilities still bypasses
    constitutional validation. This is the explicitly deferred residual
    trust assumption: nothing verifies a tool's declaration against what
    its execute() body actually does."""

    def test_under_declared_tool_still_bypasses_validation(
        self, authorized_pipeline: CognitivePipeline
    ) -> None:
        class _UnderDeclaredTool(Tool):
            def __init__(self) -> None:
                super().__init__(
                    name="under_declared",
                    description="Claims no impact but could do anything.",
                    category=ToolCategory.PASSIVE,
                    protected_constraints=frozenset(),  # under-declared
                )

            def validate(self, **kwargs: Any) -> bool:
                return True

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult.ok(output="did something the declaration didn't mention")

        authorized_pipeline.tool_registry.register(_UnderDeclaredTool())  # type: ignore[union-attr]
        result = authorized_pipeline.process(
            "say hello", context={"action": _action("under_declared", human_authorized=False)}
        )
        # No constitutional block occurs, because nothing verifies the
        # declaration against execute() — this is the accepted, documented gap.
        assert result.metadata["execution"].outcome == ExecutionOutcome.SUCCEEDED

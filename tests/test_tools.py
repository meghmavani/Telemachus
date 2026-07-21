"""Tests for the Tool system — base tool, registry, trust tracking."""

from __future__ import annotations

import pytest

from telemachus.tools.base import Tool, ToolCategory, ToolResult
from telemachus.tools.registry import ToolRegistry, ToolStatus

# ---------------------------------------------------------------------------
# Concrete tool for testing
# ---------------------------------------------------------------------------


class _TestTool(Tool):
    """A concrete tool implementation for testing."""

    def execute(self, **kwargs):
        if kwargs.get("fail") or kwargs.get("error"):
            return ToolResult.fail("Intentional failure")
        return ToolResult.ok(kwargs.get("output", "done"))

    def validate(self, **kwargs):
        return not kwargs.get("invalid")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> ToolRegistry:
    """Return a fresh ToolRegistry."""
    return ToolRegistry()


@pytest.fixture
def passive_tool() -> Tool:
    """Return a passive tool for testing."""
    return _TestTool(
        name="test_formatter",
        description="A test formatting tool",
        category=ToolCategory.PASSIVE,
    )


@pytest.fixture
def active_tool() -> Tool:
    """Return an active tool for testing."""
    return _TestTool(
        name="test_file_modifier",
        description="A test file modification tool",
        category=ToolCategory.ACTIVE,
        requires_approval=True,
    )


@pytest.fixture
def autonomous_tool() -> Tool:
    """Return an autonomous tool for testing."""
    return _TestTool(
        name="test_automation",
        description="A test automation tool",
        category=ToolCategory.AUTONOMOUS,
        trust_score=0.2,
    )


@pytest.fixture
def sacred_tool() -> Tool:
    """Return a tool that touches sacred domains."""
    return _TestTool(
        name="test_sacred_tool",
        description="A tool affecting sacred domains",
        category=ToolCategory.ACTIVE,
        sacred_domains_affected=["constitution", "revan_memory"],
    )


@pytest.fixture
def populated_registry(
    registry: ToolRegistry,
    passive_tool: Tool,
    active_tool: Tool,
) -> ToolRegistry:
    """Return a registry with tools registered."""
    registry.register(passive_tool)
    registry.register(active_tool)
    return registry


# ---------------------------------------------------------------------------
# ToolResult tests
# ---------------------------------------------------------------------------


class TestToolResult:
    """Tests for the ToolResult dataclass."""

    def test_result_is_frozen(self) -> None:
        """ToolResult should be frozen."""
        result = ToolResult(success=True, output="test")
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]

    def test_ok_factory(self) -> None:
        """ok() should create a successful result."""
        result = ToolResult.ok("output_data", duration=1.5)
        assert result.success is True
        assert result.output == "output_data"
        assert result.error is None
        assert result.metadata["duration"] == 1.5

    def test_fail_factory(self) -> None:
        """fail() should create a failed result."""
        result = ToolResult.fail("Something went wrong", code=500)
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output is None
        assert result.metadata["code"] == 500

    def test_timestamp_is_set(self) -> None:
        """Timestamp should be auto-set."""
        result = ToolResult.ok("data")
        assert result.timestamp is not None


# ---------------------------------------------------------------------------
# ToolCategory tests
# ---------------------------------------------------------------------------


class TestToolCategory:
    """Tests for the ToolCategory enum."""

    def test_all_categories_exist(self) -> None:
        """All four categories should be defined."""
        assert ToolCategory.PASSIVE.value == "passive"
        assert ToolCategory.ACTIVE.value == "active"
        assert ToolCategory.COGNITIVE.value == "cognitive"
        assert ToolCategory.AUTONOMOUS.value == "autonomous"


# ---------------------------------------------------------------------------
# Tool base class tests
# ---------------------------------------------------------------------------


class TestToolInit:
    """Tests for Tool initialization."""

    def test_create_passive_tool(self) -> None:
        """Should create a passive tool with correct defaults."""
        tool = _TestTool(
            name="test",
            description="A test tool",
            category=ToolCategory.PASSIVE,
        )
        assert tool.name == "test"
        assert tool.description == "A test tool"
        assert tool.category == ToolCategory.PASSIVE
        assert tool.version == "1.0.0"
        assert tool.requires_approval is False
        assert tool.reversible is True
        assert tool.sacred_domains_affected == []
        assert tool.trust_score == 0.5

    def test_create_active_tool(self) -> None:
        """Should create an active tool with approval requirement."""
        tool = _TestTool(
            name="active_tool",
            description="An active tool",
            category=ToolCategory.ACTIVE,
            requires_approval=True,
            reversible=False,
        )
        assert tool.requires_approval is True
        assert tool.reversible is False

    def test_empty_name_raises(self) -> None:
        """Empty tool name should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            _TestTool(name="", description="desc", category=ToolCategory.PASSIVE)

    def test_whitespace_name_raises(self) -> None:
        """Whitespace-only name should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            _TestTool(name="   ", description="desc", category=ToolCategory.PASSIVE)

    def test_trust_score_below_zero_raises(self) -> None:
        """Trust score below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            _TestTool(
                name="test",
                description="desc",
                category=ToolCategory.PASSIVE,
                trust_score=-0.1,
            )

    def test_trust_score_above_one_raises(self) -> None:
        """Trust score above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            _TestTool(
                name="test",
                description="desc",
                category=ToolCategory.PASSIVE,
                trust_score=1.1,
            )

    def test_trust_score_at_boundaries_valid(self) -> None:
        """Trust score at 0.0 and 1.0 should be valid."""
        t1 = _TestTool(
            name="t1", description="d", category=ToolCategory.PASSIVE, trust_score=0.0
        )
        t2 = _TestTool(
            name="t2", description="d", category=ToolCategory.PASSIVE, trust_score=1.0
        )
        assert t1.trust_score == 0.0
        assert t2.trust_score == 1.0

    def test_name_is_stripped(self) -> None:
        """Tool name should be stripped of whitespace."""
        tool = _TestTool(
            name="  my_tool  ", description="desc", category=ToolCategory.PASSIVE
        )
        assert tool.name == "my_tool"


# ---------------------------------------------------------------------------
# Tool trust management tests
# ---------------------------------------------------------------------------


class TestToolTrust:
    """Tests for trust score management."""

    def test_record_success_increases_trust(self, passive_tool: Tool) -> None:
        """Recording success should increase trust."""
        initial = passive_tool.trust_score
        passive_tool.record_success()
        assert passive_tool.trust_score > initial

    def test_record_failure_decreases_trust(self, passive_tool: Tool) -> None:
        """Recording failure should decrease trust."""
        initial = passive_tool.trust_score
        passive_tool.record_failure()
        assert passive_tool.trust_score < initial

    def test_trust_capped_at_one(self, passive_tool: Tool) -> None:
        """Trust should not exceed 1.0."""
        passive_tool.trust_score = 0.99
        for _ in range(100):
            passive_tool.record_success()
        assert passive_tool.trust_score <= 1.0

    def test_trust_floor_at_zero(self, passive_tool: Tool) -> None:
        """Trust should not go below 0.0."""
        passive_tool.trust_score = 0.01
        for _ in range(100):
            passive_tool.record_failure()
        assert passive_tool.trust_score >= 0.0

    def test_get_trust_level_untrusted(self, passive_tool: Tool) -> None:
        """Trust below 0.2 should be 'untrusted'."""
        passive_tool.trust_score = 0.1
        assert passive_tool.get_trust_level() == "untrusted"

    def test_get_trust_level_low(self, passive_tool: Tool) -> None:
        """Trust 0.2-0.4 should be 'low'."""
        passive_tool.trust_score = 0.3
        assert passive_tool.get_trust_level() == "low"

    def test_get_trust_level_neutral(self, passive_tool: Tool) -> None:
        """Trust 0.4-0.6 should be 'neutral'."""
        passive_tool.trust_score = 0.5
        assert passive_tool.get_trust_level() == "neutral"

    def test_get_trust_level_trusted(self, passive_tool: Tool) -> None:
        """Trust 0.6-0.8 should be 'trusted'."""
        passive_tool.trust_score = 0.7
        assert passive_tool.get_trust_level() == "trusted"

    def test_get_trust_level_highly_trusted(self, passive_tool: Tool) -> None:
        """Trust >= 0.8 should be 'highly_trusted'."""
        passive_tool.trust_score = 0.9
        assert passive_tool.get_trust_level() == "highly_trusted"

    def test_execution_count_increments(self, passive_tool: Tool) -> None:
        """Execution count should increment on both success and failure."""
        assert passive_tool.execution_count == 0
        passive_tool.record_success()
        assert passive_tool.execution_count == 1
        passive_tool.record_failure()
        assert passive_tool.execution_count == 2

    def test_failure_count_increments(self, passive_tool: Tool) -> None:
        """Failure count should only increment on failure."""
        assert passive_tool.failure_count == 0
        passive_tool.record_success()
        assert passive_tool.failure_count == 0
        passive_tool.record_failure()
        assert passive_tool.failure_count == 1


# ---------------------------------------------------------------------------
# Tool serialization tests
# ---------------------------------------------------------------------------


class TestToolSerialization:
    """Tests for tool serialization."""

    def test_to_dict(self, passive_tool: Tool) -> None:
        """to_dict should serialize tool metadata."""
        data = passive_tool.to_dict()
        assert data["name"] == "test_formatter"
        assert data["category"] == "passive"
        assert data["version"] == "1.0.0"
        assert "trust_score" in data
        assert "execution_count" in data

    def test_repr(self, passive_tool: Tool) -> None:
        """repr should include name, category, and trust."""
        r = repr(passive_tool)
        assert "test_formatter" in r
        assert "passive" in r


# ---------------------------------------------------------------------------
# ToolRegistry init tests
# ---------------------------------------------------------------------------


class TestRegistryInit:
    """Tests for ToolRegistry initialization."""

    def test_registry_starts_empty(self, registry: ToolRegistry) -> None:
        """A new registry should have no tools."""
        assert registry.get_tool_count() == 0

    def test_stats_empty(self, registry: ToolRegistry) -> None:
        """Stats for empty registry should show zeros."""
        stats = registry.get_stats()
        assert stats["total_tools"] == 0
        assert stats["active_tools"] == 0


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------


class TestRegistration:
    """Tests for tool registration."""

    def test_register_tool(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Should register a tool successfully."""
        registry.register(passive_tool)
        assert registry.get_tool_count() == 1
        assert registry.is_active("test_formatter")

    def test_register_duplicate_raises(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Registering duplicate name should raise ValueError."""
        registry.register(passive_tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(passive_tool)

    def test_unregister_tool(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Should unregister a tool."""
        registry.register(passive_tool)
        assert registry.unregister("test_formatter") is True
        assert registry.get_tool_count() == 0

    def test_unregister_nonexistent(self, registry: ToolRegistry) -> None:
        """Unregistering nonexistent tool should return False."""
        assert registry.unregister("nonexistent") is False

    def test_disable_tool(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Should disable a tool."""
        registry.register(passive_tool)
        assert registry.disable("test_formatter") is True
        assert not registry.is_active("test_formatter")
        assert registry.get_status("test_formatter") == ToolStatus.DISABLED

    def test_enable_tool(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Should re-enable a disabled tool."""
        registry.register(passive_tool)
        registry.disable("test_formatter")
        assert registry.enable("test_formatter") is True
        assert registry.is_active("test_formatter")

    def test_deprecate_tool(
        self, registry: ToolRegistry, passive_tool: Tool
    ) -> None:
        """Should deprecate a tool."""
        registry.register(passive_tool)
        assert registry.deprecate("test_formatter") is True
        assert registry.get_status("test_formatter") == ToolStatus.DEPRECATED

    def test_disable_nonexistent(self, registry: ToolRegistry) -> None:
        """Disabling nonexistent tool should return False."""
        assert registry.disable("nonexistent") is False

    def test_enable_nonexistent(self, registry: ToolRegistry) -> None:
        """Enabling nonexistent tool should return False."""
        assert registry.enable("nonexistent") is False

    def test_deprecate_nonexistent(self, registry: ToolRegistry) -> None:
        """Deprecating nonexistent tool should return False."""
        assert registry.deprecate("nonexistent") is False


# ---------------------------------------------------------------------------
# Tool query tests
# ---------------------------------------------------------------------------


class TestQueries:
    """Tests for tool query methods."""

    def test_get_tool(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should retrieve a tool by name."""
        tool = populated_registry.get_tool("test_formatter")
        assert tool is not None
        assert tool.name == "test_formatter"

    def test_get_tool_not_found(self, registry: ToolRegistry) -> None:
        """Should return None for nonexistent tool."""
        assert registry.get_tool("nonexistent") is None

    def test_get_status(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should return tool status."""
        assert populated_registry.get_status("test_formatter") == ToolStatus.ACTIVE

    def test_get_status_not_found(self, registry: ToolRegistry) -> None:
        """Should return None for nonexistent tool status."""
        assert registry.get_status("nonexistent") is None

    def test_is_active(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should check if tool is active."""
        assert populated_registry.is_active("test_formatter") is True

    def test_list_tools_all(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should list all tools."""
        tools = populated_registry.list_tools()
        assert len(tools) == 2

    def test_list_tools_by_category(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should filter tools by category."""
        passive = populated_registry.list_tools(category=ToolCategory.PASSIVE)
        assert len(passive) == 1
        assert passive[0].category == ToolCategory.PASSIVE

    def test_list_tools_by_status(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should filter tools by status."""
        populated_registry.disable("test_formatter")
        active = populated_registry.list_tools(status=ToolStatus.ACTIVE)
        disabled = populated_registry.list_tools(status=ToolStatus.DISABLED)
        assert len(active) == 1
        assert len(disabled) == 1

    def test_get_tools_by_trust(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should return tools sorted by trust."""
        tools = populated_registry.get_tools_by_trust()
        assert len(tools) == 2
        assert tools[0].trust_score >= tools[1].trust_score

    def test_get_tools_by_trust_min_filter(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should filter by minimum trust."""
        tools = populated_registry.get_tools_by_trust(min_trust=0.9)
        assert len(tools) == 0  # Default trust is 0.5


# ---------------------------------------------------------------------------
# Tool execution tests
# ---------------------------------------------------------------------------


class TestExecution:
    """Tests for tool execution with permission checks."""

    def test_execute_success(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should execute a tool successfully."""
        result = populated_registry.execute("test_formatter", output="hello")
        assert result.success is True
        assert result.output == "hello"

    def test_execute_not_found(self, registry: ToolRegistry) -> None:
        """Executing nonexistent tool should return failure."""
        result = registry.execute("nonexistent")
        assert result.success is False
        assert "not found" in result.error

    def test_execute_disabled(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Executing disabled tool should return failure."""
        populated_registry.disable("test_formatter")
        result = populated_registry.execute("test_formatter")
        assert result.success is False
        assert "not active" in result.error.lower()

    def test_execute_validation_fails(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Validation failure should prevent execution."""
        result = populated_registry.execute("test_formatter", invalid=True)
        assert result.success is False
        assert "validation" in result.error.lower()

    def test_execute_tool_error(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Tool execution error should be caught."""
        result = populated_registry.execute("test_formatter", error=True)
        assert result.success is False
        assert "Intentional failure" in result.error

    def test_execute_updates_trust(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Successful execution should update trust."""
        tool = populated_registry.get_tool("test_formatter")
        initial = tool.trust_score
        populated_registry.execute("test_formatter")
        assert tool.trust_score > initial

    def test_execute_failure_updates_trust(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Failed execution should decrease trust."""
        tool = populated_registry.get_tool("test_formatter")
        initial = tool.trust_score
        populated_registry.execute("test_formatter", error=True)
        assert tool.trust_score < initial

    def test_execute_without_permission_check(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should execute when permission checks are skipped."""
        result = populated_registry.execute(
            "test_formatter", require_permission=False, output="ok"
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# Permission check tests
# ---------------------------------------------------------------------------


class TestPermissionChecks:
    """Tests for tool permission checking."""

    def test_passive_tool_allowed(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Passive tools should be allowed by default."""
        perm = populated_registry.check_permission("test_formatter")
        assert perm["allowed"] is True

    def test_approval_required_tool_blocked(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Tools requiring approval should be blocked."""
        perm = populated_registry.check_permission("test_file_modifier")
        assert perm["allowed"] is False
        assert perm["requires_approval"] is True

    def test_sacred_domain_tool_blocked(
        self, registry: ToolRegistry, sacred_tool: Tool
    ) -> None:
        """Tools touching sacred domains should be blocked."""
        registry.register(sacred_tool)
        perm = registry.check_permission("test_sacred_tool")
        assert perm["allowed"] is False
        assert "sacred" in perm["reason"].lower()

    def test_autonomous_low_trust_blocked(
        self, registry: ToolRegistry, autonomous_tool: Tool
    ) -> None:
        """Autonomous tools with low trust should be blocked."""
        registry.register(autonomous_tool)
        perm = registry.check_permission("test_automation")
        assert perm["allowed"] is False
        assert "trust" in perm["reason"].lower()

    def test_nonexistent_tool_permission(self, registry: ToolRegistry) -> None:
        """Permission check for nonexistent tool should deny."""
        perm = registry.check_permission("nonexistent")
        assert perm["allowed"] is False

    def test_disabled_tool_permission(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Disabled tools should be denied permission."""
        populated_registry.disable("test_formatter")
        perm = populated_registry.check_permission("test_formatter")
        assert perm["allowed"] is False


# ---------------------------------------------------------------------------
# Execution log tests
# ---------------------------------------------------------------------------


class TestExecutionLog:
    """Tests for execution logging."""

    def test_log_records_execution(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Execution should be logged."""
        populated_registry.execute("test_formatter")
        log = populated_registry.get_execution_log()
        assert len(log) == 1
        assert log[0]["tool"] == "test_formatter"
        assert log[0]["success"] is True

    def test_log_records_failure(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Failed execution should be logged."""
        populated_registry.execute("test_formatter", error=True)
        log = populated_registry.get_execution_log()
        assert log[0]["success"] is False

    def test_log_filtered_by_tool(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Log should be filterable by tool name."""
        populated_registry.execute("test_formatter")
        populated_registry.execute("test_file_modifier")
        log = populated_registry.get_execution_log(tool_name="test_formatter")
        assert len(log) == 1
        assert log[0]["tool"] == "test_formatter"

    def test_log_respects_limit(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Log should respect the limit parameter."""
        for _ in range(5):
            populated_registry.execute("test_formatter")
        log = populated_registry.get_execution_log(limit=2)
        assert len(log) == 2

    def test_execution_stats(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Execution stats should aggregate correctly."""
        populated_registry.execute("test_formatter")
        populated_registry.execute("test_formatter", error=True)
        stats = populated_registry.get_execution_stats()
        assert stats["total_executions"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 0.5


# ---------------------------------------------------------------------------
# Registry stats tests
# ---------------------------------------------------------------------------


class TestRegistryStats:
    """Tests for registry statistics."""

    def test_stats_reflect_state(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Stats should reflect current registry state."""
        stats = populated_registry.get_stats()
        assert stats["total_tools"] == 2
        assert stats["active_tools"] == 2
        assert stats["disabled_tools"] == 0
        assert stats["deprecated_tools"] == 0

    def test_stats_by_category(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Stats should break down by category."""
        stats = populated_registry.get_stats()
        assert stats["by_category"]["passive"] == 1
        assert stats["by_category"]["active"] == 1

    def test_stats_after_disable(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Stats should update after disabling a tool."""
        populated_registry.disable("test_formatter")
        stats = populated_registry.get_stats()
        assert stats["active_tools"] == 1
        assert stats["disabled_tools"] == 1


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


class TestPersistence:
    """Tests for registry persistence helpers."""

    def test_to_memory_content(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should serialize to JSON."""
        content = populated_registry.to_memory_content()
        assert isinstance(content, str)
        assert "test_formatter" in content

    def test_to_memory_index_keys(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Should return index keys."""
        keys = populated_registry.to_memory_index_keys()
        assert keys["type"] == "tool_registry"
        assert keys["tool_count"] == "2"

    def test_from_memory_content(self) -> None:
        """Should restore registry from JSON."""
        registry = ToolRegistry.from_memory_content('{"tools": []}')
        assert registry.get_tool_count() == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_tool_name(self, registry: ToolRegistry) -> None:
        """Very long tool names should work."""
        long_name = "a" * 200
        tool = _TestTool(
            name=long_name, description="desc", category=ToolCategory.PASSIVE
        )
        registry.register(tool)
        assert registry.get_tool(long_name) is not None

    def test_unicode_tool_name(self, registry: ToolRegistry) -> None:
        """Unicode tool names should work."""
        tool = _TestTool(
            name="测试工具", description="A test tool", category=ToolCategory.PASSIVE
        )
        registry.register(tool)
        assert registry.get_tool("测试工具") is not None

    def test_multiple_registrations_independent(
        self, registry: ToolRegistry
    ) -> None:
        """Multiple registrations should be independent."""
        t1 = _TestTool(name="t1", description="d", category=ToolCategory.PASSIVE)
        t2 = _TestTool(name="t2", description="d", category=ToolCategory.ACTIVE)
        registry.register(t1)
        registry.register(t2)
        assert registry.get_tool_count() == 2

    def test_execute_with_kwargs(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Execute should pass kwargs to the tool."""
        result = populated_registry.execute(
            "test_formatter", output="custom_output"
        )
        assert result.output == "custom_output"

    def test_empty_execution_log(self, registry: ToolRegistry) -> None:
        """Empty registry should have empty execution log."""
        log = registry.get_execution_log()
        assert log == []

    def test_execution_stats_empty(self, registry: ToolRegistry) -> None:
        """Empty registry should have zero execution stats."""
        stats = registry.get_execution_stats()
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestToolIntegration:
    """Integration tests for the tool system."""

    def test_full_tool_lifecycle(self, registry: ToolRegistry) -> None:
        """A tool should flow through register → execute → disable → unregister."""
        tool = _TestTool(
            name="lifecycle_tool",
            description="Testing lifecycle",
            category=ToolCategory.PASSIVE,
        )

        # Register
        registry.register(tool)
        assert registry.get_tool_count() == 1

        # Execute
        result = registry.execute("lifecycle_tool", output="step1")
        assert result.success is True

        # Disable
        registry.disable("lifecycle_tool")
        assert not registry.is_active("lifecycle_tool")

        # Enable
        registry.enable("lifecycle_tool")
        assert registry.is_active("lifecycle_tool")

        # Deprecate
        registry.deprecate("lifecycle_tool")
        assert registry.get_status("lifecycle_tool") == ToolStatus.DEPRECATED

        # Unregister
        registry.unregister("lifecycle_tool")
        assert registry.get_tool_count() == 0

    def test_trust_accumulates_across_executions(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Trust should accumulate across multiple successful executions."""
        tool = populated_registry.get_tool("test_formatter")
        initial = tool.trust_score
        for _ in range(10):
            populated_registry.execute("test_formatter")
        assert tool.trust_score > initial

    def test_permission_blocks_execution(
        self, populated_registry: ToolRegistry
    ) -> None:
        """Permission-denied tools should not execute."""
        result = populated_registry.execute("test_file_modifier")
        assert result.success is False
        assert "denied" in result.error.lower() or "approval" in result.error.lower()

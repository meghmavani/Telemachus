"""Tool Registry — centralized tool management with trust tracking and governance.

The registry is the single source of truth for all tools. It enforces:
- Unique tool names
- Permission checks before execution
- Trust score tracking across executions
- Sacred domain constraint enforcement
- Tool lifecycle management (register, enable, disable, deprecate, remove)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from telemachus.tools.base import Tool, ToolCategory, ToolResult

logger = logging.getLogger("telemachus.tools.registry")


# ---------------------------------------------------------------------------
# Tool status enum
# ---------------------------------------------------------------------------


class ToolStatus:
    """Status constants for tools in the registry."""

    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"

    @classmethod
    def all_statuses(cls) -> list[str]:
        """Return all valid status values."""
        return [cls.ACTIVE, cls.DISABLED, cls.DEPRECATED]


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Central registry for all Telemachus tools.

    The registry manages tool registration, execution with permission checks,
    trust tracking, and lifecycle. It enforces the principle that capability
    does not imply permission — every tool execution must pass governance
    checks.

    Attributes:
        _tools: Internal mapping of tool name to (tool_instance, status).
        _execution_log: History of all tool executions.
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, tuple[Tool, str]] = {}
        self._execution_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Registration and lifecycle
    # ------------------------------------------------------------------

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: The tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = (tool, ToolStatus.ACTIVE)
        logger.info(
            "Tool registered: %s (category=%s, version=%s)",
            tool.name,
            tool.category.value,
            tool.version,
        )

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: The tool name to remove.

        Returns:
            True if the tool was removed, False if not found.
        """
        if name not in self._tools:
            logger.warning("Tool not found for unregistration: %s", name)
            return False
        del self._tools[name]
        logger.info("Tool unregistered: %s", name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a tool without removing it.

        Args:
            name: The tool name to disable.

        Returns:
            True if disabled, False if not found.
        """
        if name not in self._tools:
            logger.warning("Tool not found for disable: %s", name)
            return False
        tool, _ = self._tools[name]
        self._tools[name] = (tool, ToolStatus.DISABLED)
        logger.info("Tool disabled: %s", name)
        return True

    def enable(self, name: str) -> bool:
        """Re-enable a disabled tool.

        Args:
            name: The tool name to enable.

        Returns:
            True if enabled, False if not found.
        """
        if name not in self._tools:
            logger.warning("Tool not found for enable: %s", name)
            return False
        tool, _ = self._tools[name]
        self._tools[name] = (tool, ToolStatus.ACTIVE)
        logger.info("Tool enabled: %s", name)
        return True

    def deprecate(self, name: str) -> bool:
        """Mark a tool as deprecated.

        Args:
            name: The tool name to deprecate.

        Returns:
            True if deprecated, False if not found.
        """
        if name not in self._tools:
            logger.warning("Tool not found for deprecation: %s", name)
            return False
        tool, _ = self._tools[name]
        self._tools[name] = (tool, ToolStatus.DEPRECATED)
        logger.info("Tool deprecated: %s", name)
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: The tool name.

        Returns:
            The Tool instance, or None if not found.
        """
        entry = self._tools.get(name)
        return entry[0] if entry else None

    def get_status(self, name: str) -> str | None:
        """Get the status of a tool.

        Args:
            name: The tool name.

        Returns:
            Status string, or None if not found.
        """
        entry = self._tools.get(name)
        return entry[1] if entry else None

    def is_active(self, name: str) -> bool:
        """Check if a tool is active (registered and not disabled/deprecated).

        Args:
            name: The tool name.

        Returns:
            True if the tool is active.
        """
        return self.get_status(name) == ToolStatus.ACTIVE

    def list_tools(
        self,
        category: ToolCategory | None = None,
        status: str | None = None,
    ) -> list[Tool]:
        """List tools, optionally filtered by category and status.

        Args:
            category: Filter by ToolCategory.
            status: Filter by status (active, disabled, deprecated).

        Returns:
            List of matching Tool instances.
        """
        result: list[Tool] = []
        for tool, tool_status in self._tools.values():
            if status is not None and tool_status != status:
                continue
            if category is not None and tool.category != category:
                continue
            result.append(tool)
        return result

    def get_tools_by_trust(self, min_trust: float = 0.0) -> list[Tool]:
        """Get tools sorted by trust score (highest first).

        Args:
            min_trust: Minimum trust score filter.

        Returns:
            Sorted list of Tool instances.
        """
        tools = [t for t, _ in self._tools.values() if t.trust_score >= min_trust]
        return sorted(tools, key=lambda t: t.trust_score, reverse=True)

    def get_tool_count(self) -> int:
        """Return the total number of registered tools."""
        return len(self._tools)

    # ------------------------------------------------------------------
    # Execution with permission checks
    # ------------------------------------------------------------------

    def execute(
        self,
        name: str,
        *,
        require_permission: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool with permission checks.

        Args:
            name: The tool name to execute.
            require_permission: Whether to enforce permission checks.
            **kwargs: Parameters passed to the tool's execute method.

        Returns:
            ToolResult from the execution.

        Raises:
            ValueError: If the tool is not found or not active.
        """
        tool = self.get_tool(name)
        if tool is None:
            msg = f"Tool '{name}' not found in registry"
            logger.error(msg)
            return ToolResult.fail(msg)

        if not self.is_active(name):
            msg = f"Tool '{name}' is not active (status: {self.get_status(name)})"
            logger.warning(msg)
            return ToolResult.fail(msg)

        # Permission check
        if require_permission:
            permission = self.check_permission(name)
            if not permission["allowed"]:
                msg = f"Tool '{name}' execution denied: {permission['reason']}"
                logger.warning(msg)
                return ToolResult.fail(msg, permission_check=permission)

        # Validate preconditions
        try:
            if not tool.validate(**kwargs):
                msg = f"Tool '{name}' validation failed"
                logger.warning(msg)
                return ToolResult.fail(msg)
        except Exception as e:
            msg = f"Tool '{name}' validation error: {e}"
            logger.error(msg)
            return ToolResult.fail(msg)

        # Execute
        try:
            result = tool.execute(**kwargs)
        except Exception as e:
            msg = f"Tool '{name}' execution error: {e}"
            logger.error(msg, exc_info=True)
            tool.record_failure()
            self._log_execution(name, False, str(e), kwargs)
            return ToolResult.fail(msg)

        # Record outcome
        if result.success:
            tool.record_success()
        else:
            tool.record_failure()

        self._log_execution(name, result.success, result.error, kwargs)
        return result

    def check_permission(self, name: str) -> dict[str, Any]:
        """Check whether a tool can be executed.

        Evaluates:
        - Whether the tool exists and is active
        - Whether it requires explicit approval
        - Whether it touches sacred domains
        - Trust score adequacy

        Args:
            name: The tool name.

        Returns:
            Dict with 'allowed' (bool) and 'reason' (str).
        """
        tool = self.get_tool(name)
        if tool is None:
            return {"allowed": False, "reason": f"Tool '{name}' not found"}

        if not self.is_active(name):
            return {
                "allowed": False,
                "reason": f"Tool '{name}' is {self.get_status(name)}",
            }

        # Sacred domain check
        if tool.sacred_domains_affected:
            return {
                "allowed": False,
                "reason": (
                    f"Tool '{name}' affects sacred domains: "
                    f"{', '.join(tool.sacred_domains_affected)}. "
                    f"Explicit approval required."
                ),
                "requires_approval": True,
                "sacred_domains": tool.sacred_domains_affected,
            }

        # Approval requirement
        if tool.requires_approval:
            return {
                "allowed": False,
                "reason": f"Tool '{name}' requires explicit approval.",
                "requires_approval": True,
            }

        # Trust check for autonomous tools
        if tool.category == ToolCategory.AUTONOMOUS and tool.trust_score < 0.3:
            return {
                "allowed": False,
                "reason": (
                    f"Autonomous tool '{name}' has insufficient trust "
                    f"({tool.trust_score:.2f})."
                ),
            }

        return {"allowed": True, "reason": "Permission granted"}

    # ------------------------------------------------------------------
    # Execution log
    # ------------------------------------------------------------------

    def _log_execution(
        self,
        name: str,
        success: bool,
        error: str | None,
        context: Any,
    ) -> None:
        """Record an execution in the log."""
        self._execution_log.append({
            "tool": name,
            "success": success,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def get_execution_log(
        self,
        tool_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve execution history, optionally filtered by tool.

        Args:
            tool_name: Filter by tool name.
            limit: Maximum entries to return.

        Returns:
            List of execution log entries.
        """
        log = self._execution_log
        if tool_name:
            log = [e for e in log if e["tool"] == tool_name]
        return log[-limit:]

    def get_execution_stats(self) -> dict[str, Any]:
        """Return aggregate execution statistics.

        Returns:
            Dict with total_executions, success_count, failure_count,
            success_rate, and per-tool breakdown.
        """
        total = len(self._execution_log)
        successes = sum(1 for e in self._execution_log if e["success"])
        failures = total - successes

        per_tool: dict[str, dict[str, int]] = {}
        for entry in self._execution_log:
            name = entry["tool"]
            if name not in per_tool:
                per_tool[name] = {"total": 0, "successes": 0, "failures": 0}
            per_tool[name]["total"] += 1
            if entry["success"]:
                per_tool[name]["successes"] += 1
            else:
                per_tool[name]["failures"] += 1

        return {
            "total_executions": total,
            "success_count": successes,
            "failure_count": failures,
            "success_rate": successes / max(total, 1),
            "per_tool": per_tool,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return comprehensive registry statistics.

        Returns:
            Dict with tool counts by category, status, trust levels, etc.
        """
        tools = [t for t, _ in self._tools.values()]
        statuses = [s for _, s in self._tools.values()]

        return {
            "total_tools": len(tools),
            "active_tools": statuses.count(ToolStatus.ACTIVE),
            "disabled_tools": statuses.count(ToolStatus.DISABLED),
            "deprecated_tools": statuses.count(ToolStatus.DEPRECATED),
            "by_category": {
                cat.value: sum(1 for t in tools if t.category == cat)
                for cat in ToolCategory
            },
            "average_trust": (
                sum(t.trust_score for t in tools) / len(tools) if tools else 0.0
            ),
            "total_executions": sum(t.execution_count for t in tools),
            "total_failures": sum(t.failure_count for t in tools),
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize the registry to JSON for memory storage.

        Note: This serializes metadata only, not executable tool logic.
        Tools must be re-registered from code on deserialization.

        Returns:
            JSON string of registry metadata.
        """
        data = {
            "tools": [
                {
                    **tool.to_dict(),
                    "status": status,
                }
                for tool, status in self._tools.values()
            ],
            "execution_log": self._execution_log[-1000:],  # Keep last 1000 entries
        }
        return json.dumps(data, indent=2)

    def to_memory_index_keys(self) -> dict[str, str]:
        """Return index keys for memory storage.

        Returns:
            Dict of key-value pairs for the memory index.
        """
        return {
            "type": "tool_registry",
            "tool_count": str(len(self._tools)),
        }

    @classmethod
    def from_memory_content(cls, content: str) -> ToolRegistry:
        """Restore registry metadata from JSON.

        Note: This restores metadata only. Tool instances must be
        re-registered from code since executable logic cannot be serialized.

        Args:
            content: JSON string from to_memory_content().

        Returns:
            A new ToolRegistry with restored metadata.
        """
        registry = cls()
        # Metadata restoration is informational only — actual tool
        # instances must be re-registered by the application.
        logger.info(
            "Registry metadata loaded (%d tools in snapshot)",
            len(json.loads(content).get("tools", [])),
        )
        return registry

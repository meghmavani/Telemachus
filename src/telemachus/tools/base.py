"""Base tool class — the foundation for all Telemachus tools.

Every tool must have a clearly defined purpose, bounded scope of authority,
predictable behavior, transparent operation, and measurable outputs.

Tools are categorized as:
- PASSIVE: do not affect external systems (formatters, analyzers, validators)
- ACTIVE: perform external actions (file modification, automation)
- COGNITIVE: enhance reasoning without direct action (research, comparison)
- AUTONOMOUS: execute workflows independently within defined boundaries
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("telemachus.tools.base")


# ---------------------------------------------------------------------------
# Tool category enum
# ---------------------------------------------------------------------------


class ToolCategory(Enum):
    """Classification of tool types by their scope of action."""

    PASSIVE = "passive"  # No external effects (formatters, analyzers)
    ACTIVE = "active"  # External actions (file modification, automation)
    COGNITIVE = "cognitive"  # Reasoning enhancement (research, comparison)
    AUTONOMOUS = "autonomous"  # Independent workflows within boundaries


# ---------------------------------------------------------------------------
# Tool result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolResult:
    """The result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully.
        output: The primary output of the tool (string, dict, etc.).
        error: Error message if execution failed.
        metadata: Additional execution context (duration, resources used, etc.).
        timestamp: When the execution completed.
    """

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def ok(cls, output: Any, **metadata: Any) -> ToolResult:
        """Create a successful result."""
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> ToolResult:
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)


# ---------------------------------------------------------------------------
# Base Tool abstract class
# ---------------------------------------------------------------------------


class Tool(ABC):
    """Abstract base class for all Telemachus tools.

    Every tool must implement:
    - execute(): the core tool logic
    - validate(): pre-execution validation

    Tools carry metadata about their purpose, category, risk profile, and
    trustworthiness. The registry uses this metadata for permission checks
    and trust tracking.

    Attributes:
        name: Unique tool identifier.
        description: Human-readable purpose statement.
        category: ToolCategory classification.
        version: Semantic version string.
        requires_approval: Whether this tool needs explicit approval.
        reversible: Whether tool actions can be undone.
        sacred_domains_affected: Which sacred domains this tool touches.
        trust_score: Accumulated trust from successful executions (0.0-1.0).
        execution_count: Total number of executions.
        failure_count: Total number of failures.
    """

    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    requires_approval: bool = False
    reversible: bool = True
    sacred_domains_affected: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    execution_count: int = 0
    failure_count: int = 0

    def __init__(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        version: str = "1.0.0",
        requires_approval: bool = False,
        reversible: bool = True,
        sacred_domains_affected: list[str] | None = None,
        trust_score: float = 0.5,
    ) -> None:
        """Initialize a tool with its core metadata.

        Args:
            name: Unique tool identifier.
            description: Human-readable purpose statement.
            category: ToolCategory classification.
            version: Semantic version string.
            requires_approval: Whether explicit approval is needed.
            reversible: Whether actions can be undone.
            sacred_domains_affected: Sacred domains this tool interacts with.
            trust_score: Initial trust score (0.0-1.0).

        Raises:
            ValueError: If name is empty or trust_score is out of range.
        """
        if not name or not name.strip():
            raise ValueError("Tool name must not be empty")
        if not 0.0 <= trust_score <= 1.0:
            raise ValueError("Trust score must be between 0.0 and 1.0")

        self.name = name.strip()
        self.description = description
        self.category = category
        self.version = version
        self.requires_approval = requires_approval
        self.reversible = reversible
        self.sacred_domains_affected = sacred_domains_affected or []
        self.trust_score = trust_score
        self.execution_count = 0
        self.failure_count = 0

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool's core logic.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and output.
        """
        ...

    @abstractmethod
    def validate(self, **kwargs: Any) -> bool:
        """Validate that preconditions are met before execution.

        Args:
            **kwargs: Parameters to validate.

        Returns:
            True if validation passes, False otherwise.
        """
        ...

    # ------------------------------------------------------------------
    # Trust management
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record a successful execution, increasing trust."""
        self.execution_count += 1
        # Trust increases asymptotically toward 1.0
        self.trust_score = min(1.0, self.trust_score + 0.05 * (1.0 - self.trust_score))
        logger.debug(
            "Tool '%s' trust increased to %.3f (%d executions)",
            self.name,
            self.trust_score,
            self.execution_count,
        )

    def record_failure(self) -> None:
        """Record a failed execution, decreasing trust."""
        self.failure_count += 1
        self.execution_count += 1
        # Trust decreases proportionally to failure ratio
        penalty = 0.1 * (self.failure_count / max(self.execution_count, 1))
        self.trust_score = max(0.0, self.trust_score - penalty)
        logger.warning(
            "Tool '%s' trust decreased to %.3f (%d failures)",
            self.name,
            self.trust_score,
            self.failure_count,
        )

    def get_trust_level(self) -> str:
        """Return a human-readable trust level based on score.

        Returns:
            One of: 'untrusted', 'low', 'neutral', 'trusted', 'highly_trusted'.
        """
        if self.trust_score < 0.2:
            return "untrusted"
        if self.trust_score < 0.4:
            return "low"
        if self.trust_score < 0.6:
            return "neutral"
        if self.trust_score < 0.8:
            return "trusted"
        return "highly_trusted"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize tool metadata to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "requires_approval": self.requires_approval,
            "reversible": self.reversible,
            "sacred_domains_affected": self.sacred_domains_affected,
            "trust_score": self.trust_score,
            "execution_count": self.execution_count,
            "failure_count": self.failure_count,
        }

    def __repr__(self) -> str:
        return (
            f"Tool(name={self.name!r}, category={self.category.value}, "
            f"trust={self.trust_score:.2f})"
        )

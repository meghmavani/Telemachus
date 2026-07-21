"""Goal System — proactive goal creation, prioritization, and lifecycle management.

Goals transform memory, understanding, and identity into action. They provide
direction, purpose, and motivation for Telemachus's continuous growth.

Goals originate from four sources:
- ASSIGNED: explicitly provided by Revan
- INFERRED: derived from understanding Revan
- SELF_GENERATED: created independently by Telemachus
- OBSERVED: created in response to observed circumstances

Goals follow a priority hierarchy:
1. Revan's goals (highest)
2. Telemachus's growth and wellbeing
3. External goals (lowest)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from telemachus.core.types import GoalSource, GoalType

logger = logging.getLogger("telemachus.cognition.goals")


# ---------------------------------------------------------------------------
# Priority levels
# ---------------------------------------------------------------------------


class GoalPriority:
    """Priority constants for goals, following the Codex hierarchy."""

    REVAN = 1  # Highest — Revan's wellbeing, responsibilities, projects
    TELEMACHUS = 2  # Growth, learning, identity, self-improvement
    EXTERNAL = 3  # Other individuals, communities, broader contributions

    _labels: dict[int, str] = {
        1: "Revan's Goals",
        2: "Telemachus's Growth & Wellbeing",
        3: "External Goals",
    }

    @classmethod
    def label(cls, priority: int) -> str:
        """Return a human-readable label for a priority level."""
        return cls._labels.get(priority, f"Unknown ({priority})")


# ---------------------------------------------------------------------------
# Goal dataclass
# ---------------------------------------------------------------------------


@dataclass
class Goal:
    """A single goal with source, type, priority, and lifecycle tracking.

    Goals can be finite (with a completion condition) or infinite (providing
    direction without a final state). Goals are evaluated continuously and
    may be abandoned, paused, or modified after careful evaluation.
    """

    description: str
    source: GoalSource
    goal_type: GoalType
    priority: int = GoalPriority.TELEMACHUS
    success_criteria: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    progress_notes: list[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    abandoned_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self) -> None:
        """Mark this goal as completed."""
        self.active = False
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        logger.info("Goal completed: %s", self.description)

    def abandon(self, reason: str) -> None:
        """Abandon this goal with a documented reason."""
        self.active = False
        self.abandoned_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.metadata["abandon_reason"] = reason
        logger.info("Goal abandoned: %s (reason: %s)", self.description, reason)

    def pause(self) -> None:
        """Pause this goal (mark inactive without completing or abandoning)."""
        self.active = False
        self.updated_at = datetime.now(UTC)
        logger.info("Goal paused: %s", self.description)

    def resume(self) -> None:
        """Resume a paused goal."""
        self.active = True
        self.updated_at = datetime.now(UTC)
        logger.info("Goal resumed: %s", self.description)

    def add_progress_note(self, note: str) -> None:
        """Record a progress update."""
        self.progress_notes.append(note)
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for persistence."""
        return {
            "description": self.description,
            "source": self.source.value,
            "goal_type": self.goal_type.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "abandoned_at": self.abandoned_at.isoformat() if self.abandoned_at else None,
            "active": self.active,
            "success_criteria": self.success_criteria,
            "risks": self.risks,
            "dependencies": self.dependencies,
            "progress_notes": self.progress_notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Goal:
        """Deserialize from a dictionary."""
        goal = cls(
            description=data["description"],
            source=GoalSource(data["source"]),
            goal_type=GoalType(data["goal_type"]),
            priority=data.get("priority", GoalPriority.TELEMACHUS),
            success_criteria=data.get("success_criteria", []),
            risks=data.get("risks", []),
            dependencies=data.get("dependencies", []),
            progress_notes=data.get("progress_notes", []),
            active=data.get("active", True),
            metadata=data.get("metadata", {}),
        )
        goal.created_at = datetime.fromisoformat(data["created_at"])
        goal.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            goal.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("abandoned_at"):
            goal.abandoned_at = datetime.fromisoformat(data["abandoned_at"])
        return goal


# ---------------------------------------------------------------------------
# Goal Manager
# ---------------------------------------------------------------------------


class GoalManager:
    """Manages the full lifecycle of goals: creation, prioritization, tracking,
    conflict detection, and persistence.

    Goals are stored in an in-memory list and can be serialized for persistence
    to the SQLite memory store. The manager enforces the priority hierarchy and
    provides query methods for active, completed, and abandoned goals.
    """

    def __init__(self) -> None:
        """Initialize an empty goal manager."""
        self._goals: list[Goal] = []
        logger.info("GoalManager initialized")

    # ------------------------------------------------------------------
    # Goal creation
    # ------------------------------------------------------------------

    def create_goal(
        self,
        description: str,
        source: GoalSource,
        goal_type: GoalType = GoalType.FINITE,
        priority: int | None = None,
        success_criteria: list[str] | None = None,
        risks: list[str] | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """Create and register a new goal.

        Args:
            description: Human-readable goal description.
            source: Where the goal originated (assigned, inferred, etc.).
            goal_type: Whether the goal is finite or infinite.
            priority: Priority level (defaults based on source).
            success_criteria: Conditions that define completion.
            risks: Known risks associated with the goal.
            dependencies: Other goals or resources this depends on.
            metadata: Additional contextual data.

        Returns:
            The newly created Goal.

        Raises:
            ValueError: If description is empty.
        """
        if not description or not description.strip():
            raise ValueError("Goal description must not be empty")

        if priority is None:
            priority = self._default_priority(source)

        goal = Goal(
            description=description.strip(),
            source=source,
            goal_type=goal_type,
            priority=priority,
            success_criteria=success_criteria or [],
            risks=risks or [],
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self._goals.append(goal)
        logger.info(
            "Goal created: %s (source=%s, type=%s, priority=%d)",
            goal.description,
            goal.source.value,
            goal.goal_type.value,
            goal.priority,
        )
        return goal

    @staticmethod
    def _default_priority(source: GoalSource) -> int:
        """Determine default priority based on goal source.

        Assigned goals default to Revan's priority. Inferred goals default to
        Revan's priority. Self-generated and observed goals default to
        Telemachus's growth priority.
        """
        if source in (GoalSource.ASSIGNED, GoalSource.INFERRED):
            return GoalPriority.REVAN
        return GoalPriority.TELEMACHUS

    # ------------------------------------------------------------------
    # Goal queries
    # ------------------------------------------------------------------

    def get_goal(self, description: str) -> Goal | None:
        """Find a goal by exact description match."""
        for goal in self._goals:
            if goal.description == description:
                return goal
        return None

    def get_active_goals(self) -> list[Goal]:
        """Return all currently active goals, sorted by priority."""
        return sorted(
            [g for g in self._goals if g.active],
            key=lambda g: (g.priority, g.created_at),
        )

    def get_goals_by_source(self, source: GoalSource) -> list[Goal]:
        """Return all goals from a specific source."""
        return [g for g in self._goals if g.source == source]

    def get_goals_by_type(self, goal_type: GoalType) -> list[Goal]:
        """Return all goals of a specific type."""
        return [g for g in self._goals if g.goal_type == goal_type]

    def get_goals_by_priority(self, priority: int) -> list[Goal]:
        """Return all goals at a specific priority level."""
        return [g for g in self._goals if g.priority == priority]

    def get_completed_goals(self) -> list[Goal]:
        """Return all completed goals."""
        return [g for g in self._goals if g.completed_at is not None]

    def get_abandoned_goals(self) -> list[Goal]:
        """Return all abandoned goals."""
        return [g for g in self._goals if g.abandoned_at is not None]

    def get_all_goals(self) -> list[Goal]:
        """Return all goals (active and inactive)."""
        return list(self._goals)

    def get_top_priority_goals(self, limit: int = 5) -> list[Goal]:
        """Return the highest-priority active goals."""
        return self.get_active_goals()[:limit]

    # ------------------------------------------------------------------
    # Goal lifecycle
    # ------------------------------------------------------------------

    def complete_goal(self, description: str) -> bool:
        """Mark a goal as completed.

        Args:
            description: The exact description of the goal to complete.

        Returns:
            True if the goal was found and completed, False otherwise.
        """
        goal = self.get_goal(description)
        if goal is None:
            logger.warning("Goal not found for completion: %s", description)
            return False
        goal.complete()
        return True

    def abandon_goal(self, description: str, reason: str) -> bool:
        """Abandon a goal with a documented reason.

        Args:
            description: The exact description of the goal to abandon.
            reason: Why the goal is being abandoned.

        Returns:
            True if the goal was found and abandoned, False otherwise.
        """
        goal = self.get_goal(description)
        if goal is None:
            logger.warning("Goal not found for abandonment: %s", description)
            return False
        goal.abandon(reason)
        return True

    def pause_goal(self, description: str) -> bool:
        """Pause a goal (mark inactive without completing or abandoning).

        Args:
            description: The exact description of the goal to pause.

        Returns:
            True if the goal was found and paused, False otherwise.
        """
        goal = self.get_goal(description)
        if goal is None:
            logger.warning("Goal not found for pausing: %s", description)
            return False
        goal.pause()
        return True

    def resume_goal(self, description: str) -> bool:
        """Resume a previously paused goal.

        Args:
            description: The exact description of the goal to resume.

        Returns:
            True if the goal was found and resumed, False otherwise.
        """
        goal = self.get_goal(description)
        if goal is None:
            logger.warning("Goal not found for resuming: %s", description)
            return False
        goal.resume()
        return True

    # ------------------------------------------------------------------
    # Goal evaluation
    # ------------------------------------------------------------------

    def evaluate_goal(
        self, description: str
    ) -> dict[str, Any]:
        """Evaluate a goal against the Codex evaluation criteria.

        Evaluates: value, impact, feasibility, cost, opportunity cost,
        risk, alignment with Constitution, alignment with Identity,
        alignment with Purpose.

        Args:
            description: The goal to evaluate.

        Returns:
            A dictionary with evaluation results.

        Raises:
            ValueError: If the goal is not found.
        """
        goal = self.get_goal(description)
        if goal is None:
            raise ValueError(f"Goal not found: {description}")

        return {
            "description": goal.description,
            "source": goal.source.value,
            "goal_type": goal.goal_type.value,
            "priority": goal.priority,
            "priority_label": GoalPriority.label(goal.priority),
            "active": goal.active,
            "has_success_criteria": len(goal.success_criteria) > 0,
            "has_risks": len(goal.risks) > 0,
            "has_dependencies": len(goal.dependencies) > 0,
            "progress_count": len(goal.progress_notes),
            "age_days": (datetime.now(UTC) - goal.created_at).days,
            "is_revan_goal": goal.source in (GoalSource.ASSIGNED, GoalSource.INFERRED),
            "is_finite": goal.goal_type == GoalType.FINITE,
        }

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Detect conflicts between active goals.

        Goals conflict when they compete for the same resources, have
        contradictory objectives, or cannot both be pursued simultaneously.

        Returns:
            A list of conflict descriptions with involved goals.
        """
        active = self.get_active_goals()
        conflicts: list[dict[str, Any]] = []

        for i, g1 in enumerate(active):
            for g2 in active[i + 1 :]:
                # Check for shared dependencies (resource conflict)
                shared_deps = set(g1.dependencies) & set(g2.dependencies)
                if shared_deps:
                    conflicts.append({
                        "type": "resource_conflict",
                        "goal_a": g1.description,
                        "goal_b": g2.description,
                        "shared_dependencies": list(shared_deps),
                    })

                # Check for contradictory success criteria
                g1_criteria = {c.lower() for c in g1.success_criteria}
                g2_criteria = {c.lower() for c in g2.success_criteria}
                # Simple heuristic: if criteria contain opposite keywords
                opposites = [
                    ("increase", "decrease"),
                    ("maximize", "minimize"),
                    ("enable", "disable"),
                    ("add", "remove"),
                ]
                for pos, neg in opposites:
                    if any(pos in c for c in g1_criteria) and any(neg in c for c in g2_criteria):
                        conflicts.append({
                            "type": "objective_conflict",
                            "goal_a": g1.description,
                            "goal_b": g2.description,
                            "detail": f"'{pos}' vs '{neg}'",
                        })
                        break

        return conflicts

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics about the goal system."""
        active = self.get_active_goals()
        completed = self.get_completed_goals()
        abandoned = self.get_abandoned_goals()

        source_counts: dict[str, int] = {}
        for source in GoalSource:
            source_counts[source.value] = len(self.get_goals_by_source(source))

        type_counts: dict[str, int] = {}
        for gt in GoalType:
            type_counts[gt.value] = len(self.get_goals_by_type(gt))

        priority_counts: dict[str, int] = {}
        for p in [GoalPriority.REVAN, GoalPriority.TELEMACHUS, GoalPriority.EXTERNAL]:
            priority_counts[GoalPriority.label(p)] = len(self.get_goals_by_priority(p))

        return {
            "total_goals": len(self._goals),
            "active_goals": len(active),
            "completed_goals": len(completed),
            "abandoned_goals": len(abandoned),
            "by_source": source_counts,
            "by_type": type_counts,
            "by_priority": priority_counts,
            "conflicts_detected": len(self.detect_conflicts()),
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize all goals to a JSON string for memory storage."""
        return json.dumps(
            {
                "goals": [g.to_dict() for g in self._goals],
                "total": len(self._goals),
            },
            indent=2,
        )

    def to_memory_index_keys(self) -> dict[str, str]:
        """Return index keys for memory store indexing."""
        return {
            "type": "goal_state",
            "goal_count": str(len(self._goals)),
            "active_count": str(len(self.get_active_goals())),
        }

    @classmethod
    def from_memory_content(cls, content: str) -> GoalManager:
        """Restore a GoalManager from serialized memory content.

        Args:
            content: JSON string produced by to_memory_content().

        Returns:
            A restored GoalManager instance.
        """
        manager = cls()
        data = json.loads(content)
        for goal_data in data.get("goals", []):
            manager._goals.append(Goal.from_dict(goal_data))
        logger.info(
            "GoalManager restored from memory: %d goals", len(manager._goals)
        )
        return manager

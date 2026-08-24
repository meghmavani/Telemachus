"""Project Management — structured systems of intent that evolve over time.

Projects are not tasks. Projects are structured systems of intent that evolve
over time. Each project contains goals, context, constraints, tasks,
dependencies, execution history, and success criteria.

The project lifecycle follows five phases:
1. Creation — a goal is identified or a task is assigned
2. Structuring — breaking into milestones, tasks, dependencies, risks
3. Execution — selecting next best tasks, adapting to new information
4. Monitoring — tracking progress, blockers, risks, deviations
5. Reflection — analyzing what worked, what failed, why outcomes occurred

Projects are prioritized by: alignment with Revan's goals, impact, urgency,
dependency structure, and efficiency.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from telemachus.core.types import ProjectState, TaskState

logger = logging.getLogger("telemachus.cognition.projects")


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A single task within a project.

    Tasks have a description, status, priority, dependencies, estimated
    effort, and context. Tasks flow through states: pending → in_progress →
    blocked/completed/deprecated.
    """

    description: str
    status: TaskState = TaskState.PENDING
    priority: int = 0  # Lower = higher priority (0 is highest)
    dependencies: list[str] = field(default_factory=list)
    estimated_effort: str | None = None  # e.g., "2 hours", "1 day"
    context: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark this task as in progress."""
        if self.status == TaskState.PENDING:
            self.status = TaskState.IN_PROGRESS
            self.updated_at = datetime.now(UTC)
            logger.info("Task started: %s", self.description)

    def block(self, reason: str) -> None:
        """Mark this task as blocked with a reason."""
        self.status = TaskState.BLOCKED
        self.metadata["block_reason"] = reason
        self.updated_at = datetime.now(UTC)
        logger.info("Task blocked: %s (reason: %s)", self.description, reason)

    def unblock(self) -> None:
        """Unblock a task, returning it to in_progress."""
        if self.status == TaskState.BLOCKED:
            self.status = TaskState.IN_PROGRESS
            self.metadata.pop("block_reason", None)
            self.updated_at = datetime.now(UTC)
            logger.info("Task unblocked: %s", self.description)

    def complete(self) -> None:
        """Mark this task as completed."""
        self.status = TaskState.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        logger.info("Task completed: %s", self.description)

    def deprecate(self, reason: str) -> None:
        """Mark this task as deprecated (no longer relevant)."""
        self.status = TaskState.DEPRECATED
        self.metadata["deprecate_reason"] = reason
        self.updated_at = datetime.now(UTC)
        logger.info("Task deprecated: %s (reason: %s)", self.description, reason)

    def is_blocked_by(self, other_task_description: str) -> bool:
        """Check if this task depends on another specific task."""
        return other_task_description in self.dependencies

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for persistence."""
        return {
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "estimated_effort": self.estimated_effort,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize from a dictionary."""
        task = cls(
            description=data["description"],
            status=TaskState(data["status"]),
            priority=data.get("priority", 0),
            dependencies=data.get("dependencies", []),
            estimated_effort=data.get("estimated_effort"),
            context=data.get("context"),
            metadata=data.get("metadata", {}),
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        return task


# ---------------------------------------------------------------------------
# Project dataclass
# ---------------------------------------------------------------------------


@dataclass
class Project:
    """A structured system of intent that evolves over time.

    Projects contain goals, context, constraints, tasks, dependencies,
    execution history, and success criteria. They flow through a lifecycle
    of creation, structuring, execution, monitoring, reflection, and
    completion/abandonment.
    """

    name: str
    goal: str
    state: ProjectState = ProjectState.CREATED
    priority: int = 0  # Lower = higher priority
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    resource_requirements: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    abandoned_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def advance_state(self, new_state: ProjectState) -> None:
        """Advance the project to a new lifecycle state.

        Args:
            new_state: The target state.

        Raises:
            ValueError: If the transition is invalid.
        """
        valid_transitions: dict[ProjectState, set[ProjectState]] = {
            ProjectState.CREATED: {ProjectState.STRUCTURING, ProjectState.ABANDONED},
            ProjectState.STRUCTURING: {
                ProjectState.EXECUTING, ProjectState.ABANDONED
            },
            ProjectState.EXECUTING: {
                ProjectState.MONITORING, ProjectState.ABANDONED
            },
            ProjectState.MONITORING: {
                ProjectState.EXECUTING,
                ProjectState.REFLECTING,
                ProjectState.ABANDONED,
            },
            ProjectState.REFLECTING: {
                ProjectState.EXECUTING,
                ProjectState.COMPLETED,
                ProjectState.ABANDONED,
            },
            ProjectState.COMPLETED: set(),  # Terminal state
            ProjectState.ABANDONED: set(),  # Terminal state
        }

        allowed = valid_transitions.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} → {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now(UTC)
        self.history.append(
            f"State transition: {old_state.value} → {new_state.value} "
            f"at {self.updated_at.isoformat()}"
        )
        logger.info(
            "Project '%s': %s → %s", self.name, old_state.value, new_state.value
        )

        if new_state == ProjectState.COMPLETED:
            self.completed_at = datetime.now(UTC)
        elif new_state == ProjectState.ABANDONED:
            self.abandoned_at = datetime.now(UTC)

    def complete(self) -> None:
        """Mark the project as completed."""
        self.advance_state(ProjectState.COMPLETED)

    def abandon(self, reason: str) -> None:
        """Abandon the project with a documented reason.

        Args:
            reason: Why the project is being abandoned.
        """
        self.metadata["abandon_reason"] = reason
        self.history.append(f"Abandoned: {reason}")
        self.advance_state(ProjectState.ABANDONED)

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def add_task(
        self,
        description: str,
        priority: int = 0,
        dependencies: list[str] | None = None,
        estimated_effort: str | None = None,
        context: str | None = None,
    ) -> Task:
        """Add a new task to the project.

        Args:
            description: Task description.
            priority: Task priority (lower = higher).
            dependencies: Other task descriptions this depends on.
            estimated_effort: Estimated effort (e.g., "2 hours").
            context: Additional context for the task.

        Returns:
            The newly created Task.

        Raises:
            ValueError: If description is empty.
        """
        if not description or not description.strip():
            raise ValueError("Task description must not be empty")

        task = Task(
            description=description.strip(),
            priority=priority,
            dependencies=dependencies or [],
            estimated_effort=estimated_effort,
            context=context,
        )
        self.tasks.append(task)
        self.updated_at = datetime.now(UTC)
        self.history.append(f"Task added: {task.description}")
        logger.info("Task added to project '%s': %s", self.name, task.description)
        return task

    def get_task(self, description: str) -> Task | None:
        """Find a task by exact description match."""
        for task in self.tasks:
            if task.description == description:
                return task
        return None

    def get_next_task(self) -> Task | None:
        """Get the highest-priority pending task that is not blocked.

        Returns:
            The next task to work on, or None if no tasks are available.
        """
        pending = [t for t in self.tasks if t.status == TaskState.PENDING]
        if not pending:
            return None

        # Sort by priority (lower = higher), then by creation time
        pending.sort(key=lambda t: (t.priority, t.created_at))

        # Check dependencies: a task is blocked if any dependency is not completed
        completed_descriptions = {
            t.description for t in self.tasks if t.status == TaskState.COMPLETED
        }
        for task in pending:
            if all(dep in completed_descriptions for dep in task.dependencies):
                return task

        return None  # All pending tasks are blocked

    def get_tasks_by_status(self, status: TaskState) -> list[Task]:
        """Return all tasks with a specific status."""
        return [t for t in self.tasks if t.status == status]

    def get_blocked_tasks(self) -> list[Task]:
        """Return all blocked tasks."""
        return self.get_tasks_by_status(TaskState.BLOCKED)

    def get_completed_tasks(self) -> list[Task]:
        """Return all completed tasks."""
        return self.get_tasks_by_status(TaskState.COMPLETED)

    def get_progress(self) -> dict[str, Any]:
        """Return progress statistics for the project."""
        total = len(self.tasks)
        if total == 0:
            return {
                "total_tasks": 0,
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "blocked": 0,
                "deprecated": 0,
                "completion_pct": 0.0,
            }

        counts: dict[str, float] = {
            "total_tasks": total,
            "completed": len(self.get_completed_tasks()),
            "in_progress": len(self.get_tasks_by_status(TaskState.IN_PROGRESS)),
            "pending": len(self.get_tasks_by_status(TaskState.PENDING)),
            "blocked": len(self.get_blocked_tasks()),
            "deprecated": len(self.get_tasks_by_status(TaskState.DEPRECATED)),
        }
        effective_total = total - counts["deprecated"]
        counts["completion_pct"] = (
            round(counts["completed"] / effective_total * 100, 1)
            if effective_total > 0
            else 0.0
        )
        return counts

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------

    def add_reflection(self, reflection: str) -> None:
        """Record a reflection on the project.

        Args:
            reflection: The reflection text.
        """
        self.reflections.append(reflection)
        self.updated_at = datetime.now(UTC)
        self.history.append(f"Reflection recorded: {reflection[:80]}...")
        logger.info("Reflection added to project '%s'", self.name)

    def add_decision(self, decision: str) -> None:
        """Record a decision made during the project.

        Args:
            decision: Description of the decision.
        """
        self.decisions.append(decision)
        self.updated_at = datetime.now(UTC)
        self.history.append(f"Decision recorded: {decision[:80]}...")
        logger.info("Decision added to project '%s'", self.name)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for persistence."""
        return {
            "name": self.name,
            "goal": self.goal,
            "state": self.state.value,
            "priority": self.priority,
            "success_criteria": self.success_criteria,
            "constraints": self.constraints,
            "risks": self.risks,
            "tasks": [t.to_dict() for t in self.tasks],
            "milestones": self.milestones,
            "dependencies": self.dependencies,
            "resource_requirements": self.resource_requirements,
            "decisions": self.decisions,
            "reflections": self.reflections,
            "history": self.history,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "abandoned_at": self.abandoned_at.isoformat() if self.abandoned_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        """Deserialize from a dictionary."""
        project = cls(
            name=data["name"],
            goal=data["goal"],
            state=ProjectState(data["state"]),
            priority=data.get("priority", 0),
            success_criteria=data.get("success_criteria", []),
            constraints=data.get("constraints", []),
            risks=data.get("risks", []),
            milestones=data.get("milestones", []),
            dependencies=data.get("dependencies", []),
            resource_requirements=data.get("resource_requirements", []),
            decisions=data.get("decisions", []),
            reflections=data.get("reflections", []),
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
        )
        project.created_at = datetime.fromisoformat(data["created_at"])
        project.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            project.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("abandoned_at"):
            project.abandoned_at = datetime.fromisoformat(data["abandoned_at"])
        for task_data in data.get("tasks", []):
            project.tasks.append(Task.from_dict(task_data))
        return project


# ---------------------------------------------------------------------------
# Project Manager
# ---------------------------------------------------------------------------


class ProjectManager:
    """Manages multiple projects with prioritization, lifecycle tracking,
    and persistence.

    Projects are prioritized by: alignment with Revan's goals, impact,
    urgency, dependency structure, and efficiency. The manager supports
    dynamic reprioritization as new information appears.
    """

    def __init__(self) -> None:
        """Initialize an empty project manager."""
        self._projects: list[Project] = []
        logger.info("ProjectManager initialized")

    # ------------------------------------------------------------------
    # Project creation
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        goal: str,
        priority: int = 0,
        success_criteria: list[str] | None = None,
        constraints: list[str] | None = None,
        risks: list[str] | None = None,
        milestones: list[str] | None = None,
        dependencies: list[str] | None = None,
        resource_requirements: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Create and register a new project.

        Args:
            name: Unique project name.
            goal: The goal this project serves.
            priority: Project priority (lower = higher).
            success_criteria: Conditions that define completion.
            constraints: Known constraints on the project.
            risks: Known risks.
            milestones: Planned milestones.
            dependencies: Other projects this depends on.
            resource_requirements: Resources needed.
            metadata: Additional contextual data.

        Returns:
            The newly created Project.

        Raises:
            ValueError: If name or goal is empty, or if name already exists.
        """
        if not name or not name.strip():
            raise ValueError("Project name must not be empty")
        if not goal or not goal.strip():
            raise ValueError("Project goal must not be empty")
        if self.get_project(name.strip()) is not None:
            raise ValueError(f"Project '{name.strip()}' already exists")

        project = Project(
            name=name.strip(),
            goal=goal.strip(),
            priority=priority,
            success_criteria=success_criteria or [],
            constraints=constraints or [],
            risks=risks or [],
            milestones=milestones or [],
            dependencies=dependencies or [],
            resource_requirements=resource_requirements or [],
            metadata=metadata or {},
        )
        self._projects.append(project)
        logger.info("Project created: %s (goal: %s)", project.name, project.goal)
        return project

    # ------------------------------------------------------------------
    # Project queries
    # ------------------------------------------------------------------

    def get_project(self, name: str) -> Project | None:
        """Find a project by exact name match."""
        for project in self._projects:
            if project.name == name:
                return project
        return None

    def get_active_projects(self) -> list[Project]:
        """Return all non-terminal projects, sorted by priority."""
        terminal = {ProjectState.COMPLETED, ProjectState.ABANDONED}
        return sorted(
            [p for p in self._projects if p.state not in terminal],
            key=lambda p: (p.priority, p.created_at),
        )

    def get_projects_by_state(self, state: ProjectState) -> list[Project]:
        """Return all projects in a specific state."""
        return [p for p in self._projects if p.state == state]

    def get_completed_projects(self) -> list[Project]:
        """Return all completed projects."""
        return self.get_projects_by_state(ProjectState.COMPLETED)

    def get_abandoned_projects(self) -> list[Project]:
        """Return all abandoned projects."""
        return self.get_projects_by_state(ProjectState.ABANDONED)

    def get_all_projects(self) -> list[Project]:
        """Return all projects (active and terminal)."""
        return list(self._projects)

    def get_top_priority_project(self) -> Project | None:
        """Return the highest-priority active project."""
        active = self.get_active_projects()
        return active[0] if active else None

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def advance_project(self, name: str, new_state: ProjectState) -> bool:
        """Advance a project to a new lifecycle state.

        Args:
            name: The project name.
            new_state: The target state.

        Returns:
            True if the project was found and advanced, False otherwise.
        """
        project = self.get_project(name)
        if project is None:
            logger.warning("Project not found: %s", name)
            return False
        try:
            project.advance_state(new_state)
            return True
        except ValueError as e:
            logger.error("Invalid state transition for '%s': %s", name, e)
            return False

    def complete_project(self, name: str) -> bool:
        """Mark a project as completed.

        Args:
            name: The project name.

        Returns:
            True if completed successfully, False otherwise.
        """
        project = self.get_project(name)
        if project is None:
            logger.warning("Project not found for completion: %s", name)
            return False
        project.complete()
        return True

    def abandon_project(self, name: str, reason: str) -> bool:
        """Abandon a project with a documented reason.

        Args:
            name: The project name.
            reason: Why the project is being abandoned.

        Returns:
            True if abandoned successfully, False otherwise.
        """
        project = self.get_project(name)
        if project is None:
            logger.warning("Project not found for abandonment: %s", name)
            return False
        project.abandon(reason)
        return True

    # ------------------------------------------------------------------
    # Prioritization
    # ------------------------------------------------------------------

    def reprioritize(self, name: str, new_priority: int) -> bool:
        """Change a project's priority.

        Args:
            name: The project name.
            new_priority: New priority value (lower = higher).

        Returns:
            True if reprioritized, False if project not found.
        """
        project = self.get_project(name)
        if project is None:
            logger.warning("Project not found for reprioritization: %s", name)
            return False
        old = project.priority
        project.priority = new_priority
        project.updated_at = datetime.now(UTC)
        project.history.append(f"Priority changed: {old} → {new_priority}")
        logger.info("Project '%s' priority: %d → %d", name, old, new_priority)
        return True

    def detect_stalled_projects(self, days_threshold: int = 7) -> list[Project]:
        """Detect projects that haven't been updated recently.

        Args:
            days_threshold: Number of days without updates to consider stalled.

        Returns:
            List of stalled active projects.
        """
        now = datetime.now(UTC)
        stalled: list[Project] = []
        terminal = {ProjectState.COMPLETED, ProjectState.ABANDONED}
        for project in self._projects:
            if project.state in terminal:
                continue
            age = (now - project.updated_at).days
            if age >= days_threshold:
                stalled.append(project)
        return stalled

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics about the project system."""
        state_counts: dict[str, int] = {}
        for state in ProjectState:
            state_counts[state.value] = len(self.get_projects_by_state(state))

        total_tasks = sum(len(p.tasks) for p in self._projects)
        completed_tasks = sum(
            len(p.get_completed_tasks()) for p in self._projects
        )

        return {
            "total_projects": len(self._projects),
            "active_projects": len(self.get_active_projects()),
            "completed_projects": len(self.get_completed_projects()),
            "abandoned_projects": len(self.get_abandoned_projects()),
            "by_state": state_counts,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "stalled_projects": len(self.detect_stalled_projects()),
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize all projects to a JSON string for memory storage."""
        return json.dumps(
            {
                "projects": [p.to_dict() for p in self._projects],
                "total": len(self._projects),
            },
            indent=2,
        )

    def to_memory_index_keys(self) -> dict[str, str]:
        """Return index keys for memory store indexing."""
        return {
            "type": "project_state",
            "project_count": str(len(self._projects)),
            "active_count": str(len(self.get_active_projects())),
        }

    @classmethod
    def from_memory_content(cls, content: str) -> ProjectManager:
        """Restore a ProjectManager from serialized memory content.

        Args:
            content: JSON string produced by to_memory_content().

        Returns:
            A restored ProjectManager instance.
        """
        manager = cls()
        data = json.loads(content)
        for project_data in data.get("projects", []):
            manager._projects.append(Project.from_dict(project_data))
        logger.info(
            "ProjectManager restored from memory: %d projects",
            len(manager._projects),
        )
        return manager

"""Tests for the ProjectManager — structured project lifecycle management."""

from __future__ import annotations

import pytest

from telemachus.cognition.projects import Project, ProjectManager, Task
from telemachus.core.types import ProjectState, TaskState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> ProjectManager:
    """Return a fresh ProjectManager."""
    return ProjectManager()


@pytest.fixture
def sample_project(manager: ProjectManager) -> Project:
    """Return a project with tasks in various states."""
    project = manager.create_project(
        name="Test Project",
        goal="Complete testing",
        success_criteria=["All tests pass"],
        milestones=["M1: Setup", "M2: Tests", "M3: Review"],
    )
    project.add_task("Task 1: Setup environment", priority=0)
    project.add_task("Task 2: Write tests", priority=1, dependencies=["Task 1: Setup environment"])
    project.add_task("Task 3: Review code", priority=2, dependencies=["Task 2: Write tests"])
    return project


# ---------------------------------------------------------------------------
# Task dataclass tests
# ---------------------------------------------------------------------------


class TestTask:
    """Tests for the Task dataclass."""

    def test_create_task(self) -> None:
        """A task should be created with correct defaults."""
        task = Task(description="Test task")
        assert task.description == "Test task"
        assert task.status == TaskState.PENDING
        assert task.priority == 0
        assert task.dependencies == []
        assert task.completed_at is None

    def test_start_task(self) -> None:
        """Starting a pending task should set it to in_progress."""
        task = Task(description="Test task")
        task.start()
        assert task.status == TaskState.IN_PROGRESS

    def test_start_already_in_progress(self) -> None:
        """Starting an in-progress task should be idempotent."""
        task = Task(description="Test task", status=TaskState.IN_PROGRESS)
        task.start()
        assert task.status == TaskState.IN_PROGRESS

    def test_block_task(self) -> None:
        """Blocking a task should record the reason."""
        task = Task(description="Test task")
        task.block("Waiting for dependency")
        assert task.status == TaskState.BLOCKED
        assert task.metadata["block_reason"] == "Waiting for dependency"

    def test_unblock_task(self) -> None:
        """Unblocking a task should return it to in_progress."""
        task = Task(description="Test task", status=TaskState.BLOCKED)
        task.metadata["block_reason"] = "Was blocked"
        task.unblock()
        assert task.status == TaskState.IN_PROGRESS
        assert "block_reason" not in task.metadata

    def test_complete_task(self) -> None:
        """Completing a task should set completed_at."""
        task = Task(description="Test task")
        task.complete()
        assert task.status == TaskState.COMPLETED
        assert task.completed_at is not None

    def test_deprecate_task(self) -> None:
        """Deprecating a task should record the reason."""
        task = Task(description="Test task")
        task.deprecate("No longer needed")
        assert task.status == TaskState.DEPRECATED
        assert task.metadata["deprecate_reason"] == "No longer needed"

    def test_is_blocked_by(self) -> None:
        """Should detect dependency on another task."""
        task = Task(
            description="Test task",
            dependencies=["Task A", "Task B"],
        )
        assert task.is_blocked_by("Task A") is True
        assert task.is_blocked_by("Task C") is False

    def test_task_serialization_roundtrip(self) -> None:
        """Task should survive to_dict → from_dict roundtrip."""
        task = Task(
            description="Test task",
            status=TaskState.IN_PROGRESS,
            priority=1,
            dependencies=["Dep 1"],
            estimated_effort="2 hours",
            context="Some context",
            metadata={"key": "value"},
        )
        data = task.to_dict()
        restored = Task.from_dict(data)

        assert restored.description == task.description
        assert restored.status == task.status
        assert restored.priority == task.priority
        assert restored.dependencies == task.dependencies
        assert restored.estimated_effort == task.estimated_effort
        assert restored.context == task.context
        assert restored.metadata == task.metadata


# ---------------------------------------------------------------------------
# Project dataclass tests
# ---------------------------------------------------------------------------


class TestProject:
    """Tests for the Project dataclass."""

    def test_create_project(self) -> None:
        """A project should be created with correct defaults."""
        project = Project(name="Test", goal="Complete testing")
        assert project.name == "Test"
        assert project.goal == "Complete testing"
        assert project.state == ProjectState.CREATED
        assert project.tasks == []
        assert project.completed_at is None

    def test_advance_state_valid(self) -> None:
        """Valid state transitions should succeed."""
        project = Project(name="Test", goal="Goal")
        project.advance_state(ProjectState.STRUCTURING)
        assert project.state == ProjectState.STRUCTURING

    def test_advance_state_invalid_raises(self) -> None:
        """Invalid state transitions should raise ValueError."""
        project = Project(name="Test", goal="Goal")
        with pytest.raises(ValueError, match="Invalid transition"):
            project.advance_state(ProjectState.EXECUTING)  # Can't skip structuring

    def test_complete_project(self) -> None:
        """Completing a project should set terminal state."""
        project = Project(name="Test", goal="Goal")
        project.advance_state(ProjectState.STRUCTURING)
        project.advance_state(ProjectState.EXECUTING)
        project.advance_state(ProjectState.MONITORING)
        project.advance_state(ProjectState.REFLECTING)
        project.complete()
        assert project.state == ProjectState.COMPLETED
        assert project.completed_at is not None

    def test_abandon_project(self) -> None:
        """Abandoning a project should record the reason."""
        project = Project(name="Test", goal="Goal")
        project.abandon("No longer relevant")
        assert project.state == ProjectState.ABANDONED
        assert project.metadata["abandon_reason"] == "No longer relevant"

    def test_state_transition_adds_to_history(self) -> None:
        """State transitions should be recorded in history."""
        project = Project(name="Test", goal="Goal")
        project.advance_state(ProjectState.STRUCTURING)
        assert len(project.history) == 1
        assert "created" in project.history[0]
        assert "structuring" in project.history[0]

    def test_terminal_state_no_transitions(self) -> None:
        """Terminal states should not allow further transitions."""
        project = Project(name="Test", goal="Goal", state=ProjectState.COMPLETED)
        with pytest.raises(ValueError):
            project.advance_state(ProjectState.EXECUTING)

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def test_add_task(self) -> None:
        """Adding a task should append to the project."""
        project = Project(name="Test", goal="Goal")
        task = project.add_task("New task")
        assert len(project.tasks) == 1
        assert task.description == "New task"

    def test_add_task_empty_raises(self) -> None:
        """Empty task description should raise ValueError."""
        project = Project(name="Test", goal="Goal")
        with pytest.raises(ValueError, match="must not be empty"):
            project.add_task("")

    def test_get_task(self) -> None:
        """Should find a task by description."""
        project = Project(name="Test", goal="Goal")
        project.add_task("Task A")
        project.add_task("Task B")
        task = project.get_task("Task A")
        assert task is not None
        assert task.description == "Task A"

    def test_get_task_not_found(self) -> None:
        """Should return None for nonexistent task."""
        project = Project(name="Test", goal="Goal")
        assert project.get_task("Nonexistent") is None

    def test_get_next_task_returns_highest_priority(self) -> None:
        """get_next_task should return highest-priority pending task."""
        project = Project(name="Test", goal="Goal")
        project.add_task("Low priority", priority=2)
        project.add_task("High priority", priority=0)
        next_task = project.get_next_task()
        assert next_task is not None
        assert next_task.description == "High priority"

    def test_get_next_task_respects_dependencies(self) -> None:
        """get_next_task should skip tasks with unmet dependencies."""
        project = Project(name="Test", goal="Goal")
        project.add_task("Task A", priority=0)
        project.add_task("Task B", priority=1, dependencies=["Task A"])
        next_task = project.get_next_task()
        assert next_task is not None
        assert next_task.description == "Task A"

    def test_get_next_task_returns_blocked_task_when_deps_met(self) -> None:
        """get_next_task should return dependent task when deps are completed."""
        project = Project(name="Test", goal="Goal")
        task_a = project.add_task("Task A", priority=0)
        project.add_task("Task B", priority=1, dependencies=["Task A"])
        task_a.complete()
        next_task = project.get_next_task()
        assert next_task is not None
        assert next_task.description == "Task B"

    def test_get_next_task_none_when_all_completed(self) -> None:
        """get_next_task should return None when all tasks are done."""
        project = Project(name="Test", goal="Goal")
        task = project.add_task("Task A")
        task.complete()
        assert project.get_next_task() is None

    def test_get_tasks_by_status(self) -> None:
        """Should filter tasks by status."""
        project = Project(name="Test", goal="Goal")
        t1 = project.add_task("Task A")
        project.add_task("Task B")
        t1.start()
        pending = project.get_tasks_by_status(TaskState.PENDING)
        in_progress = project.get_tasks_by_status(TaskState.IN_PROGRESS)
        assert len(pending) == 1
        assert len(in_progress) == 1

    def test_get_blocked_tasks(self) -> None:
        """Should return only blocked tasks."""
        project = Project(name="Test", goal="Goal")
        t1 = project.add_task("Task A")
        project.add_task("Task B")
        t1.block("Blocked")
        blocked = project.get_blocked_tasks()
        assert len(blocked) == 1
        assert blocked[0].description == "Task A"

    def test_get_completed_tasks(self) -> None:
        """Should return only completed tasks."""
        project = Project(name="Test", goal="Goal")
        t1 = project.add_task("Task A")
        project.add_task("Task B")
        t1.complete()
        completed = project.get_completed_tasks()
        assert len(completed) == 1

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def test_get_progress_empty(self) -> None:
        """Progress for empty project should show zeros."""
        project = Project(name="Test", goal="Goal")
        progress = project.get_progress()
        assert progress["total_tasks"] == 0
        assert progress["completion_pct"] == 0.0

    def test_get_progress_with_tasks(self) -> None:
        """Progress should reflect task completion."""
        project = Project(name="Test", goal="Goal")
        t1 = project.add_task("Task A")
        project.add_task("Task B")
        t1.complete()
        progress = project.get_progress()
        assert progress["total_tasks"] == 2
        assert progress["completed"] == 1
        assert progress["completion_pct"] == 50.0

    # ------------------------------------------------------------------
    # Reflection and decisions
    # ------------------------------------------------------------------

    def test_add_reflection(self) -> None:
        """Reflections should be appended."""
        project = Project(name="Test", goal="Goal")
        project.add_reflection("This went well")
        project.add_reflection("This could improve")
        assert len(project.reflections) == 2

    def test_add_decision(self) -> None:
        """Decisions should be recorded."""
        project = Project(name="Test", goal="Goal")
        project.add_decision("Chose approach A over B")
        assert len(project.decisions) == 1

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def test_project_serialization_roundtrip(self) -> None:
        """Project should survive to_dict → from_dict roundtrip."""
        project = Project(
            name="Test Project",
            goal="Complete testing",
            state=ProjectState.EXECUTING,
            priority=1,
            success_criteria=["All tests pass"],
            constraints=["Time limit"],
            risks=["Flaky tests"],
            milestones=["M1", "M2"],
            dependencies=["Other project"],
            resource_requirements=["CPU time"],
            metadata={"key": "value"},
        )
        project.add_task("Task 1")
        project.add_reflection("Good progress")
        project.add_decision("Use pytest")

        data = project.to_dict()
        restored = Project.from_dict(data)

        assert restored.name == project.name
        assert restored.goal == project.goal
        assert restored.state == project.state
        assert restored.priority == project.priority
        assert restored.success_criteria == project.success_criteria
        assert restored.constraints == project.constraints
        assert restored.risks == project.risks
        assert restored.milestones == project.milestones
        assert restored.dependencies == project.dependencies
        assert len(restored.tasks) == 1
        assert len(restored.reflections) == 1
        assert len(restored.decisions) == 1
        assert restored.metadata == project.metadata


# ---------------------------------------------------------------------------
# ProjectManager initialization
# ---------------------------------------------------------------------------


class TestProjectManagerInit:
    """Tests for ProjectManager initialization."""

    def test_manager_starts_empty(self, manager: ProjectManager) -> None:
        """A new manager should have no projects."""
        assert len(manager.get_all_projects()) == 0
        assert len(manager.get_active_projects()) == 0

    def test_stats_empty(self, manager: ProjectManager) -> None:
        """Stats for empty manager should show zeros."""
        stats = manager.get_stats()
        assert stats["total_projects"] == 0
        assert stats["active_projects"] == 0


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------


class TestProjectCreation:
    """Tests for project creation."""

    def test_create_project(self, manager: ProjectManager) -> None:
        """Creating a project should register it."""
        project = manager.create_project(
            name="My Project",
            goal="Build something",
        )
        assert project.name == "My Project"
        assert project.state == ProjectState.CREATED
        assert len(manager.get_all_projects()) == 1

    def test_create_project_with_all_fields(self, manager: ProjectManager) -> None:
        """All optional fields should be accepted."""
        project = manager.create_project(
            name="Full Project",
            goal="Comprehensive goal",
            priority=1,
            success_criteria=["Done"],
            constraints=["Budget"],
            risks=["Risk 1"],
            milestones=["M1"],
            dependencies=["Other"],
            resource_requirements=["Server"],
            metadata={"owner": "Revan"},
        )
        assert len(project.success_criteria) == 1
        assert len(project.constraints) == 1
        assert len(project.risks) == 1
        assert len(project.milestones) == 1
        assert project.metadata["owner"] == "Revan"

    def test_create_duplicate_name_raises(self, manager: ProjectManager) -> None:
        """Duplicate project names should raise ValueError."""
        manager.create_project("My Project", goal="Goal")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_project("My Project", goal="Another goal")

    def test_empty_name_raises(self, manager: ProjectManager) -> None:
        """Empty name should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            manager.create_project("", goal="Goal")

    def test_empty_goal_raises(self, manager: ProjectManager) -> None:
        """Empty goal should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            manager.create_project("Project", goal="")


# ---------------------------------------------------------------------------
# Project queries
# ---------------------------------------------------------------------------


class TestProjectQueries:
    """Tests for project query methods."""

    def test_get_project(self, manager: ProjectManager) -> None:
        """Should find a project by name."""
        manager.create_project("Project A", goal="Goal A")
        project = manager.get_project("Project A")
        assert project is not None
        assert project.goal == "Goal A"

    def test_get_project_not_found(self, manager: ProjectManager) -> None:
        """Should return None for nonexistent project."""
        assert manager.get_project("Nonexistent") is None

    def test_get_active_projects(self, manager: ProjectManager) -> None:
        """Should return only non-terminal projects."""
        manager.create_project("Active", goal="Goal")
        manager.create_project("Completed", goal="Goal")
        # Advance Completed through states, then complete
        manager.advance_project("Completed", ProjectState.STRUCTURING)
        manager.advance_project("Completed", ProjectState.EXECUTING)
        manager.advance_project("Completed", ProjectState.MONITORING)
        manager.advance_project("Completed", ProjectState.REFLECTING)
        manager.complete_project("Completed")
        active = manager.get_active_projects()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_get_projects_by_state(self, manager: ProjectManager) -> None:
        """Should filter projects by state."""
        manager.create_project("P1", goal="G1")
        manager.create_project("P2", goal="G2")
        created = manager.get_projects_by_state(ProjectState.CREATED)
        assert len(created) == 2

    def test_get_completed_projects(self, manager: ProjectManager) -> None:
        """Should return only completed projects."""
        manager.create_project("P1", goal="G1")
        manager.create_project("P2", goal="G2")
        manager.advance_project("P1", ProjectState.STRUCTURING)
        manager.advance_project("P1", ProjectState.EXECUTING)
        manager.advance_project("P1", ProjectState.MONITORING)
        manager.advance_project("P1", ProjectState.REFLECTING)
        manager.complete_project("P1")
        completed = manager.get_completed_projects()
        assert len(completed) == 1

    def test_get_abandoned_projects(self, manager: ProjectManager) -> None:
        """Should return only abandoned projects."""
        manager.create_project("P1", goal="G1")
        manager.abandon_project("P1", "Done")
        abandoned = manager.get_abandoned_projects()
        assert len(abandoned) == 1

    def test_get_top_priority_project(self, manager: ProjectManager) -> None:
        """Should return highest-priority active project."""
        manager.create_project("Low", goal="G", priority=2)
        manager.create_project("High", goal="G", priority=0)
        top = manager.get_top_priority_project()
        assert top is not None
        assert top.name == "High"


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------


class TestProjectLifecycle:
    """Tests for project lifecycle management."""

    def test_advance_project(self, manager: ProjectManager) -> None:
        """Should advance a project to a new state."""
        manager.create_project("P1", goal="G1")
        result = manager.advance_project("P1", ProjectState.STRUCTURING)
        assert result is True
        project = manager.get_project("P1")
        assert project is not None
        assert project.state == ProjectState.STRUCTURING

    def test_advance_nonexistent_project(self, manager: ProjectManager) -> None:
        """Advancing a nonexistent project should return False."""
        assert manager.advance_project("Nonexistent", ProjectState.STRUCTURING) is False

    def test_advance_invalid_transition(self, manager: ProjectManager) -> None:
        """Invalid transitions should return False."""
        manager.create_project("P1", goal="G1")
        result = manager.advance_project("P1", ProjectState.EXECUTING)
        assert result is False

    def test_complete_project(self, manager: ProjectManager) -> None:
        """Should complete a project from any non-terminal state."""
        manager.create_project("P1", goal="G1")
        # Advance through states to reach REFLECTING, then complete
        manager.advance_project("P1", ProjectState.STRUCTURING)
        manager.advance_project("P1", ProjectState.EXECUTING)
        manager.advance_project("P1", ProjectState.MONITORING)
        manager.advance_project("P1", ProjectState.REFLECTING)
        result = manager.complete_project("P1")
        assert result is True

    def test_complete_nonexistent_project(self, manager: ProjectManager) -> None:
        """Completing a nonexistent project should return False."""
        assert manager.complete_project("Nonexistent") is False

    def test_abandon_project(self, manager: ProjectManager) -> None:
        """Should abandon a project with reason."""
        manager.create_project("P1", goal="G1")
        result = manager.abandon_project("P1", "No longer needed")
        assert result is True
        project = manager.get_project("P1")
        assert project is not None
        assert project.state == ProjectState.ABANDONED

    def test_full_lifecycle(self, manager: ProjectManager) -> None:
        """A project should flow through the full lifecycle."""
        manager.create_project("P1", goal="G1")
        manager.advance_project("P1", ProjectState.STRUCTURING)
        manager.advance_project("P1", ProjectState.EXECUTING)
        manager.advance_project("P1", ProjectState.MONITORING)
        manager.advance_project("P1", ProjectState.REFLECTING)
        manager.complete_project("P1")
        project = manager.get_project("P1")
        assert project is not None
        assert project.state == ProjectState.COMPLETED


# ---------------------------------------------------------------------------
# Prioritization
# ---------------------------------------------------------------------------


class TestPrioritization:
    """Tests for project prioritization."""

    def test_reprioritize(self, manager: ProjectManager) -> None:
        """Should change a project's priority."""
        manager.create_project("P1", goal="G1", priority=5)
        result = manager.reprioritize("P1", 1)
        assert result is True
        project = manager.get_project("P1")
        assert project is not None
        assert project.priority == 1

    def test_reprioritize_nonexistent(self, manager: ProjectManager) -> None:
        """Reprioritizing a nonexistent project should return False."""
        assert manager.reprioritize("Nonexistent", 1) is False

    def test_detect_stalled_projects(self, manager: ProjectManager) -> None:
        """Should detect projects not updated recently."""
        manager.create_project("P1", goal="G1")
        stalled = manager.detect_stalled_projects(days_threshold=0)
        assert len(stalled) == 1

    def test_detect_stalled_excludes_completed(self, manager: ProjectManager) -> None:
        """Completed projects should not be flagged as stalled."""
        manager.create_project("P1", goal="G1")
        manager.advance_project("P1", ProjectState.STRUCTURING)
        manager.advance_project("P1", ProjectState.EXECUTING)
        manager.advance_project("P1", ProjectState.MONITORING)
        manager.advance_project("P1", ProjectState.REFLECTING)
        manager.complete_project("P1")
        stalled = manager.detect_stalled_projects(days_threshold=0)
        assert len(stalled) == 0


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestProjectStats:
    """Tests for project statistics."""

    def test_stats_reflect_state(self, manager: ProjectManager) -> None:
        """Stats should reflect the current state."""
        manager.create_project("P1", goal="G1")
        manager.create_project("P2", goal="G2")
        manager.advance_project("P1", ProjectState.STRUCTURING)
        manager.advance_project("P1", ProjectState.EXECUTING)
        manager.advance_project("P1", ProjectState.MONITORING)
        manager.advance_project("P1", ProjectState.REFLECTING)
        manager.complete_project("P1")
        stats = manager.get_stats()
        assert stats["total_projects"] == 2
        assert stats["active_projects"] == 1
        assert stats["completed_projects"] == 1

    def test_stats_includes_task_counts(self, manager: ProjectManager) -> None:
        """Stats should include task counts."""
        project = manager.create_project("P1", goal="G1")
        project.add_task("Task 1")
        project.add_task("Task 2")
        stats = manager.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["completed_tasks"] == 0


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


class TestProjectPersistence:
    """Tests for memory persistence helpers."""

    def test_to_memory_content(self, manager: ProjectManager) -> None:
        """to_memory_content should produce valid JSON."""
        manager.create_project("P1", goal="G1")
        content = manager.to_memory_content()
        assert isinstance(content, str)
        assert "projects" in content
        assert "total" in content

    def test_to_memory_index_keys(self, manager: ProjectManager) -> None:
        """to_memory_index_keys should return indexable keys."""
        manager.create_project("P1", goal="G1")
        keys = manager.to_memory_index_keys()
        assert keys["type"] == "project_state"
        assert int(keys["project_count"]) == 1

    def test_from_memory_content_roundtrip(self, manager: ProjectManager) -> None:
        """from_memory_content should restore the manager."""
        manager.create_project("P1", goal="G1")
        project = manager.get_project("P1")
        assert project is not None
        project.add_task("Task 1")
        content = manager.to_memory_content()
        restored = ProjectManager.from_memory_content(content)
        assert len(restored.get_all_projects()) == 1
        restored_project = restored.get_project("P1")
        assert restored_project is not None
        assert len(restored_project.tasks) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestProjectEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_name(self, manager: ProjectManager) -> None:
        """Very long project names should be accepted."""
        long_name = "P" * 500
        project = manager.create_project(long_name, goal="Goal")
        assert project.name == long_name

    def test_unicode_name(self, manager: ProjectManager) -> None:
        """Unicode names should be accepted."""
        project = manager.create_project("プロジェクト 🚀", goal="目標")
        assert "プロジェクト" in project.name

    def test_many_tasks(self, manager: ProjectManager) -> None:
        """Projects should handle many tasks."""
        project = manager.create_project("P1", goal="G1")
        for i in range(100):
            project.add_task(f"Task {i}")
        assert len(project.tasks) == 100

    def test_get_next_task_all_blocked(self, manager: ProjectManager) -> None:
        """When all pending tasks are blocked, get_next_task returns None."""
        project = manager.create_project("P1", goal="G1")
        project.add_task("Task A", dependencies=["Nonexistent"])
        project.add_task("Task B", dependencies=["Also nonexistent"])
        assert project.get_next_task() is None

    def test_progress_with_deprecated_tasks(self, manager: ProjectManager) -> None:
        """Deprecated tasks should not count toward completion percentage."""
        project = manager.create_project("P1", goal="G1")
        t1 = project.add_task("Task A")
        t2 = project.add_task("Task B")
        t2.deprecate("Not needed")
        t1.complete()
        progress = project.get_progress()
        assert progress["completion_pct"] == 100.0  # 1/1 effective


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestProjectIntegration:
    """Integration tests for the project system."""

    def test_full_project_lifecycle_with_tasks(self, manager: ProjectManager) -> None:
        """A project should flow through the full lifecycle with tasks."""
        project = manager.create_project(
            name="Integration Project",
            goal="Test full lifecycle",
            success_criteria=["All tasks done"],
        )

        # Structuring
        manager.advance_project("Integration Project", ProjectState.STRUCTURING)
        project.add_task("Setup", priority=0)
        project.add_task("Implement", priority=1, dependencies=["Setup"])
        project.add_task("Test", priority=2, dependencies=["Implement"])

        # Execution
        manager.advance_project("Integration Project", ProjectState.EXECUTING)

        # Complete tasks in order
        task1 = project.get_next_task()
        assert task1 is not None
        assert task1.description == "Setup"
        task1.start()
        task1.complete()

        task2 = project.get_next_task()
        assert task2 is not None
        assert task2.description == "Implement"
        task2.start()
        task2.complete()

        task3 = project.get_next_task()
        assert task3 is not None
        assert task3.description == "Test"
        task3.start()
        task3.complete()

        assert project.get_next_task() is None

        # Monitoring and reflection
        manager.advance_project("Integration Project", ProjectState.MONITORING)
        project.add_reflection("All tasks completed smoothly")
        manager.advance_project("Integration Project", ProjectState.REFLECTING)

        # Complete
        manager.complete_project("Integration Project")
        assert project.state == ProjectState.COMPLETED
        assert project.completed_at is not None

    def test_multiple_projects_independent(self, manager: ProjectManager) -> None:
        """Multiple projects should be independent."""
        p1 = manager.create_project("P1", goal="G1")
        p2 = manager.create_project("P2", goal="G2")
        p1.add_task("Task for P1")
        p2.add_task("Task for P2")
        assert len(p1.tasks) == 1
        assert len(p2.tasks) == 1
        assert p1.tasks[0].description != p2.tasks[0].description

    def test_project_tracks_through_full_lifecycle(self, manager: ProjectManager) -> None:
        """Project should track through all lifecycle states."""
        project = manager.create_project("Lifecycle Project", goal="Test")
        states = [
            ProjectState.STRUCTURING,
            ProjectState.EXECUTING,
            ProjectState.MONITORING,
            ProjectState.REFLECTING,
        ]
        for state in states:
            result = manager.advance_project("Lifecycle Project", state)
            assert result is True
        manager.complete_project("Lifecycle Project")
        assert project.state == ProjectState.COMPLETED

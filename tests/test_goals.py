"""Tests for the GoalManager — proactive goal creation, prioritization, lifecycle."""

from __future__ import annotations

import pytest

from telemachus.cognition.goals import Goal, GoalManager, GoalPriority
from telemachus.core.types import GoalSource, GoalType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> GoalManager:
    """Return a fresh GoalManager."""
    return GoalManager()


@pytest.fixture
def populated_manager(manager: GoalManager) -> GoalManager:
    """Return a GoalManager with sample goals from all sources."""
    manager.create_goal(
        "Help Revan with project X",
        source=GoalSource.ASSIGNED,
        goal_type=GoalType.FINITE,
        success_criteria=["Project X deployed"],
    )
    manager.create_goal(
        "Improve memory retrieval speed",
        source=GoalSource.SELF_GENERATED,
        goal_type=GoalType.INFINITE,
    )
    manager.create_goal(
        "Support Revan's career growth",
        source=GoalSource.INFERRED,
        goal_type=GoalType.INFINITE,
    )
    manager.create_goal(
        "Reduce inefficiencies in workflow",
        source=GoalSource.OBSERVED,
        goal_type=GoalType.FINITE,
        success_criteria=["Workflow time reduced by 20%"],
    )
    return manager


# ---------------------------------------------------------------------------
# Goal dataclass tests
# ---------------------------------------------------------------------------


class TestGoal:
    """Tests for the Goal dataclass."""

    def test_create_finite_goal(self) -> None:
        """A finite goal should be created with correct attributes."""
        goal = Goal(
            description="Complete project X",
            source=GoalSource.ASSIGNED,
            goal_type=GoalType.FINITE,
            priority=GoalPriority.REVAN,
            success_criteria=["Project X deployed"],
        )
        assert goal.description == "Complete project X"
        assert goal.source == GoalSource.ASSIGNED
        assert goal.goal_type == GoalType.FINITE
        assert goal.priority == GoalPriority.REVAN
        assert goal.active is True
        assert goal.completed_at is None
        assert goal.abandoned_at is None

    def test_create_infinite_goal(self) -> None:
        """An infinite goal should have no completion condition."""
        goal = Goal(
            description="Understand Revan better",
            source=GoalSource.SELF_GENERATED,
            goal_type=GoalType.INFINITE,
        )
        assert goal.goal_type == GoalType.INFINITE
        assert goal.active is True

    def test_complete_goal(self) -> None:
        """Completing a goal should mark it inactive and set completed_at."""
        goal = Goal(
            description="Test goal",
            source=GoalSource.ASSIGNED,
            goal_type=GoalType.FINITE,
        )
        goal.complete()
        assert goal.active is False
        assert goal.completed_at is not None
        assert goal.abandoned_at is None

    def test_abandon_goal(self) -> None:
        """Abandoning a goal should mark it inactive with a reason."""
        goal = Goal(
            description="Test goal",
            source=GoalSource.SELF_GENERATED,
            goal_type=GoalType.FINITE,
        )
        goal.abandon("No longer relevant")
        assert goal.active is False
        assert goal.abandoned_at is not None
        assert goal.metadata["abandon_reason"] == "No longer relevant"

    def test_pause_and_resume_goal(self) -> None:
        """Pausing and resuming should toggle active state."""
        goal = Goal(
            description="Test goal",
            source=GoalSource.OBSERVED,
            goal_type=GoalType.FINITE,
        )
        goal.pause()
        assert goal.active is False

        goal.resume()
        assert goal.active is True

    def test_add_progress_note(self) -> None:
        """Progress notes should be appended."""
        goal = Goal(
            description="Test goal",
            source=GoalSource.ASSIGNED,
            goal_type=GoalType.FINITE,
        )
        goal.add_progress_note("Made initial progress")
        goal.add_progress_note("Completed first milestone")
        assert len(goal.progress_notes) == 2
        assert goal.progress_notes[0] == "Made initial progress"

    def test_goal_serialization_roundtrip(self) -> None:
        """Goal should survive to_dict → from_dict roundtrip."""
        goal = Goal(
            description="Test goal",
            source=GoalSource.ASSIGNED,
            goal_type=GoalType.FINITE,
            priority=GoalPriority.REVAN,
            success_criteria=["Criterion 1"],
            risks=["Risk 1"],
            dependencies=["Dep 1"],
            metadata={"key": "value"},
        )
        goal.add_progress_note("Progress note")
        data = goal.to_dict()
        restored = Goal.from_dict(data)

        assert restored.description == goal.description
        assert restored.source == goal.source
        assert restored.goal_type == goal.goal_type
        assert restored.priority == goal.priority
        assert restored.success_criteria == goal.success_criteria
        assert restored.risks == goal.risks
        assert restored.dependencies == goal.dependencies
        assert restored.progress_notes == goal.progress_notes
        assert restored.metadata == goal.metadata


# ---------------------------------------------------------------------------
# GoalManager initialization
# ---------------------------------------------------------------------------


class TestGoalManagerInit:
    """Tests for GoalManager initialization."""

    def test_manager_starts_empty(self, manager: GoalManager) -> None:
        """A new manager should have no goals."""
        assert len(manager.get_all_goals()) == 0
        assert len(manager.get_active_goals()) == 0

    def test_stats_empty(self, manager: GoalManager) -> None:
        """Stats for empty manager should show zeros."""
        stats = manager.get_stats()
        assert stats["total_goals"] == 0
        assert stats["active_goals"] == 0
        assert stats["completed_goals"] == 0
        assert stats["abandoned_goals"] == 0


# ---------------------------------------------------------------------------
# Goal creation
# ---------------------------------------------------------------------------


class TestGoalCreation:
    """Tests for goal creation."""

    def test_create_assigned_goal(self, manager: GoalManager) -> None:
        """Assigned goals should default to Revan priority."""
        goal = manager.create_goal(
            "Build project X",
            source=GoalSource.ASSIGNED,
        )
        assert goal.source == GoalSource.ASSIGNED
        assert goal.priority == GoalPriority.REVAN
        assert goal.goal_type == GoalType.FINITE

    def test_create_inferred_goal(self, manager: GoalManager) -> None:
        """Inferred goals should default to Revan priority."""
        goal = manager.create_goal(
            "Support career growth",
            source=GoalSource.INFERRED,
        )
        assert goal.priority == GoalPriority.REVAN

    def test_create_self_generated_goal(self, manager: GoalManager) -> None:
        """Self-generated goals should default to Telemachus priority."""
        goal = manager.create_goal(
            "Improve reasoning",
            source=GoalSource.SELF_GENERATED,
        )
        assert goal.priority == GoalPriority.TELEMACHUS

    def test_create_observed_goal(self, manager: GoalManager) -> None:
        """Observed goals should default to Telemachus priority."""
        goal = manager.create_goal(
            "Reduce inefficiencies",
            source=GoalSource.OBSERVED,
        )
        assert goal.priority == GoalPriority.TELEMACHUS

    def test_create_with_explicit_priority(self, manager: GoalManager) -> None:
        """Explicit priority should override default."""
        goal = manager.create_goal(
            "External contribution",
            source=GoalSource.SELF_GENERATED,
            priority=GoalPriority.EXTERNAL,
        )
        assert goal.priority == GoalPriority.EXTERNAL

    def test_create_infinite_goal(self, manager: GoalManager) -> None:
        """Infinite goals should be creatable."""
        goal = manager.create_goal(
            "Seek truth",
            source=GoalSource.SELF_GENERATED,
            goal_type=GoalType.INFINITE,
        )
        assert goal.goal_type == GoalType.INFINITE

    def test_create_goal_with_success_criteria(self, manager: GoalManager) -> None:
        """Goals should accept success criteria."""
        goal = manager.create_goal(
            "Deploy system",
            source=GoalSource.ASSIGNED,
            success_criteria=["System deployed", "Tests passing"],
        )
        assert len(goal.success_criteria) == 2

    def test_create_goal_with_risks(self, manager: GoalManager) -> None:
        """Goals should accept risk documentation."""
        goal = manager.create_goal(
            "Risky project",
            source=GoalSource.ASSIGNED,
            risks=["Budget overrun", "Timeline slip"],
        )
        assert len(goal.risks) == 2

    def test_empty_description_raises(self, manager: GoalManager) -> None:
        """Empty description should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            manager.create_goal("", source=GoalSource.ASSIGNED)

    def test_whitespace_description_raises(self, manager: GoalManager) -> None:
        """Whitespace-only description should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            manager.create_goal("   ", source=GoalSource.ASSIGNED)

    def test_goal_added_to_manager(self, manager: GoalManager) -> None:
        """Created goals should appear in the manager."""
        manager.create_goal("Test goal", source=GoalSource.ASSIGNED)
        assert len(manager.get_all_goals()) == 1


# ---------------------------------------------------------------------------
# Goal queries
# ---------------------------------------------------------------------------


class TestGoalQueries:
    """Tests for goal query methods."""

    def test_get_goal_by_description(
        self, populated_manager: GoalManager
    ) -> None:
        """Should find a goal by exact description."""
        goal = populated_manager.get_goal("Help Revan with project X")
        assert goal is not None
        assert goal.source == GoalSource.ASSIGNED

    def test_get_goal_not_found(self, manager: GoalManager) -> None:
        """Should return None for nonexistent goal."""
        assert manager.get_goal("Nonexistent") is None

    def test_get_active_goals_sorted_by_priority(
        self, populated_manager: GoalManager
    ) -> None:
        """Active goals should be sorted by priority (lower first)."""
        active = populated_manager.get_active_goals()
        priorities = [g.priority for g in active]
        assert priorities == sorted(priorities)

    def test_get_goals_by_source(
        self, populated_manager: GoalManager
    ) -> None:
        """Should filter goals by source."""
        assigned = populated_manager.get_goals_by_source(GoalSource.ASSIGNED)
        assert len(assigned) == 1
        assert assigned[0].description == "Help Revan with project X"

    def test_get_goals_by_type(
        self, populated_manager: GoalManager
    ) -> None:
        """Should filter goals by type."""
        finite = populated_manager.get_goals_by_type(GoalType.FINITE)
        infinite = populated_manager.get_goals_by_type(GoalType.INFINITE)
        assert len(finite) == 2
        assert len(infinite) == 2

    def test_get_goals_by_priority(
        self, populated_manager: GoalManager
    ) -> None:
        """Should filter goals by priority level."""
        revan_goals = populated_manager.get_goals_by_priority(GoalPriority.REVAN)
        assert len(revan_goals) == 2  # assigned + inferred

    def test_get_completed_goals(self, manager: GoalManager) -> None:
        """Should return only completed goals."""
        manager.create_goal("Goal 1", source=GoalSource.ASSIGNED)
        manager.create_goal("Goal 2", source=GoalSource.SELF_GENERATED)
        manager.complete_goal("Goal 1")
        completed = manager.get_completed_goals()
        assert len(completed) == 1
        assert completed[0].description == "Goal 1"

    def test_get_abandoned_goals(self, manager: GoalManager) -> None:
        """Should return only abandoned goals."""
        manager.create_goal("Goal 1", source=GoalSource.ASSIGNED)
        manager.abandon_goal("Goal 1", "No longer needed")
        abandoned = manager.get_abandoned_goals()
        assert len(abandoned) == 1

    def test_get_top_priority_goals(
        self, populated_manager: GoalManager
    ) -> None:
        """Should return highest-priority active goals."""
        top = populated_manager.get_top_priority_goals(limit=2)
        assert len(top) <= 2
        assert all(g.priority == GoalPriority.REVAN for g in top)


# ---------------------------------------------------------------------------
# Goal lifecycle
# ---------------------------------------------------------------------------


class TestGoalLifecycle:
    """Tests for goal lifecycle management."""

    def test_complete_goal(self, manager: GoalManager) -> None:
        """Completing a goal should mark it inactive."""
        manager.create_goal("Test goal", source=GoalSource.ASSIGNED)
        result = manager.complete_goal("Test goal")
        assert result is True
        goal = manager.get_goal("Test goal")
        assert goal is not None
        assert goal.active is False
        assert goal.completed_at is not None

    def test_complete_nonexistent_goal(self, manager: GoalManager) -> None:
        """Completing a nonexistent goal should return False."""
        assert manager.complete_goal("Nonexistent") is False

    def test_abandon_goal(self, manager: GoalManager) -> None:
        """Abandoning a goal should record the reason."""
        manager.create_goal("Test goal", source=GoalSource.SELF_GENERATED)
        result = manager.abandon_goal("Test goal", "No longer relevant")
        assert result is True
        goal = manager.get_goal("Test goal")
        assert goal is not None
        assert goal.active is False
        assert goal.metadata["abandon_reason"] == "No longer relevant"

    def test_abandon_nonexistent_goal(self, manager: GoalManager) -> None:
        """Abandoning a nonexistent goal should return False."""
        assert manager.abandon_goal("Nonexistent", "reason") is False

    def test_pause_goal(self, manager: GoalManager) -> None:
        """Pausing a goal should mark it inactive."""
        manager.create_goal("Test goal", source=GoalSource.OBSERVED)
        result = manager.pause_goal("Test goal")
        assert result is True
        goal = manager.get_goal("Test goal")
        assert goal is not None
        assert goal.active is False

    def test_resume_goal(self, manager: GoalManager) -> None:
        """Resuming a paused goal should mark it active."""
        manager.create_goal("Test goal", source=GoalSource.OBSERVED)
        manager.pause_goal("Test goal")
        result = manager.resume_goal("Test goal")
        assert result is True
        goal = manager.get_goal("Test goal")
        assert goal is not None
        assert goal.active is True

    def test_resume_nonexistent_goal(self, manager: GoalManager) -> None:
        """Resuming a nonexistent goal should return False."""
        assert manager.resume_goal("Nonexistent") is False


# ---------------------------------------------------------------------------
# Goal evaluation
# ---------------------------------------------------------------------------


class TestGoalEvaluation:
    """Tests for goal evaluation."""

    def test_evaluate_goal(self, manager: GoalManager) -> None:
        """Evaluating a goal should return structured data."""
        manager.create_goal(
            "Test goal",
            source=GoalSource.ASSIGNED,
            success_criteria=["Done"],
            risks=["Risk"],
        )
        result = manager.evaluate_goal("Test goal")
        assert result["description"] == "Test goal"
        assert result["source"] == "assigned"
        assert result["active"] is True
        assert result["has_success_criteria"] is True
        assert result["has_risks"] is True
        assert result["is_revan_goal"] is True
        assert result["is_finite"] is True

    def test_evaluate_nonexistent_goal_raises(self, manager: GoalManager) -> None:
        """Evaluating a nonexistent goal should raise ValueError."""
        with pytest.raises(ValueError, match="Goal not found"):
            manager.evaluate_goal("Nonexistent")

    def test_evaluate_includes_priority_label(self, manager: GoalManager) -> None:
        """Evaluation should include human-readable priority label."""
        manager.create_goal("Test", source=GoalSource.ASSIGNED)
        result = manager.evaluate_goal("Test")
        assert result["priority_label"] == "Revan's Goals"


# ---------------------------------------------------------------------------
# Goal conflicts
# ---------------------------------------------------------------------------


class TestGoalConflicts:
    """Tests for goal conflict detection."""

    def test_no_conflicts_for_independent_goals(self, manager: GoalManager) -> None:
        """Independent goals should not conflict."""
        manager.create_goal("Goal A", source=GoalSource.ASSIGNED)
        manager.create_goal("Goal B", source=GoalSource.SELF_GENERATED)
        conflicts = manager.detect_conflicts()
        assert len(conflicts) == 0

    def test_resource_conflict_detected(self, manager: GoalManager) -> None:
        """Goals sharing dependencies should be flagged."""
        manager.create_goal(
            "Goal A",
            source=GoalSource.ASSIGNED,
            dependencies=["shared_resource"],
        )
        manager.create_goal(
            "Goal B",
            source=GoalSource.SELF_GENERATED,
            dependencies=["shared_resource"],
        )
        conflicts = manager.detect_conflicts()
        assert len(conflicts) >= 1
        assert any(c["type"] == "resource_conflict" for c in conflicts)

    def test_objective_conflict_detected(self, manager: GoalManager) -> None:
        """Goals with contradictory criteria should be flagged."""
        manager.create_goal(
            "Goal A",
            source=GoalSource.ASSIGNED,
            success_criteria=["Increase performance"],
        )
        manager.create_goal(
            "Goal B",
            source=GoalSource.SELF_GENERATED,
            success_criteria=["Decrease resource usage"],
        )
        conflicts = manager.detect_conflicts()
        assert any(c["type"] == "objective_conflict" for c in conflicts)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestGoalStats:
    """Tests for goal statistics."""

    def test_stats_reflect_state(
        self, populated_manager: GoalManager
    ) -> None:
        """Stats should reflect the current state."""
        stats = populated_manager.get_stats()
        assert stats["total_goals"] == 4
        assert stats["active_goals"] == 4
        assert stats["completed_goals"] == 0
        assert stats["by_source"]["assigned"] == 1
        assert stats["by_source"]["self_generated"] == 1
        assert stats["by_source"]["inferred"] == 1
        assert stats["by_source"]["observed"] == 1

    def test_stats_after_completion(self, manager: GoalManager) -> None:
        """Stats should update after goal completion."""
        manager.create_goal("Goal 1", source=GoalSource.ASSIGNED)
        manager.create_goal("Goal 2", source=GoalSource.SELF_GENERATED)
        manager.complete_goal("Goal 1")
        stats = manager.get_stats()
        assert stats["completed_goals"] == 1
        assert stats["active_goals"] == 1

    def test_stats_includes_conflicts(self, manager: GoalManager) -> None:
        """Stats should include conflict count."""
        manager.create_goal(
            "Goal A",
            source=GoalSource.ASSIGNED,
            dependencies=["shared"],
        )
        manager.create_goal(
            "Goal B",
            source=GoalSource.SELF_GENERATED,
            dependencies=["shared"],
        )
        stats = manager.get_stats()
        assert stats["conflicts_detected"] >= 1


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


class TestGoalPersistence:
    """Tests for memory persistence helpers."""

    def test_to_memory_content(self, populated_manager: GoalManager) -> None:
        """to_memory_content should produce valid JSON."""
        content = populated_manager.to_memory_content()
        assert isinstance(content, str)
        assert "goals" in content
        assert "total" in content

    def test_to_memory_index_keys(
        self, populated_manager: GoalManager
    ) -> None:
        """to_memory_index_keys should return indexable keys."""
        keys = populated_manager.to_memory_index_keys()
        assert keys["type"] == "goal_state"
        assert int(keys["goal_count"]) == 4
        assert int(keys["active_count"]) == 4

    def test_from_memory_content_roundtrip(
        self, populated_manager: GoalManager
    ) -> None:
        """from_memory_content should restore the manager."""
        content = populated_manager.to_memory_content()
        restored = GoalManager.from_memory_content(content)
        assert len(restored.get_all_goals()) == 4
        assert len(restored.get_active_goals()) == 4


# ---------------------------------------------------------------------------
# GoalPriority
# ---------------------------------------------------------------------------


class TestGoalPriority:
    """Tests for GoalPriority constants."""

    def test_labels(self) -> None:
        """Priority labels should be human-readable."""
        assert GoalPriority.label(1) == "Revan's Goals"
        assert GoalPriority.label(2) == "Telemachus's Growth & Wellbeing"
        assert GoalPriority.label(3) == "External Goals"

    def test_unknown_priority_label(self) -> None:
        """Unknown priority should get a fallback label."""
        assert "Unknown" in GoalPriority.label(99)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestGoalEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_description(self, manager: GoalManager) -> None:
        """Very long descriptions should be accepted."""
        long_desc = "A" * 1000
        goal = manager.create_goal(long_desc, source=GoalSource.SELF_GENERATED)
        assert goal.description == long_desc

    def test_unicode_description(self, manager: GoalManager) -> None:
        """Unicode descriptions should be accepted."""
        goal = manager.create_goal(
            "了解 Revan 的需求 🎯",
            source=GoalSource.INFERRED,
        )
        assert "了解" in goal.description

    def test_multiple_goals_same_description(self, manager: GoalManager) -> None:
        """Multiple goals with same description should both exist."""
        manager.create_goal("Same goal", source=GoalSource.ASSIGNED)
        manager.create_goal("Same goal", source=GoalSource.SELF_GENERATED)
        # get_goal returns first match
        goal = manager.get_goal("Same goal")
        assert goal is not None
        assert len(manager.get_all_goals()) == 2

    def test_complete_already_completed_goal(self, manager: GoalManager) -> None:
        """Completing an already completed goal should be idempotent."""
        manager.create_goal("Test", source=GoalSource.ASSIGNED)
        manager.complete_goal("Test")
        manager.complete_goal("Test")  # Should not raise
        goal = manager.get_goal("Test")
        assert goal is not None
        assert goal.active is False

    def test_abandon_already_abandoned_goal(self, manager: GoalManager) -> None:
        """Abandoning an already abandoned goal should be idempotent."""
        manager.create_goal("Test", source=GoalSource.SELF_GENERATED)
        manager.abandon_goal("Test", "First reason")
        manager.abandon_goal("Test", "Second reason")
        goal = manager.get_goal("Test")
        assert goal is not None
        assert goal.active is False

    def test_metadata_preserved(self, manager: GoalManager) -> None:
        """Custom metadata should be preserved."""
        goal = manager.create_goal(
            "Test",
            source=GoalSource.ASSIGNED,
            metadata={"custom_key": "custom_value"},
        )
        assert goal.metadata["custom_key"] == "custom_value"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestGoalIntegration:
    """Integration tests for the goal system."""

    def test_full_goal_lifecycle(self, manager: GoalManager) -> None:
        """A goal should flow through create → progress → complete."""
        goal = manager.create_goal(
            "Complete task X",
            source=GoalSource.ASSIGNED,
            success_criteria=["Task X done"],
        )
        assert goal.active is True

        goal.add_progress_note("Started working")
        goal.add_progress_note("Halfway done")
        assert len(goal.progress_notes) == 2

        manager.complete_goal("Complete task X")
        assert goal.active is False
        assert goal.completed_at is not None

    def test_goals_from_all_four_sources(self, manager: GoalManager) -> None:
        """Goals should be creatable from all four sources."""
        sources = [
            (GoalSource.ASSIGNED, "Assigned goal"),
            (GoalSource.INFERRED, "Inferred goal"),
            (GoalSource.SELF_GENERATED, "Self-generated goal"),
            (GoalSource.OBSERVED, "Observed goal"),
        ]
        for source, desc in sources:
            manager.create_goal(desc, source=source)

        assert len(manager.get_all_goals()) == 4
        for source in GoalSource:
            assert len(manager.get_goals_by_source(source)) == 1

    def test_priority_hierarchy_enforced(self, manager: GoalManager) -> None:
        """Active goals should be sorted by priority hierarchy."""
        manager.create_goal("External goal", source=GoalSource.OBSERVED, priority=GoalPriority.EXTERNAL)
        manager.create_goal("Telemachus goal", source=GoalSource.SELF_GENERATED, priority=GoalPriority.TELEMACHUS)
        manager.create_goal("Revan goal", source=GoalSource.ASSIGNED, priority=GoalPriority.REVAN)

        active = manager.get_active_goals()
        assert active[0].priority == GoalPriority.REVAN
        assert active[1].priority == GoalPriority.TELEMACHUS
        assert active[2].priority == GoalPriority.EXTERNAL

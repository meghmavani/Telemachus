"""Cognition layer — learning, reflection, goals, projects, research, evolution."""

from telemachus.cognition.evolution import (
    EvolutionCheck,
    EvolutionEngine,
    EvolutionProposal,
    EvolutionStatus,
    EvolutionType,
)
from telemachus.cognition.goals import Goal, GoalManager, GoalPriority
from telemachus.cognition.learning import LearningEngine, LearningSignal, LearningType
from telemachus.cognition.projects import Project, ProjectManager, Task
from telemachus.cognition.reflection import ReflectionEngine, ReflectionOutput, ReflectionPhase
from telemachus.cognition.research import (
    EvidenceItem,
    ResearchConclusion,
    ResearchEngine,
    SubQuestion,
)

__all__ = [
    "EvidenceItem",
    "EvolutionCheck",
    "EvolutionEngine",
    "EvolutionProposal",
    "EvolutionStatus",
    "EvolutionType",
    "Goal",
    "GoalManager",
    "GoalPriority",
    "LearningEngine",
    "LearningSignal",
    "LearningType",
    "Project",
    "ProjectManager",
    "ReflectionEngine",
    "ReflectionOutput",
    "ReflectionPhase",
    "ResearchConclusion",
    "ResearchEngine",
    "SubQuestion",
    "Task",
]

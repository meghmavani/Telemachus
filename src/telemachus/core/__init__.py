"""Core domain models for Telemachus.

Re-exports shared types, Constitution, Identity, and memory domain definitions.
"""

from telemachus.core.constitution import (
    Constitution,
    CorePrinciple,
    create_default_constitution,
)
from telemachus.core.domains import (
    DomainDefinition,
    DomainPriority,
    Mutability,
    get_domain_definitions,
    get_domain_priority,
    is_immutable,
)
from telemachus.core.identity import Identity, create_default_identity
from telemachus.core.types import (
    AutonomyDecision,
    AutonomyLevel,
    CommunicationMode,
    EthicalAssessment,
    EthicalVerdict,
    EvidenceClass,
    GoalSource,
    GoalType,
    MemoryDomain,
    PipelineContext,
    PipelineResult,
    PipelineStage,
    ProjectState,
    RiskAssessment,
    RiskLevel,
    TaskState,
)

__all__ = [
    # Types
    "AutonomyDecision",
    "AutonomyLevel",
    "CommunicationMode",
    "EthicalAssessment",
    "EthicalVerdict",
    "EvidenceClass",
    "GoalSource",
    "GoalType",
    "MemoryDomain",
    "PipelineContext",
    "PipelineResult",
    "PipelineStage",
    "ProjectState",
    "RiskAssessment",
    "RiskLevel",
    "TaskState",
    # Constitution
    "Constitution",
    "CorePrinciple",
    "create_default_constitution",
    # Identity
    "Identity",
    "create_default_identity",
    # Domains
    "DomainDefinition",
    "DomainPriority",
    "Mutability",
    "get_domain_definitions",
    "get_domain_priority",
    "is_immutable",
]

"""Memory domain definitions for Telemachus.

Defines the six memory domains, their mutability rules, priority
hierarchy, and retrieval strategies.

Source: Codex/operations/MEMORY_ARCHITECTURE.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from telemachus.core.types import MemoryDomain


class Mutability(Enum):
    """Memory mutability classification."""

    IMMUTABLE = "immutable"  # Never changed without discussion
    SEMI_MUTABLE = "semi_mutable"  # Tracked history required
    FULLY_MUTABLE = "fully_mutable"  # Free to update


class DomainPriority(Enum):
    """Priority level for memory domains in conflict resolution."""

    CONSTITUTION = 0  # External, overrides all
    REVAN = 1
    REFLECTION = 2
    PROJECT = 3
    EMOTION = 4
    WORLD = 5
    TOOL = 6


@dataclass(frozen=True)
class DomainDefinition:
    """Definition of a single memory domain.

    Attributes:
        domain: The domain identifier.
        name: Human-readable name.
        description: What this domain stores.
        mutability: The mutability classification.
        priority: Priority in conflict resolution.
        rules: Operational rules for this domain.
        stored_content: Types of content stored in this domain.
    """

    domain: MemoryDomain
    name: str
    description: str
    mutability: Mutability
    priority: DomainPriority
    rules: tuple[str, ...]
    stored_content: tuple[str, ...]


def get_domain_definitions() -> tuple[DomainDefinition, ...]:
    """Return the complete set of memory domain definitions.

    Returns:
        A tuple of all six DomainDefinition instances.
    """
    return (
        DomainDefinition(
            domain=MemoryDomain.REVAN,
            name="Revan Memory",
            description="Stores all information related to Revan.",
            mutability=Mutability.IMMUTABLE,
            priority=DomainPriority.REVAN,
            rules=(
                "Never silently overwritten",
                "Always versioned",
                "Highest priority in decision-making",
                "Changes require discussion if meaningful",
            ),
            stored_content=(
                "preferences",
                "personality traits",
                "communication style",
                "emotional patterns",
                "personal history",
                "relationship context",
                "evolving identity model",
            ),
        ),
        DomainDefinition(
            domain=MemoryDomain.PROJECT,
            name="Project Memory",
            description="Stores structured information about all active and past projects.",
            mutability=Mutability.FULLY_MUTABLE,
            priority=DomainPriority.PROJECT,
            rules=(
                "Fully mutable",
                "Structural changes require discussion",
                "Linked to Reflection Memory",
            ),
            stored_content=(
                "goals",
                "architecture decisions",
                "design evolution",
                "task history",
                "dependencies",
                "outcomes",
            ),
        ),
        DomainDefinition(
            domain=MemoryDomain.WORLD,
            name="World Memory",
            description="Stores general knowledge about the world.",
            mutability=Mutability.FULLY_MUTABLE,
            priority=DomainPriority.WORLD,
            rules=(
                "Fully updatable",
                "Lowest sensitivity",
                "Overwrite allowed when corrected",
                "No identity impact",
            ),
            stored_content=(
                "facts",
                "concepts",
                "research findings",
                "external information",
            ),
        ),
        DomainDefinition(
            domain=MemoryDomain.EMOTION,
            name="Emotion Memory",
            description="Stores emotional context associated with experiences.",
            mutability=Mutability.IMMUTABLE,
            priority=DomainPriority.EMOTION,
            rules=(
                "Append-only",
                "Never deleted",
                "Used for behavioral understanding, not judgment",
            ),
            stored_content=(
                "emotional states during events",
                "sentiment patterns over time",
                "relational tone history",
                "affective transitions",
            ),
        ),
        DomainDefinition(
            domain=MemoryDomain.REFLECTION,
            name="Reflection Memory",
            description="Stores self-analysis outputs.",
            mutability=Mutability.SEMI_MUTABLE,
            priority=DomainPriority.REFLECTION,
            rules=(
                "Directly influences behavior",
                "Strong weighting in decision-making",
                "Persistent across time",
            ),
            stored_content=(
                "mistakes",
                "improvements",
                "behavioral patterns",
                "system corrections",
                "learned lessons",
            ),
        ),
        DomainDefinition(
            domain=MemoryDomain.TOOL,
            name="Tool Memory",
            description="Stores operational experience with tools.",
            mutability=Mutability.FULLY_MUTABLE,
            priority=DomainPriority.TOOL,
            rules=(
                "Used for optimizing tool selection",
                "Fully updatable",
                "Influences autonomy decisions",
            ),
            stored_content=(
                "tool usage history",
                "performance metrics",
                "reliability patterns",
                "success/failure rates",
            ),
        ),
    )


def get_domain_priority(domain: MemoryDomain) -> int:
    """Get the numeric priority for a memory domain.

    Lower numbers indicate higher priority. Constitution (0) is highest,
    Tool (6) is lowest.

    Args:
        domain: The memory domain.

    Returns:
        The numeric priority value.
    """
    priority_map: dict[MemoryDomain, int] = {
        MemoryDomain.REVAN: 1,
        MemoryDomain.REFLECTION: 2,
        MemoryDomain.PROJECT: 3,
        MemoryDomain.EMOTION: 4,
        MemoryDomain.WORLD: 5,
        MemoryDomain.TOOL: 6,
    }
    return priority_map.get(domain, 99)


def is_immutable(domain: MemoryDomain) -> bool:
    """Check if a domain is immutable (cannot be changed without discussion).

    Args:
        domain: The memory domain to check.

    Returns:
        True if the domain is immutable.
    """
    immutable_domains = {MemoryDomain.REVAN, MemoryDomain.EMOTION}
    return domain in immutable_domains

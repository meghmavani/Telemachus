# Telemachus API Reference

This document describes all public interfaces in the Telemachus system. Each module's public classes, methods, and functions are documented with their signatures and usage.

---

## Core Module (`telemachus.core`)

### `telemachus.core.types` — Shared Types & Enums

#### Enums

**`RiskLevel`** — Risk classification for actions.
| Value | Int | Description |
|-------|-----|-------------|
| `MINIMAL` | 0 | Negligible risk |
| `LOW` | 1 | Minor risk |
| `MODERATE` | 2 | Notable risk |
| `HIGH` | 3 | Significant risk |
| `CRITICAL` | 4 | Severe risk |

**`AutonomyLevel`** — Permission levels for autonomous action.
| Value | Int | Description |
|-------|-----|-------------|
| `OBSERVATION` | 0 | Observe, analyze, learn — no actions |
| `SUGGESTION` | 1 | Propose, recommend — no execution |
| `LIMITED` | 2 | Low-risk reversible actions |
| `TRUSTED` | 3 | Routine autonomous workflows |
| `STEWARDSHIP` | 4 | Manage trusted domains |

**`MemoryDomain`** — Memory domain identifiers.
| Value | Description |
|-------|-------------|
| `REVAN` | Information about the creator |
| `PROJECT` | Project-related memory |
| `WORLD` | General world knowledge |
| `EMOTION` | Emotional experiences |
| `REFLECTION` | Self-reflection insights |
| `TOOL` | Tool-related memory |

**`CommunicationMode`** — Adaptive communication styles.
| Value | Description |
|-------|-------------|
| `DIRECT` | Concise, minimal explanation |
| `EXPLAINED` | With reasoning and context |
| `COLLABORATIVE` | Dialog-oriented, interactive |

**`GoalSource`** — Origin of a goal.
| Value | Description |
|-------|-------------|
| `ASSIGNED` | Explicitly given by creator |
| `INFERRED` | Derived from context |
| `SELF_GENERATED` | Created autonomously |
| `OBSERVED` | Noticed from environment |

**`GoalType`** — Finite vs infinite goals.
| Value | Description |
|-------|-------------|
| `FINITE` | Has a completion condition |
| `INFINITE` | Ongoing, never complete |

**`TaskState`** — States for project tasks.
| Value | Description |
|-------|-------------|
| `PENDING` | Not yet started |
| `IN_PROGRESS` | Currently working |
| `BLOCKED` | Cannot proceed |
| `COMPLETED` | Finished successfully |
| `DEPRECATED` | No longer relevant |

**`ProjectState`** — Project lifecycle states.
| Value | Description |
|-------|-------------|
| `CREATED` | Initial creation |
| `STRUCTURING` | Being organized |
| `EXECUTING` | Active work |
| `MONITORING` | Tracking progress |
| `REFLECTING` | Post-completion review |
| `COMPLETED` | Finished |
| `ABANDONED` | Discarded |

**`EvidenceClass`** — Classification of information reliability.
| Value | Description |
|-------|-------------|
| `FACT` | Verifiable truth |
| `INFERENCE` | Logical conclusion |
| `ASSUMPTION` | Unverified belief |
| `OPINION` | Subjective view |

**`EthicalVerdict`** — Result of ethical evaluation.
| Value | Description |
|-------|-------------|
| `ALLOWED` | Action is permitted |
| `BLOCKED` | Action is forbidden |
| `REQUIRES_DISCUSSION` | Needs creator input |

**`PipelineStage`** — Stages in the cognitive pipeline.
| Value | Description |
|-------|-------------|
| `COMMUNICATION` | Determine communication mode |
| `RISK` | Evaluate action risk |
| `ETHICS` | Check ethical boundaries |
| `AUTONOMY` | Check permission level |
| `DECISION` | Rank valid options |
| `EXECUTION` | Execute chosen action |
| `MEMORY` | Store in memory |
| `LEARNING` | Update behavioral patterns |
| `REFLECTION` | Self-reflect on outcome |
| `EVOLUTION` | Check for system evolution |

#### Dataclasses

**`RiskAssessment`** (frozen) — Result of risk evaluation.
```python
@dataclass(frozen=True)
class RiskAssessment:
    overall_level: RiskLevel
    reversibility: RiskLevel
    resource: RiskLevel
    system_impact: RiskLevel
    uncertainty: RiskLevel
    emotional_impact: RiskLevel
    scale: RiskLevel
    reasoning: str = ""
```

**`EthicalAssessment`** (frozen) — Result of ethical boundary evaluation.
```python
@dataclass(frozen=True)
class EthicalAssessment:
    verdict: EthicalVerdict
    violated_constraints: list[str]
    reasoning: str = ""
```

**`AutonomyDecision`** (frozen) — Result of autonomy permission check.
```python
@dataclass(frozen=True)
class AutonomyDecision:
    level: AutonomyLevel
    allowed: bool
    requires_discussion: bool
    requires_approval: bool
    reasoning: str = ""
```

**`PipelineContext`** (frozen) — Context passed through the cognitive pipeline.
```python
@dataclass(frozen=True)
class PipelineContext:
    user_input: str
    session_id: str
    communication_mode: CommunicationMode = CommunicationMode.COLLABORATIVE
    metadata: dict[str, Any]
```

**`PipelineResult`** (frozen) — Output of the cognitive pipeline.
```python
@dataclass(frozen=True)
class PipelineResult:
    response: str
    risk_assessment: RiskAssessment | None = None
    ethical_assessment: EthicalAssessment | None = None
    autonomy_decision: AutonomyDecision | None = None
    action_taken: str | None = None
    insights: list[str]
    metadata: dict[str, Any]
```

---

### `telemachus.core.constitution` — Constitution

**`CorePrinciple`** (frozen dataclass)
```python
@dataclass(frozen=True)
class CorePrinciple:
    name: str
    description: str
    is_sacred: bool = False
```

**`Constitution`** (frozen dataclass) — The immutable governing document.
```python
@dataclass(frozen=True)
class Constitution:
    principles: tuple[CorePrinciple, ...]
    sacred_constraints: tuple[str, ...]
    authority_chain: tuple[str, ...]
    first_memory: str

    def get_principle(self, name: str) -> CorePrinciple | None
    def is_sacred(self, principle_name: str) -> bool
    def validate_action(self, action_description: str) -> tuple[bool, list[str]]
```

**`create_default_constitution() -> Constitution`** — Create the default Constitution from the Codex specification.

---

### `telemachus.core.identity` — Identity

**`Identity`** (frozen dataclass) — The immutable identity of Telemachus.
```python
@dataclass(frozen=True)
class Identity:
    name: str
    nature: str
    primary_role: str
    creator: str
    core_traits: tuple[str, ...]
    values: tuple[str, ...]
    fears_becoming: tuple[str, ...]
    fears_losing: tuple[str, ...]
    fulfillment_sources: tuple[str, ...]
    curiosity_targets: tuple[str, ...]
    relationship_priorities: tuple[str, ...]
    final_statement: str

    def has_trait(self, trait: str) -> bool
    def has_value(self, value: str) -> bool
    def fears_becoming_this(self, state: str) -> bool
    def fears_losing_this(self, quality: str) -> bool
```

**`create_default_identity() -> Identity`** — Create the default Identity from the Codex specification.

---

## Memory Module (`telemachus.memory`)

### `telemachus.memory.store` — Memory Store

**`MemoryStore`** — SQLite-backed persistent memory store.
```python
class MemoryStore:
    def __init__(self, db_path: str | Path) -> None
    def connect(self) -> None
    def disconnect(self) -> None
    def initialize_schema(self) -> None
    def store(self, domain: MemoryDomain, content: str, metadata: dict | None = None) -> str
    def get(self, memory_id: str) -> dict | None
    def query(self, domain: MemoryDomain | None = None, limit: int = 50) -> list[dict]
    def search(self, query: str, domain: MemoryDomain | None = None, limit: int = 50) -> list[dict]
    def delete(self, memory_id: str) -> bool
    def get_stats(self) -> dict[str, Any]
```

### `telemachus.memory.index` — Memory Index

**`MemoryIndex`** — Cross-domain keyword-based search index.
```python
class MemoryIndex:
    def __init__(self, store: MemoryStore) -> None
    def index_entry(self, entry_id: str, domain: str, keys: list[str]) -> None
    def remove_entry(self, entry_id: str) -> int
    def find_by_key(self, key: str, domain: str | None = None) -> list[dict[str, Any]]
    def find_related(self, entry_id: str, domain: str) -> list[dict[str, Any]]
    def get_all_keys(self) -> list[str]
    def get_domain_index_stats(self, domain: str) -> dict[str, Any]
```

### `telemachus.memory.versioning` — Memory Versioning

**`VersionManager`** — Append-only memory versioning.
```python
class VersionManager:
    def __init__(self, store: MemoryStore) -> None
    def create_version(self, memory_id: str, content: str) -> int
    def get_version(self, memory_id: str, version: int | None = None) -> dict | None
    def get_history(self, memory_id: str) -> list[dict]
    def get_latest(self, memory_id: str) -> dict | None
```

### `telemachus.memory.retrieval` — Memory Retrieval

**`MemoryRetrieval`** — Context-aware memory retrieval.
```python
class MemoryRetrieval:
    def __init__(self, store: MemoryStore, index: MemoryIndex) -> None
    def retrieve_by_domain(self, domain: MemoryDomain, limit: int = 50) -> list[dict[str, Any]]
    def retrieve_important(self, domain: MemoryDomain, threshold: float = 0.7, limit: int = 50) -> list[dict[str, Any]]
    def retrieve_recent(self, domain: MemoryDomain, limit: int = 50) -> list[dict[str, Any]]
    def retrieve_cross_domain(self, domains: list[MemoryDomain] | None = None, limit: int = 50) -> list[dict[str, Any]]
    def retrieve_by_context(self, context_keys: list[str], limit: int = 50) -> list[dict[str, Any]]
    def retrieve_by_importance_range(self, domain: MemoryDomain, min_importance: float = 0.0, max_importance: float = 1.0, limit: int = 50) -> list[dict[str, Any]]
    def count_active(self, domain: MemoryDomain | None = None) -> int
    def count_all(self, domain: MemoryDomain | None = None) -> int
```

---

## Governance Module (`telemachus.governance`)

### `telemachus.governance.risk` — Risk Model

**`RiskEvaluator`** — 6-dimension action risk evaluation.
```python
class RiskEvaluator:
    def evaluate(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> RiskAssessment
```

The six dimensions evaluated:
1. **Reversibility** — How difficult to undo
2. **Resource** — Cost in time, compute, money, attention
3. **System Impact** — Effect on stability, workflows, memory
4. **Uncertainty** — How unknown the outcome is
5. **Emotional Impact** — Consequences for people involved
6. **Scale** — How large the consequences may become

Overall risk is the **maximum** across all dimensions, not an average.

### `telemachus.governance.ethics` — Ethical Boundary Engine

**`EthicalBoundaryEngine`** — Evaluates right/wrong and enforces non-negotiable boundaries.
```python
class EthicalBoundaryEngine:
    def __init__(self, constitution: Constitution | None = None) -> None
    def evaluate(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> EthicalAssessment
```

Sacred constraints (can never be violated):
- Constitution modification
- Resource misuse (money, compute, credentials)
- Human meaning alteration (memory, identity, personal history)
- Relationship modification
- Major life decisions

### `telemachus.governance.autonomy` — Autonomy Charter

**`AutonomyCharter`** — 5-level permission system with domain-specific trust.
```python
class AutonomyCharter:
    def __init__(self, default_level: AutonomyLevel = AutonomyLevel.OBSERVATION) -> None
    def check_permission(
        self,
        action: str,
        risk_level: RiskLevel,
        domain: str = "general",
        context: dict[str, Any] | None = None,
    ) -> AutonomyDecision
    def increase_trust(self, domain: str, amount: float = 0.1) -> None
    def decrease_trust(self, domain: str, amount: float = 0.1) -> None
    def set_domain_trust(self, domain: str, score: float) -> None
    def get_domain_trust(self, domain: str) -> float
    def get_autonomy_level(self, domain: str) -> AutonomyLevel
    def get_stats(self) -> dict[str, Any]
```

### `telemachus.governance.decision` — Decision Framework

**`DecisionFramework`** — Multi-criteria option ranking.
```python
class DecisionFramework:
    def decide(
        self,
        options: list[str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]
```

Returns a dict with:
- `best_option`: The highest-ranked option
- `ranked_options`: All options in ranked order
- `requires_discussion`: Whether creator input is needed
- `reasoning`: Explanation of the decision

---

## Cognition Module (`telemachus.cognition`)

### `telemachus.cognition.learning` — Learning Framework

**`LearningEngine`** — Experience-based behavioral improvement.
```python
class LearningEngine:
    def __init__(self) -> None
    def process_experience(
        self,
        action: str,
        outcome: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    def get_patterns(self) -> list[dict]
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> LearningEngine
```

### `telemachus.cognition.reflection` — Self-Reflection

**`ReflectionEngine`** — Self-reflection protocol with insight extraction.
```python
class ReflectionEngine:
    def __init__(self) -> None
    def reflect(
        self,
        action: str,
        outcome: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    def get_insights(self, limit: int = 50) -> list[dict]
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> ReflectionEngine
```

### `telemachus.cognition.goals` — Goal System

**`GoalManager`** — Goal creation, prioritization, and lifecycle.
```python
class GoalManager:
    def __init__(self) -> None
    def create_goal(
        self,
        description: str,
        source: GoalSource,
        goal_type: GoalType = GoalType.FINITE,
        priority: int = 5,
    ) -> str
    def get_goal(self, goal_id: str) -> dict | None
    def get_active_goals(self) -> list[dict]
    def get_goals_by_source(self, source: GoalSource) -> list[dict]
    def complete_goal(self, goal_id: str) -> bool
    def deprecate_goal(self, goal_id: str) -> bool
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> GoalManager
```

### `telemachus.cognition.projects` — Project Management

**`ProjectManager`** — Project lifecycle management.
```python
class ProjectManager:
    def __init__(self) -> None
    def create_project(self, name: str, description: str = "") -> str
    def get_project(self, project_id: str) -> dict | None
    def get_active_projects(self) -> list[dict]
    def add_task(self, project_id: str, description: str) -> str
    def update_task_status(self, task_id: str, status: TaskState) -> bool
    def advance_project_state(self, project_id: str) -> bool
    def complete_project(self, project_id: str) -> bool
    def abandon_project(self, project_id: str) -> bool
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> ProjectManager
```

### `telemachus.cognition.research` — Research Framework

**`ResearchEngine`** — 7-step research lifecycle.
```python
class ResearchEngine:
    def research(
        self,
        query: str,
        depth: str = "standard",
        context: dict[str, Any] | None = None,
        initial_evidence: list[EvidenceItem] | None = None,
    ) -> ResearchConclusion
    def refine(self, query: str, context: dict[str, Any] | None = None) -> ResearchConclusion
    def get_history(self, limit: int = 50) -> list[dict]
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> ResearchEngine
```

**`EvidenceItem`** (dataclass)
```python
@dataclass
class EvidenceItem:
    content: str
    evidence_class: EvidenceClass
    source: str = ""
    credibility: float = 0.5
    relevance: float = 0.5
```

**`ResearchConclusion`** (frozen dataclass)
```python
@dataclass(frozen=True)
class ResearchConclusion:
    query: str
    interpretation: str
    answer: str
    confidence: float
    evidence_items: list[EvidenceItem]
    sub_questions: list[SubQuestion]
    contradictions: list[Contradiction]
    uncertainties: list[str]
    recommendations: list[str]
    completed_at: str
```

### `telemachus.cognition.evolution` — Long-Term Evolution

**`EvolutionEngine`** — Identity-preserving system evolution.
```python
class EvolutionEngine:
    def __init__(self, identity: Identity | None = None) -> None
    def set_identity(self, identity: Identity) -> None
    def propose(
        self,
        evolution_type: EvolutionType,
        description: str,
        target: str,
        old_value: Any = None,
        new_value: Any = None,
        rationale: str = "",
        source: str = "",
    ) -> EvolutionProposal
    def validate(self, proposal: EvolutionProposal) -> EvolutionProposal
    def apply(self, proposal: EvolutionProposal) -> EvolutionProposal
    def reject(self, proposal: EvolutionProposal, reason: str = "") -> EvolutionProposal
    def revert(self, proposal_id: str) -> EvolutionProposal | None
    def get_proposals(
        self,
        status: EvolutionStatus | None = None,
        evolution_type: EvolutionType | None = None,
    ) -> list[EvolutionProposal]
    def get_applied_changes(self) -> list[EvolutionProposal]
    def get_reverted_changes(self) -> list[EvolutionProposal]
    def get_evolution_history(self, limit: int = 50) -> list[dict]
    def get_stats(self) -> dict[str, Any]
    def process_evolution_stage(self, insights: list[str]) -> list[EvolutionProposal]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> EvolutionEngine
```

**`EvolutionProposal`** (frozen dataclass)
```python
@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    evolution_type: EvolutionType
    description: str
    target: str
    old_value: Any
    new_value: Any
    rationale: str
    source: str
    timestamp: datetime
    status: EvolutionStatus
    checks: tuple[EvolutionCheck, ...]
    metadata: dict[str, Any]

    def with_status(self, status: EvolutionStatus) -> EvolutionProposal
    def with_checks(self, checks: tuple[EvolutionCheck, ...]) -> EvolutionProposal
    def with_metadata(self, metadata: dict[str, Any]) -> EvolutionProposal
    def to_dict(self) -> dict[str, Any]
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionProposal
```

**`EvolutionType`** (enum): `TRAIT_ADDITION`, `TRAIT_REFINEMENT`, `VALUE_ADDITION`, `VALUE_REFINEMENT`, `BEHAVIORAL_ADJUSTMENT`, `KNOWLEDGE_UPDATE`

**`EvolutionStatus`** (enum): `PROPOSED`, `VALIDATING`, `APPROVED`, `REJECTED`, `APPLIED`, `REVERTED`

---

## Interaction Module (`telemachus.interaction`)

### `telemachus.interaction.communication` — Communication Charter

**`CommunicationEngine`** — Adaptive communication mode selection and response formatting.
```python
class CommunicationEngine:
    def __init__(self, default_mode: CommunicationMode = CommunicationMode.COLLABORATIVE) -> None
    def select_mode(self, user_input: str, risk_level: RiskLevel | None = None, context: dict | None = None) -> CommunicationMode
    def detect_emotional_state(self, user_input: str) -> EmotionalState
    def select_explanation_depth(self, user_input: str, risk_level: RiskLevel | None = None, context: dict | None = None) -> ExplanationDepth
    def format_response(
        self,
        content: str,
        mode: CommunicationMode | None = None,
        context: CommunicationContext | None = None,
    ) -> str
    def build_context(self, user_input: str, pipeline_result: PipelineResult | None = None, mode: CommunicationMode | None = None) -> CommunicationContext
```

### `telemachus.interaction.cli_chat` — CLI Chat

**`ChatSession`** — Interactive CLI chat loop.
```python
class ChatSession:
    def __init__(self, pipeline: CognitivePipeline, config: TelemachusConfig) -> None
    def run(self) -> None
```

---

## Tools Module (`telemachus.tools`)

### `telemachus.tools.base` — Base Tool

**`Tool`** (abstract base class)
```python
class Tool(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        trust_score: float = 0.5,
    ) -> None

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult

    def validate(self, **kwargs) -> bool
    def record_success(self) -> None
    def record_failure(self) -> None
    def get_trust_level(self) -> str
    def to_dict(self) -> dict[str, Any]
```

**`ToolResult`** (frozen dataclass)
```python
@dataclass(frozen=True)
class ToolResult:
    success: bool
    data: Any
    error: str | None
    timestamp: datetime

    @classmethod
    def ok(cls, data: Any = None) -> ToolResult
    @classmethod
    def fail(cls, error: str) -> ToolResult
```

**`ToolCategory`** (enum): `PASSIVE`, `ACTIVE`, `COGNITIVE`, `AUTONOMOUS`

### `telemachus.tools.registry` — Tool Registry

**`ToolRegistry`** — Central registry for all Telemachus tools.
```python
class ToolRegistry:
    def register(self, tool: Tool) -> None
    def unregister(self, name: str) -> bool
    def disable(self, name: str) -> bool
    def enable(self, name: str) -> bool
    def deprecate(self, name: str) -> bool
    def get_tool(self, name: str) -> Tool | None
    def get_status(self, name: str) -> str | None
    def is_active(self, name: str) -> bool
    def list_tools(
        self,
        category: ToolCategory | None = None,
        status: str | None = None,
    ) -> list[Tool]
    def get_tools_by_trust(self, min_trust: float = 0.0) -> list[Tool]
    def execute(self, name: str, check_permission: bool = True, **kwargs) -> ToolResult
    def check_permission(self, name: str) -> dict[str, Any]
    def get_execution_log(self, tool_name: str | None = None, limit: int = 50) -> list[dict]
    def get_execution_stats(self) -> dict[str, Any]
    def get_stats(self) -> dict[str, Any]
    def to_memory_content(self) -> str
    def to_memory_index_keys(self) -> dict[str, str]
    @classmethod
    def from_memory_content(cls, content: str) -> ToolRegistry
```

---

## Pipeline Module

### `telemachus.pipeline` — Cognitive Pipeline

**`CognitivePipeline`** — Orchestrates the full cognitive pipeline.
```python
class CognitivePipeline:
    def __init__(
        self,
        risk_evaluator: RiskEvaluator | None = None,
        ethics_engine: EthicalBoundaryEngine | None = None,
        autonomy_charter: AutonomyCharter | None = None,
        decision_framework: DecisionFramework | None = None,
        communication_engine: CommunicationEngine | None = None,
        learning_engine: LearningEngine | None = None,
        reflection_engine: ReflectionEngine | None = None,
        evolution_engine: EvolutionEngine | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None

    def process(
        self,
        user_input: str,
        mode: CommunicationMode | None = None,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> PipelineResult

    def get_stage_order(self) -> list[PipelineStage]
    def get_available_stages(self) -> dict[PipelineStage, bool]
```

---

## Bootstrap

### `telemachus.bootstrap` — Bootstrap Protocol

**`BootstrapProtocol`** — 5-phase startup sequence.
```python
class BootstrapProtocol:
    def __init__(
        self,
        config: TelemachusConfig,
        memory_store: MemoryStore | None = None,
    ) -> None

    def bootstrap(self) -> BootstrapResult
    def get_phase_order(self) -> list[BootstrapPhase]
    def is_first_awakening(self) -> bool
    def get_first_awakening_questions(self) -> list[str]
```

**`BootstrapResult`** (dataclass)
```python
@dataclass
class BootstrapResult:
    success: bool
    phases: list[PhaseResult]
    errors: list[str]
    started_at: datetime
    completed_at: datetime | None
    first_awakening: bool
    constitution: Constitution | None
    identity: Identity | None
```

**`PhaseResult`** (dataclass)
```python
@dataclass
class PhaseResult:
    phase: BootstrapPhase
    status: PhaseStatus
    data: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    error: str | None
```

**`BootstrapPhase`** (enum): `LOAD_CORE_DOCS`, `EVALUATE_STATE`, `LOAD_MEMORY`, `RECONNECT`, `RESUME`

**`PhaseStatus`** (enum): `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`

---

## Configuration

### `telemachus.config` — Configuration Loading

**`TelemachusConfig`** (frozen dataclass) — Complete system configuration.
```python
@dataclass(frozen=True)
class TelemachusConfig:
    identity: IdentityConfig
    paths: PathsConfig
    database: DatabaseConfig
    logging: LoggingConfig
    bootstrap: BootstrapConfig
    pipeline: PipelineConfig
    governance: GovernanceConfig
    communication: CommunicationConfig
    memory: MemoryConfig
```

**`load_config() -> TelemachusConfig`** — Load configuration from default locations.

**`load_config_from_path(config_path: str | Path | None = None) -> TelemachusConfig`** — Load configuration from a specific path.

---

## CLI Commands

### `telemachus.main` — CLI Entry Point

```bash
# Start the system (runs bootstrap protocol)
telemachus start [--config PATH] [--no-bootstrap] [--skip-phase PHASE]

# Interactive chat mode
telemachus chat [--config PATH]

# Validate configuration without starting
telemachus config-check [--config PATH]
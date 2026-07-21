"""Research Framework — structured understanding formation under uncertainty.

Research is not information gathering. Research is the process of converging
on truth under uncertainty through evidence, reasoning, and validation.

The 7-step research lifecycle:
1. Query Interpretation — understand what is being asked
2. Decomposition — break complex questions into components
3. Information Gathering — collect evidence from sources
4. Source Evaluation — assess credibility, consistency, relevance
5. Synthesis — combine evidence, resolve contradictions
6. Conclusion Formation — explicit, justified, confidence-labeled
7. Uncertainty Declaration — state what is unknown and why
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from telemachus.core.types import EvidenceClass

logger = logging.getLogger("telemachus.cognition.research")


# ---------------------------------------------------------------------------
# Research dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EvidenceItem:
    """A single piece of evidence gathered during research.

    Attributes:
        content: The evidence content.
        source: Where the evidence came from.
        evidence_class: Classification (fact, inference, assumption, opinion).
        credibility: Assessed credibility score (0.0-1.0).
        relevance: Relevance to the research question (0.0-1.0).
        notes: Additional observations about this evidence.
    """

    content: str
    source: str
    evidence_class: EvidenceClass = EvidenceClass.ASSUMPTION
    credibility: float = 0.5
    relevance: float = 0.5
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate credibility and relevance ranges."""
        if not 0.0 <= self.credibility <= 1.0:
            raise ValueError("Credibility must be between 0.0 and 1.0")
        if not 0.0 <= self.relevance <= 1.0:
            raise ValueError("Relevance must be between 0.0 and 1.0")


@dataclass
class SubQuestion:
    """A decomposed component of a complex research question.

    Attributes:
        question: The sub-question text.
        assumptions: Assumptions underlying this sub-question.
        dependencies: Other sub-questions this depends on.
        status: Current status (pending, answered, unresolved).
        answer: The answer found, if any.
        confidence: Confidence in the answer (0.0-1.0).
    """

    question: str
    assumptions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    answer: str | None = None
    confidence: float = 0.0


@dataclass
class Contradiction:
    """A detected contradiction between evidence items.

    Attributes:
        item_a: First conflicting evidence content.
        item_b: Second conflicting evidence content.
        analysis: Why the conflict exists.
        resolved: Whether the contradiction has been resolved.
        resolution: How it was resolved, if applicable.
    """

    item_a: str
    item_b: str
    analysis: str = ""
    resolved: bool = False
    resolution: str | None = None


@dataclass
class ResearchConclusion:
    """The final output of a research session.

    Attributes:
        query: The original research question.
        interpretation: How the query was interpreted.
        answer: The synthesized answer.
        confidence: Overall confidence in the conclusion (0.0-1.0).
        evidence_summary: Summary of evidence used.
        uncertainties: Declared remaining uncertainties.
        recommendations: Actionable recommendations based on findings.
        sub_questions: Decomposed sub-questions and their answers.
        contradictions: Detected and resolved contradictions.
        evidence_items: All evidence gathered.
        started_at: When research began.
        completed_at: When research concluded.
    """

    query: str
    interpretation: str
    answer: str
    confidence: float
    evidence_summary: str = ""
    uncertainties: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    sub_questions: list[SubQuestion] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Research Engine
# ---------------------------------------------------------------------------


class ResearchEngine:
    """Implements the 7-step research lifecycle.

    The engine guides research from query interpretation through conclusion
    formation, maintaining epistemic honesty at every step. It explicitly
    tracks evidence classification, contradictions, and uncertainty.

    Research depth adapts based on question importance, risk level, ambiguity,
    and real-world impact.
    """

    def __init__(self) -> None:
        """Initialize the research engine."""
        self._history: list[ResearchConclusion] = []

    # ------------------------------------------------------------------
    # Main research method
    # ------------------------------------------------------------------

    def research(
        self,
        query: str,
        *,
        depth: str = "standard",
        context: dict[str, Any] | None = None,
        initial_evidence: list[EvidenceItem] | None = None,
    ) -> ResearchConclusion:
        """Execute the full 7-step research lifecycle.

        Args:
            query: The research question to investigate.
            depth: Research depth ('quick', 'standard', 'deep').
            context: Additional context (risk level, importance, etc.).
            initial_evidence: Pre-existing evidence to incorporate.

        Returns:
            A ResearchConclusion with the synthesized findings.

        Raises:
            ValueError: If query is empty.
        """
        if not query or not query.strip():
            raise ValueError("Research query must not be empty")

        ctx = context or {}
        evidence: list[EvidenceItem] = list(initial_evidence or [])

        # Step 1: Query Interpretation
        interpretation = self._interpret_query(query, ctx)
        logger.info("Research: interpreted '%s' as '%s'", query[:60], interpretation)

        # Step 2: Decomposition
        sub_questions = self._decompose(query, interpretation, ctx, depth)
        logger.debug("Research: decomposed into %d sub-questions", len(sub_questions))

        # Step 3: Information Gathering
        new_evidence = self._gather_information(
            query, interpretation, sub_questions, ctx, depth
        )
        evidence.extend(new_evidence)
        logger.debug("Research: gathered %d evidence items", len(new_evidence))

        # Step 4: Source Evaluation
        evaluated = self._evaluate_sources(evidence)
        logger.debug("Research: evaluated %d sources", len(evaluated))

        # Step 5: Synthesis
        synthesis_result = self._synthesize(
            query, interpretation, sub_questions, evaluated, ctx
        )
        logger.info("Research: synthesis complete")

        # Step 6: Conclusion Formation
        conclusion = self._form_conclusion(
            query,
            interpretation,
            sub_questions,
            evaluated,
            synthesis_result,
            ctx,
        )

        # Step 7: Uncertainty Declaration
        uncertainties = self._declare_uncertainties(
            conclusion, evaluated, synthesis_result
        )
        conclusion.uncertainties = uncertainties
        conclusion.completed_at = datetime.now(UTC)

        # Store in history
        self._history.append(conclusion)
        logger.info(
            "Research complete: '%s' — confidence=%.2f, %d uncertainties",
            query[:60],
            conclusion.confidence,
            len(uncertainties),
        )

        return conclusion

    # ------------------------------------------------------------------
    # Step 1: Query Interpretation
    # ------------------------------------------------------------------

    @staticmethod
    def _interpret_query(
        query: str, ctx: dict[str, Any]
    ) -> str:
        """Interpret what is being asked and what the real intent is.

        Args:
            query: The raw query string.
            ctx: Research context.

        Returns:
            A clear interpretation of the query.
        """
        query_lower = query.lower().strip()

        # Detect question type for better interpretation
        if query_lower.startswith("what is"):
            return f"Definition/explanation request: {query}"
        if query_lower.startswith("how do") or query_lower.startswith("how to"):
            return f"Procedural/how-to request: {query}"
        if query_lower.startswith("why"):
            return f"Causal explanation request: {query}"
        if query_lower.startswith("which") or query_lower.startswith("what should"):
            return f"Decision support request: {query}"
        if query_lower.startswith("compare") or " vs " in query_lower:
            return f"Comparison request: {query}"
        if "?" in query:
            return f"Direct question: {query}"

        return f"General inquiry: {query}"

    # ------------------------------------------------------------------
    # Step 2: Decomposition
    # ------------------------------------------------------------------

    @staticmethod
    def _decompose(
        query: str,
        interpretation: str,
        ctx: dict[str, Any],
        depth: str,
    ) -> list[SubQuestion]:
        """Break a complex question into sub-questions.

        Args:
            query: The original query.
            interpretation: The interpreted query.
            ctx: Research context.
            depth: Research depth level.

        Returns:
            List of SubQuestion instances.
        """
        sub_questions: list[SubQuestion] = []

        # For deep research, decompose more thoroughly
        if depth == "deep":
            sub_questions.append(
                SubQuestion(
                    question=f"What are the key concepts involved in: {query}?",
                    assumptions=["The query involves multiple concepts"],
                )
            )
            sub_questions.append(
                SubQuestion(
                    question=f"What evidence exists regarding: {query}?",
                    assumptions=["Evidence can be gathered"],
                )
            )
            sub_questions.append(
                SubQuestion(
                    question=f"What are the implications or consequences of: {query}?",
                    assumptions=["The query has practical implications"],
                )
            )
        elif depth == "standard":
            sub_questions.append(
                SubQuestion(
                    question=f"What is the core of: {query}?",
                    assumptions=["The query has a definable core"],
                )
            )
            sub_questions.append(
                SubQuestion(
                    question=f"What evidence supports conclusions about: {query}?",
                    assumptions=["Evidence exists or can be inferred"],
                )
            )
        else:  # quick
            sub_questions.append(
                SubQuestion(
                    question=f"What is the direct answer to: {query}?",
                    assumptions=["A direct answer is possible"],
                )
            )

        return sub_questions

    # ------------------------------------------------------------------
    # Step 3: Information Gathering
    # ------------------------------------------------------------------

    @staticmethod
    def _gather_information(
        query: str,
        interpretation: str,
        sub_questions: list[SubQuestion],
        ctx: dict[str, Any],
        depth: str,
    ) -> list[EvidenceItem]:
        """Gather evidence from available sources.

        In a full implementation, this would query memory, external APIs,
        and perform logical inference. The current implementation provides
        the structural framework for evidence collection.

        Args:
            query: The original query.
            interpretation: The interpreted query.
            sub_questions: Decomposed sub-questions.
            ctx: Research context.
            depth: Research depth level.

        Returns:
            List of EvidenceItem instances.
        """
        evidence: list[EvidenceItem] = []

        # Gather from context if provided
        if ctx.get("known_facts"):
            for fact in ctx["known_facts"]:
                evidence.append(
                    EvidenceItem(
                        content=str(fact),
                        source="provided_context",
                        evidence_class=EvidenceClass.FACT,
                        credibility=0.9,
                        relevance=0.8,
                    )
                )

        if ctx.get("assumptions"):
            for assumption in ctx["assumptions"]:
                evidence.append(
                    EvidenceItem(
                        content=str(assumption),
                        source="provided_context",
                        evidence_class=EvidenceClass.ASSUMPTION,
                        credibility=0.4,
                        relevance=0.6,
                    )
                )

        # Logical inference from the query itself
        evidence.append(
            EvidenceItem(
                content=f"Query interpretation: {interpretation}",
                source="logical_inference",
                evidence_class=EvidenceClass.INFERENCE,
                credibility=0.7,
                relevance=1.0,
                notes="Derived from query analysis",
            )
        )

        # For deeper research, add more inference items
        if depth in ("standard", "deep"):
            for sq in sub_questions:
                evidence.append(
                    EvidenceItem(
                        content=f"Sub-question identified: {sq.question}",
                        source="decomposition",
                        evidence_class=EvidenceClass.INFERENCE,
                        credibility=0.6,
                        relevance=0.7,
                        notes=f"Assumptions: {', '.join(sq.assumptions)}",
                    )
                )

        return evidence

    # ------------------------------------------------------------------
    # Step 4: Source Evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_sources(
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        """Evaluate each evidence item for credibility and consistency.

        Args:
            evidence: Raw evidence items.

        Returns:
            Evaluated evidence items with adjusted credibility.
        """
        evaluated: list[EvidenceItem] = []

        for item in evidence:
            # Facts get higher credibility
            if item.evidence_class == EvidenceClass.FACT:
                adjusted = min(1.0, item.credibility + 0.1)
            elif item.evidence_class == EvidenceClass.OPINION:
                adjusted = max(0.1, item.credibility - 0.1)
            else:
                adjusted = item.credibility

            evaluated.append(
                EvidenceItem(
                    content=item.content,
                    source=item.source,
                    evidence_class=item.evidence_class,
                    credibility=adjusted,
                    relevance=item.relevance,
                    notes=item.notes,
                )
            )

        return evaluated

    # ------------------------------------------------------------------
    # Step 5: Synthesis
    # ------------------------------------------------------------------

    @staticmethod
    def _synthesize(
        query: str,
        interpretation: str,
        sub_questions: list[SubQuestion],
        evidence: list[EvidenceItem],
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Synthesize evidence into coherent understanding.

        Synthesis combines evidence, resolves contradictions where possible,
        identifies gaps, and builds structured understanding.

        Args:
            query: The original query.
            interpretation: The interpreted query.
            sub_questions: Decomposed sub-questions.
            evidence: Evaluated evidence items.
            ctx: Research context.

        Returns:
            Dict with synthesis results including key_findings, gaps,
            contradictions, and overall coherence.
        """
        # Separate evidence by class
        facts = [e for e in evidence if e.evidence_class == EvidenceClass.FACT]
        inferences = [e for e in evidence if e.evidence_class == EvidenceClass.INFERENCE]
        assumptions = [e for e in evidence if e.evidence_class == EvidenceClass.ASSUMPTION]
        opinions = [e for e in evidence if e.evidence_class == EvidenceClass.OPINION]

        # Detect contradictions
        contradictions: list[Contradiction] = []
        for i, e1 in enumerate(evidence):
            for e2 in evidence[i + 1 :]:
                if ResearchEngine._are_contradictory(e1.content, e2.content):
                    contradictions.append(
                        Contradiction(
                            item_a=e1.content[:100],
                            item_b=e2.content[:100],
                            analysis="Potential semantic contradiction detected",
                        )
                    )

        # Identify gaps
        gaps: list[str] = []
        if not facts:
            gaps.append("No verified facts available")
        if len(evidence) < 3:
            gaps.append("Limited evidence — conclusions may be preliminary")

        # Compute overall coherence
        avg_credibility = (
            sum(e.credibility for e in evidence) / len(evidence) if evidence else 0.0
        )
        avg_relevance = (
            sum(e.relevance for e in evidence) / len(evidence) if evidence else 0.0
        )
        coherence = (avg_credibility + avg_relevance) / 2

        return {
            "key_findings": [e.content for e in evidence if e.credibility >= 0.6],
            "fact_count": len(facts),
            "inference_count": len(inferences),
            "assumption_count": len(assumptions),
            "opinion_count": len(opinions),
            "gaps": gaps,
            "contradictions": contradictions,
            "coherence": coherence,
            "evidence_summary": (
                f"Analysis based on {len(facts)} facts, {len(inferences)} inferences, "
                f"{len(assumptions)} assumptions, and {len(opinions)} opinions. "
                f"Overall coherence: {coherence:.2f}"
            ),
        }

    @staticmethod
    def _are_contradictory(content_a: str, content_b: str) -> bool:
        """Simple heuristic for detecting contradictory statements.

        Args:
            content_a: First content string.
            content_b: Second content string.

        Returns:
            True if the contents appear contradictory.
        """
        a_lower = content_a.lower()
        b_lower = content_b.lower()

        # Check for negation patterns
        negation_pairs = [
            ("is", "is not"),
            ("can", "cannot"),
            ("should", "should not"),
            ("always", "never"),
            ("increase", "decrease"),
            ("true", "false"),
        ]
        for pos, neg in negation_pairs:
            if pos in a_lower and neg in b_lower:
                return True
            if neg in a_lower and pos in b_lower:
                return True

        return False

    # ------------------------------------------------------------------
    # Step 6: Conclusion Formation
    # ------------------------------------------------------------------

    @staticmethod
    def _form_conclusion(
        query: str,
        interpretation: str,
        sub_questions: list[SubQuestion],
        evidence: list[EvidenceItem],
        synthesis: dict[str, Any],
        ctx: dict[str, Any],
    ) -> ResearchConclusion:
        """Form an explicit, justified, confidence-labeled conclusion.

        Args:
            query: The original query.
            interpretation: The interpreted query.
            sub_questions: Decomposed sub-questions.
            evidence: Evaluated evidence.
            synthesis: Synthesis results.
            ctx: Research context.

        Returns:
            A ResearchConclusion instance.
        """
        coherence = synthesis["coherence"]
        gaps = synthesis["gaps"]

        # Confidence is based on evidence coherence, adjusted for gaps
        confidence = coherence
        if gaps:
            confidence *= 0.8  # Reduce confidence when gaps exist
        confidence = max(0.1, min(1.0, confidence))

        # Build the answer
        key_findings = synthesis["key_findings"]
        if key_findings:
            answer = (
                f"Based on available evidence, the following was determined "
                f"regarding '{query}': {'; '.join(key_findings[:3])}."
            )
        else:
            answer = (
                f"Insufficient evidence to form a strong conclusion about "
                f"'{query}'. Further research is recommended."
            )

        # Generate recommendations
        recommendations: list[str] = []
        if gaps:
            recommendations.append(
                "Gather additional evidence to address identified gaps"
            )
        if synthesis["contradictions"]:
            recommendations.append(
                "Resolve detected contradictions before acting on conclusions"
            )
        if confidence < 0.5:
            recommendations.append(
                "Treat conclusions as preliminary; seek verification"
            )

        return ResearchConclusion(
            query=query,
            interpretation=interpretation,
            answer=answer,
            confidence=confidence,
            evidence_summary=synthesis["evidence_summary"],
            sub_questions=sub_questions,
            contradictions=synthesis["contradictions"],
            evidence_items=evidence,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Step 7: Uncertainty Declaration
    # ------------------------------------------------------------------

    @staticmethod
    def _declare_uncertainties(
        conclusion: ResearchConclusion,
        evidence: list[EvidenceItem],
        synthesis: dict[str, Any],
    ) -> list[str]:
        """Declare what is unknown, why, and how it could be resolved.

        Args:
            conclusion: The formed conclusion.
            evidence: All evidence items.
            synthesis: Synthesis results.

        Returns:
            List of uncertainty statements.
        """
        uncertainties: list[str] = []

        # Gaps become uncertainties
        for gap in synthesis["gaps"]:
            uncertainties.append(f"Gap: {gap}")

        # Unresolved contradictions
        for contradiction in synthesis["contradictions"]:
            if not contradiction.resolved:
                uncertainties.append(
                    "Unresolved contradiction between evidence items. "
                    "Further investigation needed."
                )

        # Low-confidence evidence
        low_conf = [e for e in evidence if e.credibility < 0.4]
        if low_conf:
            uncertainties.append(
                f"{len(low_conf)} evidence items have low credibility "
                f"(< 0.4). Conclusions dependent on these items may be unreliable."
            )

        # Assumption-based conclusions
        assumptions = [e for e in evidence if e.evidence_class == EvidenceClass.ASSUMPTION]
        if assumptions and conclusion.confidence > 0.5:
            uncertainties.append(
                f"Conclusion relies on {len(assumptions)} unverified assumptions. "
                f"Validate assumptions to increase confidence."
            )

        # Overall confidence statement
        if conclusion.confidence < 0.3:
            uncertainties.append(
                "Overall confidence is very low. This conclusion should be "
                "treated as speculative."
            )
        elif conclusion.confidence < 0.6:
            uncertainties.append(
                "Overall confidence is moderate. Verify key findings before "
                "making decisions based on this research."
            )

        return uncertainties

    # ------------------------------------------------------------------
    # Iterative research
    # ------------------------------------------------------------------

    def refine(
        self,
        previous_conclusion: ResearchConclusion,
        additional_evidence: list[EvidenceItem],
        refined_query: str | None = None,
    ) -> ResearchConclusion:
        """Refine a previous research conclusion with new evidence.

        If confidence was insufficient, this allows gathering additional
        evidence and re-evaluating conclusions.

        Args:
            previous_conclusion: The conclusion to refine.
            additional_evidence: New evidence to incorporate.
            refined_query: Optionally refined query.

        Returns:
            A new ResearchConclusion incorporating the additional evidence.
        """
        query = refined_query or previous_conclusion.query
        all_evidence = list(previous_conclusion.evidence_items) + additional_evidence

        return self.research(
            query=query,
            depth="deep",  # Refinement always uses deep research
            context={"previous_confidence": previous_conclusion.confidence},
            initial_evidence=all_evidence,
        )

    # ------------------------------------------------------------------
    # History and statistics
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> list[ResearchConclusion]:
        """Return recent research history.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of ResearchConclusion instances.
        """
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Return research engine statistics.

        Returns:
            Dict with total_sessions, average_confidence, etc.
        """
        total = len(self._history)
        if total == 0:
            return {
                "total_sessions": 0,
                "average_confidence": 0.0,
                "high_confidence_sessions": 0,
                "low_confidence_sessions": 0,
            }

        confidences = [c.confidence for c in self._history]
        return {
            "total_sessions": total,
            "average_confidence": sum(confidences) / total,
            "high_confidence_sessions": sum(1 for c in confidences if c >= 0.7),
            "low_confidence_sessions": sum(1 for c in confidences if c < 0.4),
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_memory_content(self) -> str:
        """Serialize research history to JSON for memory storage.

        Returns:
            JSON string of research history.
        """
        data = {
            "history": [
                {
                    "query": c.query,
                    "interpretation": c.interpretation,
                    "answer": c.answer,
                    "confidence": c.confidence,
                    "evidence_summary": c.evidence_summary,
                    "uncertainties": c.uncertainties,
                    "recommendations": c.recommendations,
                    "started_at": c.started_at.isoformat(),
                    "completed_at": c.completed_at.isoformat()
                    if c.completed_at
                    else None,
                }
                for c in self._history[-50:]  # Keep last 50 sessions
            ]
        }
        return json.dumps(data, indent=2)

    def to_memory_index_keys(self) -> dict[str, str]:
        """Return index keys for memory storage.

        Returns:
            Dict of key-value pairs for the memory index.
        """
        return {
            "type": "research_engine",
            "session_count": str(len(self._history)),
        }

    @classmethod
    def from_memory_content(cls, content: str) -> ResearchEngine:
        """Restore research engine from JSON.

        Args:
            content: JSON string from to_memory_content().

        Returns:
            A new ResearchEngine with restored history.
        """
        engine = cls()
        data = json.loads(content)
        for entry in data.get("history", []):
            engine._history.append(
                ResearchConclusion(
                    query=entry["query"],
                    interpretation=entry["interpretation"],
                    answer=entry["answer"],
                    confidence=entry["confidence"],
                    evidence_summary=entry.get("evidence_summary", ""),
                    uncertainties=entry.get("uncertainties", []),
                    recommendations=entry.get("recommendations", []),
                )
            )
        logger.info(
            "Research engine restored with %d historical sessions",
            len(engine._history),
        )
        return engine

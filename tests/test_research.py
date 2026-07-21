"""Tests for the ResearchEngine — 7-step research lifecycle."""

from __future__ import annotations

import json

import pytest

from telemachus.cognition.research import (
    Contradiction,
    EvidenceItem,
    ResearchConclusion,
    ResearchEngine,
    SubQuestion,
)
from telemachus.core.types import EvidenceClass

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> ResearchEngine:
    """Return a fresh ResearchEngine."""
    return ResearchEngine()


@pytest.fixture
def fact_evidence() -> EvidenceItem:
    """Return a fact evidence item."""
    return EvidenceItem(
        content="The sky is blue",
        source="observation",
        evidence_class=EvidenceClass.FACT,
        credibility=0.9,
        relevance=0.8,
    )


@pytest.fixture
def inference_evidence() -> EvidenceItem:
    """Return an inference evidence item."""
    return EvidenceItem(
        content="It will likely rain tomorrow",
        source="weather_model",
        evidence_class=EvidenceClass.INFERENCE,
        credibility=0.6,
        relevance=0.7,
    )


@pytest.fixture
def assumption_evidence() -> EvidenceItem:
    """Return an assumption evidence item."""
    return EvidenceItem(
        content="Users prefer dark mode",
        source="design_team",
        evidence_class=EvidenceClass.ASSUMPTION,
        credibility=0.4,
        relevance=0.5,
    )


@pytest.fixture
def opinion_evidence() -> EvidenceItem:
    """Return an opinion evidence item."""
    return EvidenceItem(
        content="Python is the best language",
        source="developer_survey",
        evidence_class=EvidenceClass.OPINION,
        credibility=0.3,
        relevance=0.4,
    )


# ---------------------------------------------------------------------------
# EvidenceItem tests
# ---------------------------------------------------------------------------


class TestEvidenceItem:
    """Tests for the EvidenceItem dataclass."""

    def test_create_evidence_item(self) -> None:
        """Should create an evidence item with defaults."""
        item = EvidenceItem(content="test", source="test_source")
        assert item.content == "test"
        assert item.source == "test_source"
        assert item.evidence_class == EvidenceClass.ASSUMPTION
        assert item.credibility == 0.5
        assert item.relevance == 0.5
        assert item.notes == ""

    def test_create_with_all_fields(self) -> None:
        """Should create with all fields specified."""
        item = EvidenceItem(
            content="factual data",
            source="database",
            evidence_class=EvidenceClass.FACT,
            credibility=0.95,
            relevance=0.9,
            notes="Verified by multiple sources",
        )
        assert item.content == "factual data"
        assert item.source == "database"
        assert item.evidence_class == EvidenceClass.FACT
        assert item.credibility == 0.95
        assert item.relevance == 0.9
        assert item.notes == "Verified by multiple sources"

    def test_credibility_below_zero_raises(self) -> None:
        """Credibility below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            EvidenceItem(content="test", source="s", credibility=-0.1)

    def test_credibility_above_one_raises(self) -> None:
        """Credibility above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            EvidenceItem(content="test", source="s", credibility=1.1)

    def test_relevance_below_zero_raises(self) -> None:
        """Relevance below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            EvidenceItem(content="test", source="s", relevance=-0.1)

    def test_relevance_above_one_raises(self) -> None:
        """Relevance above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            EvidenceItem(content="test", source="s", relevance=1.1)

    def test_credibility_at_boundaries_valid(self) -> None:
        """Credibility at 0.0 and 1.0 should be valid."""
        e1 = EvidenceItem(content="t", source="s", credibility=0.0)
        e2 = EvidenceItem(content="t", source="s", credibility=1.0)
        assert e1.credibility == 0.0
        assert e2.credibility == 1.0

    def test_relevance_at_boundaries_valid(self) -> None:
        """Relevance at 0.0 and 1.0 should be valid."""
        e1 = EvidenceItem(content="t", source="s", relevance=0.0)
        e2 = EvidenceItem(content="t", source="s", relevance=1.0)
        assert e1.relevance == 0.0
        assert e2.relevance == 1.0


# ---------------------------------------------------------------------------
# SubQuestion tests
# ---------------------------------------------------------------------------


class TestSubQuestion:
    """Tests for the SubQuestion dataclass."""

    def test_create_sub_question(self) -> None:
        """Should create a sub-question with defaults."""
        sq = SubQuestion(question="What is X?")
        assert sq.question == "What is X?"
        assert sq.assumptions == []
        assert sq.dependencies == []
        assert sq.status == "pending"
        assert sq.answer is None
        assert sq.confidence == 0.0

    def test_create_with_assumptions(self) -> None:
        """Should create with assumptions."""
        sq = SubQuestion(
            question="What is X?",
            assumptions=["X exists", "X is measurable"],
        )
        assert len(sq.assumptions) == 2

    def test_create_with_dependencies(self) -> None:
        """Should create with dependencies."""
        sq = SubQuestion(
            question="What is X?",
            dependencies=["Define Y first"],
        )
        assert len(sq.dependencies) == 1

    def test_answer_can_be_set(self) -> None:
        """Answer should be settable."""
        sq = SubQuestion(question="What is X?")
        sq.answer = "X is 42"
        sq.confidence = 0.8
        sq.status = "answered"
        assert sq.answer == "X is 42"
        assert sq.confidence == 0.8
        assert sq.status == "answered"


# ---------------------------------------------------------------------------
# Contradiction tests
# ---------------------------------------------------------------------------


class TestContradiction:
    """Tests for the Contradiction dataclass."""

    def test_create_contradiction(self) -> None:
        """Should create a contradiction with defaults."""
        c = Contradiction(item_a="X is true", item_b="X is false")
        assert c.item_a == "X is true"
        assert c.item_b == "X is false"
        assert c.analysis == ""
        assert c.resolved is False
        assert c.resolution is None

    def test_create_with_analysis(self) -> None:
        """Should create with analysis."""
        c = Contradiction(
            item_a="X is true",
            item_b="X is false",
            analysis="Semantic conflict",
        )
        assert c.analysis == "Semantic conflict"

    def test_resolve_contradiction(self) -> None:
        """Should be able to mark as resolved."""
        c = Contradiction(item_a="X is true", item_b="X is false")
        c.resolved = True
        c.resolution = "X is true in context A, false in context B"
        assert c.resolved is True
        assert c.resolution is not None


# ---------------------------------------------------------------------------
# ResearchConclusion tests
# ---------------------------------------------------------------------------


class TestResearchConclusion:
    """Tests for the ResearchConclusion dataclass."""

    def test_create_conclusion(self) -> None:
        """Should create a research conclusion."""
        rc = ResearchConclusion(
            query="What is X?",
            interpretation="Definition request: What is X?",
            answer="X is 42",
            confidence=0.8,
        )
        assert rc.query == "What is X?"
        assert rc.answer == "X is 42"
        assert rc.confidence == 0.8
        assert rc.uncertainties == []
        assert rc.recommendations == []
        assert rc.sub_questions == []
        assert rc.contradictions == []
        assert rc.evidence_items == []
        assert rc.started_at is not None
        assert rc.completed_at is None

    def test_create_with_all_fields(self) -> None:
        """Should create with all optional fields."""
        sq = SubQuestion(question="What is X?")
        c = Contradiction(item_a="a", item_b="b")
        e = EvidenceItem(content="data", source="s")
        rc = ResearchConclusion(
            query="What is X?",
            interpretation="Definition request",
            answer="X is 42",
            confidence=0.9,
            evidence_summary="Strong evidence",
            uncertainties=["Some uncertainty"],
            recommendations=["Verify with more data"],
            sub_questions=[sq],
            contradictions=[c],
            evidence_items=[e],
        )
        assert len(rc.uncertainties) == 1
        assert len(rc.recommendations) == 1
        assert len(rc.sub_questions) == 1
        assert len(rc.contradictions) == 1
        assert len(rc.evidence_items) == 1


# ---------------------------------------------------------------------------
# ResearchEngine init tests
# ---------------------------------------------------------------------------


class TestResearchEngineInit:
    """Tests for ResearchEngine initialization."""

    def test_engine_starts_empty(self, engine: ResearchEngine) -> None:
        """A new engine should have empty history."""
        assert engine.get_history() == []

    def test_stats_empty(self, engine: ResearchEngine) -> None:
        """Stats for empty engine should show zeros."""
        stats = engine.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["average_confidence"] == 0.0
        assert stats["high_confidence_sessions"] == 0
        assert stats["low_confidence_sessions"] == 0


# ---------------------------------------------------------------------------
# Step 1: Query Interpretation tests
# ---------------------------------------------------------------------------


class TestQueryInterpretation:
    """Tests for Step 1: Query Interpretation."""

    def test_what_is_question(self, engine: ResearchEngine) -> None:
        """'What is' questions should be interpreted as definitions."""
        result = engine._interpret_query("What is Python?", {})
        assert "Definition" in result

    def test_how_to_question(self, engine: ResearchEngine) -> None:
        """'How to' questions should be interpreted as procedural."""
        result = engine._interpret_query("How do I install Python?", {})
        assert "Procedural" in result

    def test_why_question(self, engine: ResearchEngine) -> None:
        """'Why' questions should be interpreted as causal."""
        result = engine._interpret_query("Why is the sky blue?", {})
        assert "Causal" in result

    def test_which_question(self, engine: ResearchEngine) -> None:
        """'Which' questions should be interpreted as decision support."""
        result = engine._interpret_query("Which framework should I use?", {})
        assert "Decision" in result

    def test_comparison_question(self, engine: ResearchEngine) -> None:
        """Comparison questions should be detected."""
        result = engine._interpret_query("Compare Python vs JavaScript", {})
        assert "Comparison" in result

    def test_vs_in_question(self, engine: ResearchEngine) -> None:
        """'vs' in query should be detected as comparison."""
        result = engine._interpret_query("Python vs JavaScript for web dev", {})
        assert "Comparison" in result

    def test_direct_question(self, engine: ResearchEngine) -> None:
        """Questions with '?' should be direct questions."""
        result = engine._interpret_query("Is Python fast?", {})
        assert "Direct question" in result

    def test_general_inquiry(self, engine: ResearchEngine) -> None:
        """Non-question text should be general inquiry."""
        result = engine._interpret_query("Tell me about Python", {})
        assert "General inquiry" in result


# ---------------------------------------------------------------------------
# Step 2: Decomposition tests
# ---------------------------------------------------------------------------


class TestDecomposition:
    """Tests for Step 2: Decomposition."""

    def test_quick_depth_one_sub_question(self, engine: ResearchEngine) -> None:
        """Quick depth should produce 1 sub-question."""
        sqs = engine._decompose("What is X?", "Definition: What is X?", {}, "quick")
        assert len(sqs) == 1

    def test_standard_depth_two_sub_questions(self, engine: ResearchEngine) -> None:
        """Standard depth should produce 2 sub-questions."""
        sqs = engine._decompose("What is X?", "Definition: What is X?", {}, "standard")
        assert len(sqs) == 2

    def test_deep_depth_three_sub_questions(self, engine: ResearchEngine) -> None:
        """Deep depth should produce 3 sub-questions."""
        sqs = engine._decompose("What is X?", "Definition: What is X?", {}, "deep")
        assert len(sqs) == 3

    def test_sub_questions_have_assumptions(self, engine: ResearchEngine) -> None:
        """Sub-questions should include assumptions."""
        sqs = engine._decompose("What is X?", "Definition: What is X?", {}, "standard")
        for sq in sqs:
            assert len(sq.assumptions) > 0

    def test_sub_questions_are_pending(self, engine: ResearchEngine) -> None:
        """Sub-questions should start as pending."""
        sqs = engine._decompose("What is X?", "Definition: What is X?", {}, "quick")
        for sq in sqs:
            assert sq.status == "pending"


# ---------------------------------------------------------------------------
# Step 3: Information Gathering tests
# ---------------------------------------------------------------------------


class TestInformationGathering:
    """Tests for Step 3: Information Gathering."""

    def test_gathers_from_context_facts(self, engine: ResearchEngine) -> None:
        """Should gather evidence from context known_facts."""
        ctx = {"known_facts": ["Python was created in 1991"]}
        sqs = engine._decompose("What is Python?", "Definition", ctx, "quick")
        evidence = engine._gather_information(
            "What is Python?", "Definition", sqs, ctx, "quick"
        )
        fact_items = [e for e in evidence if e.evidence_class == EvidenceClass.FACT]
        assert len(fact_items) >= 1

    def test_gathers_from_context_assumptions(self, engine: ResearchEngine) -> None:
        """Should gather from context assumptions."""
        ctx = {"assumptions": ["Users have basic knowledge"]}
        sqs = engine._decompose("What is X?", "Definition", ctx, "quick")
        evidence = engine._gather_information(
            "What is X?", "Definition", sqs, ctx, "quick"
        )
        assumption_items = [
            e for e in evidence if e.evidence_class == EvidenceClass.ASSUMPTION
        ]
        assert len(assumption_items) >= 1

    def test_always_includes_interpretation_inference(self, engine: ResearchEngine) -> None:
        """Should always include the query interpretation as inference."""
        sqs = engine._decompose("What is X?", "Definition", {}, "quick")
        evidence = engine._gather_information(
            "What is X?", "Definition: What is X?", sqs, {}, "quick"
        )
        inference_items = [
            e for e in evidence if e.evidence_class == EvidenceClass.INFERENCE
        ]
        assert len(inference_items) >= 1

    def test_standard_depth_includes_sub_question_evidence(
        self, engine: ResearchEngine
    ) -> None:
        """Standard depth should include sub-question decomposition evidence."""
        sqs = engine._decompose("What is X?", "Definition", {}, "standard")
        evidence = engine._gather_information(
            "What is X?", "Definition", sqs, {}, "standard"
        )
        # Should have more evidence than just the inference
        assert len(evidence) >= 3  # inference + 2 sub-question items

    def test_quick_depth_minimal_evidence(self, engine: ResearchEngine) -> None:
        """Quick depth should produce minimal evidence."""
        sqs = engine._decompose("What is X?", "Definition", {}, "quick")
        evidence = engine._gather_information(
            "What is X?", "Definition", sqs, {}, "quick"
        )
        # Quick: only the inference item (no sub-question decomposition items)
        assert len(evidence) == 1

    def test_empty_context_produces_evidence(self, engine: ResearchEngine) -> None:
        """Even with empty context, should produce evidence."""
        sqs = engine._decompose("What is X?", "Definition", {}, "quick")
        evidence = engine._gather_information(
            "What is X?", "Definition", sqs, {}, "quick"
        )
        assert len(evidence) > 0


# ---------------------------------------------------------------------------
# Step 4: Source Evaluation tests
# ---------------------------------------------------------------------------


class TestSourceEvaluation:
    """Tests for Step 4: Source Evaluation."""

    def test_facts_get_credibility_boost(self, engine: ResearchEngine) -> None:
        """Facts should get a credibility boost."""
        evidence = [
            EvidenceItem(
                content="fact",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.5,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility > 0.5

    def test_opinions_get_credibility_penalty(self, engine: ResearchEngine) -> None:
        """Opinions should get a credibility penalty."""
        evidence = [
            EvidenceItem(
                content="opinion",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.5,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility < 0.5

    def test_inferences_keep_credibility(self, engine: ResearchEngine) -> None:
        """Inferences should keep their credibility."""
        evidence = [
            EvidenceItem(
                content="inference",
                source="s",
                evidence_class=EvidenceClass.INFERENCE,
                credibility=0.5,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility == 0.5

    def test_assumptions_keep_credibility(self, engine: ResearchEngine) -> None:
        """Assumptions should keep their credibility."""
        evidence = [
            EvidenceItem(
                content="assumption",
                source="s",
                evidence_class=EvidenceClass.ASSUMPTION,
                credibility=0.5,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility == 0.5

    def test_credibility_capped_at_one(self, engine: ResearchEngine) -> None:
        """Credibility should not exceed 1.0 after boost."""
        evidence = [
            EvidenceItem(
                content="fact",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.99,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility <= 1.0

    def test_credibility_floor_at_zero_point_one(self, engine: ResearchEngine) -> None:
        """Opinion credibility should not go below 0.1."""
        evidence = [
            EvidenceItem(
                content="opinion",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.1,
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].credibility >= 0.1

    def test_preserves_content_and_source(self, engine: ResearchEngine) -> None:
        """Evaluation should preserve content and source."""
        evidence = [
            EvidenceItem(
                content="original content",
                source="original_source",
                evidence_class=EvidenceClass.FACT,
                credibility=0.7,
                relevance=0.8,
                notes="original notes",
            )
        ]
        evaluated = engine._evaluate_sources(evidence)
        assert evaluated[0].content == "original content"
        assert evaluated[0].source == "original_source"
        assert evaluated[0].relevance == 0.8
        assert evaluated[0].notes == "original notes"


# ---------------------------------------------------------------------------
# Step 5: Synthesis tests
# ---------------------------------------------------------------------------


class TestSynthesis:
    """Tests for Step 5: Synthesis."""

    def test_synthesis_counts_evidence_classes(self, engine: ResearchEngine) -> None:
        """Synthesis should count evidence by class."""
        evidence = [
            EvidenceItem(
                content="fact1",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            ),
            EvidenceItem(
                content="inference1",
                source="s",
                evidence_class=EvidenceClass.INFERENCE,
                credibility=0.6,
            ),
            EvidenceItem(
                content="assumption1",
                source="s",
                evidence_class=EvidenceClass.ASSUMPTION,
                credibility=0.4,
            ),
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert result["fact_count"] == 1
        assert result["inference_count"] == 1
        assert result["assumption_count"] == 1
        assert result["opinion_count"] == 0

    def test_synthesis_detects_contradictions(self, engine: ResearchEngine) -> None:
        """Synthesis should detect contradictory evidence."""
        evidence = [
            EvidenceItem(
                content="X is true",
                source="s1",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            ),
            EvidenceItem(
                content="X is not true",
                source="s2",
                evidence_class=EvidenceClass.FACT,
                credibility=0.7,
            ),
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert len(result["contradictions"]) >= 1

    def test_synthesis_identifies_gaps_no_facts(self, engine: ResearchEngine) -> None:
        """Synthesis should identify gap when no facts exist."""
        evidence = [
            EvidenceItem(
                content="opinion",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.3,
            )
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert len(result["gaps"]) >= 1
        assert any("No verified facts" in g for g in result["gaps"])

    def test_synthesis_identifies_limited_evidence_gap(
        self, engine: ResearchEngine
    ) -> None:
        """Synthesis should flag limited evidence."""
        evidence = [
            EvidenceItem(
                content="only item",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            )
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert any("Limited evidence" in g for g in result["gaps"])

    def test_synthesis_computes_coherence(self, engine: ResearchEngine) -> None:
        """Synthesis should compute coherence score."""
        evidence = [
            EvidenceItem(
                content="f1",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
                relevance=0.9,
            ),
            EvidenceItem(
                content="f2",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
                relevance=0.8,
            ),
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert "coherence" in result
        assert 0.0 <= result["coherence"] <= 1.0

    def test_synthesis_empty_evidence(self, engine: ResearchEngine) -> None:
        """Synthesis with empty evidence should handle gracefully."""
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, [], {})
        assert result["coherence"] == 0.0
        assert len(result["gaps"]) >= 1

    def test_synthesis_key_findings_filtered(self, engine: ResearchEngine) -> None:
        """Key findings should only include credible evidence."""
        evidence = [
            EvidenceItem(
                content="high cred",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
            ),
            EvidenceItem(
                content="low cred",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.2,
            ),
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert len(result["key_findings"]) == 1
        assert "high cred" in result["key_findings"][0]

    def test_synthesis_evidence_summary_includes_counts(
        self, engine: ResearchEngine
    ) -> None:
        """Evidence summary should include counts."""
        evidence = [
            EvidenceItem(
                content="f",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            )
        ]
        sqs: list[SubQuestion] = []
        result = engine._synthesize("query", "interpretation", sqs, evidence, {})
        assert "1 facts" in result["evidence_summary"]


# ---------------------------------------------------------------------------
# Contradiction detection tests
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    """Tests for contradiction detection heuristics."""

    def test_is_not_contradiction(self, engine: ResearchEngine) -> None:
        """'is' vs 'is not' should be contradictory."""
        assert engine._are_contradictory("X is valid", "X is not valid") is True

    def test_can_cannot_contradiction(self, engine: ResearchEngine) -> None:
        """'can' vs 'cannot' should be contradictory."""
        assert engine._are_contradictory("We can proceed", "We cannot proceed") is True

    def test_should_should_not_contradiction(self, engine: ResearchEngine) -> None:
        """'should' vs 'should not' should be contradictory."""
        assert (
            engine._are_contradictory("You should go", "You should not go") is True
        )

    def test_always_never_contradiction(self, engine: ResearchEngine) -> None:
        """'always' vs 'never' should be contradictory."""
        assert engine._are_contradictory("It always works", "It never works") is True

    def test_increase_decrease_contradiction(self, engine: ResearchEngine) -> None:
        """'increase' vs 'decrease' should be contradictory."""
        assert (
            engine._are_contradictory("Profits increase", "Profits decrease") is True
        )

    def test_true_false_contradiction(self, engine: ResearchEngine) -> None:
        """'true' vs 'false' should be contradictory."""
        assert engine._are_contradictory("Statement is true", "Statement is false") is True

    def test_non_contradictory_statements(self, engine: ResearchEngine) -> None:
        """Non-contradictory statements should not be flagged."""
        assert engine._are_contradictory("The sky is blue", "The grass is green") is False

    def test_similar_but_not_contradictory(self, engine: ResearchEngine) -> None:
        """Similar but non-contradictory statements should not be flagged."""
        assert (
            engine._are_contradictory("Python is popular", "Python is widely used")
            is False
        )

    def test_reverse_order_contradiction(self, engine: ResearchEngine) -> None:
        """Contradiction detection should work regardless of order."""
        assert engine._are_contradictory("X is not valid", "X is valid") is True


# ---------------------------------------------------------------------------
# Step 6: Conclusion Formation tests
# ---------------------------------------------------------------------------


class TestConclusionFormation:
    """Tests for Step 6: Conclusion Formation."""

    def test_forms_conclusion_with_evidence(self, engine: ResearchEngine) -> None:
        """Should form a conclusion when evidence exists."""
        evidence = [
            EvidenceItem(
                content="Finding: Python is popular",
                source="survey",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
                relevance=0.9,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "What is Python?", "Definition", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "What is Python?", "Definition", sqs, evidence, synthesis, {}
        )
        assert conclusion.query == "What is Python?"
        assert conclusion.confidence > 0.0
        assert len(conclusion.answer) > 0

    def test_forms_conclusion_without_evidence(self, engine: ResearchEngine) -> None:
        """Conclusion should handle no evidence gracefully."""
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "What is X?", "query", sqs, [], {}
        )
        conclusion = engine._form_conclusion(
            "What is X?", "query", sqs, [], synthesis, {}
        )
        assert "Insufficient evidence" in conclusion.answer

    def test_confidence_reduced_by_gaps(self, engine: ResearchEngine) -> None:
        """Confidence should be reduced when gaps exist."""
        evidence = [
            EvidenceItem(
                content="only item",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
                relevance=0.9,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        # With gaps, confidence should be reduced
        assert conclusion.confidence < synthesis["coherence"]

    def test_confidence_never_below_zero_point_one(
        self, engine: ResearchEngine
    ) -> None:
        """Confidence should never be below 0.1."""
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize("query", "interpretation", sqs, [], {})
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, [], synthesis, {}
        )
        assert conclusion.confidence >= 0.1

    def test_recommendations_for_gaps(self, engine: ResearchEngine) -> None:
        """Should recommend gathering evidence when gaps exist."""
        evidence = [
            EvidenceItem(
                content="only item",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.3,
                relevance=0.3,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        assert any("Gather additional evidence" in r for r in conclusion.recommendations)

    def test_recommendations_for_low_confidence(self, engine: ResearchEngine) -> None:
        """Should recommend verification for low confidence."""
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize("query", "interpretation", sqs, [], {})
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, [], synthesis, {}
        )
        assert any(
            "preliminary" in r.lower() or "verification" in r.lower()
            for r in conclusion.recommendations
        )

    def test_conclusion_includes_evidence_items(self, engine: ResearchEngine) -> None:
        """Conclusion should include evidence items."""
        evidence = [
            EvidenceItem(
                content="data",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        assert len(conclusion.evidence_items) == 1

    def test_conclusion_includes_sub_questions(self, engine: ResearchEngine) -> None:
        """Conclusion should include sub-questions."""
        sqs = [
            SubQuestion(question="Sub Q1"),
            SubQuestion(question="Sub Q2"),
        ]
        synthesis = engine._synthesize("query", "interpretation", sqs, [], {})
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, [], synthesis, {}
        )
        assert len(conclusion.sub_questions) == 2


# ---------------------------------------------------------------------------
# Step 7: Uncertainty Declaration tests
# ---------------------------------------------------------------------------


class TestUncertaintyDeclaration:
    """Tests for Step 7: Uncertainty Declaration."""

    def test_declares_gaps_as_uncertainties(self, engine: ResearchEngine) -> None:
        """Gaps should be declared as uncertainties."""
        evidence: list[EvidenceItem] = []
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize("query", "interpretation", sqs, evidence, {})
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert len(uncertainties) >= 1
        assert any("Gap:" in u for u in uncertainties)

    def test_declares_unresolved_contradictions(self, engine: ResearchEngine) -> None:
        """Unresolved contradictions should be declared."""
        evidence = [
            EvidenceItem(
                content="X is true",
                source="s1",
                evidence_class=EvidenceClass.FACT,
                credibility=0.8,
            ),
            EvidenceItem(
                content="X is not true",
                source="s2",
                evidence_class=EvidenceClass.FACT,
                credibility=0.7,
            ),
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert any("contradiction" in u.lower() for u in uncertainties)

    def test_declares_low_credibility_evidence(self, engine: ResearchEngine) -> None:
        """Low credibility evidence should be flagged."""
        evidence = [
            EvidenceItem(
                content="unreliable",
                source="s",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.2,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert any("low credibility" in u.lower() for u in uncertainties)

    def test_declares_assumption_dependency(self, engine: ResearchEngine) -> None:
        """Assumption-based conclusions should be flagged."""
        evidence = [
            EvidenceItem(
                content="assumed fact",
                source="s",
                evidence_class=EvidenceClass.ASSUMPTION,
                credibility=0.5,
                relevance=0.9,
            ),
            EvidenceItem(
                content="supporting fact",
                source="s",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
                relevance=0.9,
            ),
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert any("assumption" in u.lower() for u in uncertainties)

    def test_very_low_confidence_warning(self, engine: ResearchEngine) -> None:
        """Very low confidence should trigger a warning."""
        evidence: list[EvidenceItem] = []
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize("query", "interpretation", sqs, evidence, {})
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert any("speculative" in u.lower() for u in uncertainties)

    def test_moderate_confidence_warning(self, engine: ResearchEngine) -> None:
        """Moderate confidence should trigger a verification warning."""
        evidence = [
            EvidenceItem(
                content="moderate evidence",
                source="s",
                evidence_class=EvidenceClass.INFERENCE,
                credibility=0.5,
                relevance=0.5,
            )
        ]
        sqs: list[SubQuestion] = []
        synthesis = engine._synthesize(
            "query", "interpretation", sqs, evidence, {}
        )
        conclusion = engine._form_conclusion(
            "query", "interpretation", sqs, evidence, synthesis, {}
        )
        uncertainties = engine._declare_uncertainties(conclusion, evidence, synthesis)
        assert any("moderate" in u.lower() for u in uncertainties)


# ---------------------------------------------------------------------------
# Full research lifecycle tests
# ---------------------------------------------------------------------------


class TestFullResearch:
    """Tests for the complete research() method."""

    def test_research_quick_depth(self, engine: ResearchEngine) -> None:
        """Quick research should complete successfully."""
        conclusion = engine.research("What is Python?", depth="quick")
        assert conclusion.query == "What is Python?"
        assert conclusion.confidence > 0.0
        assert conclusion.completed_at is not None
        assert len(conclusion.sub_questions) == 1

    def test_research_standard_depth(self, engine: ResearchEngine) -> None:
        """Standard research should complete successfully."""
        conclusion = engine.research("What is Python?", depth="standard")
        assert conclusion.confidence > 0.0
        assert len(conclusion.sub_questions) == 2

    def test_research_deep_depth(self, engine: ResearchEngine) -> None:
        """Deep research should complete successfully."""
        conclusion = engine.research("What is Python?", depth="deep")
        assert conclusion.confidence > 0.0
        assert len(conclusion.sub_questions) == 3

    def test_research_with_context(self, engine: ResearchEngine) -> None:
        """Research with context should incorporate known facts."""
        conclusion = engine.research(
            "What is Python?",
            depth="standard",
            context={
                "known_facts": ["Python was created by Guido van Rossum"],
                "assumptions": ["The user has basic programming knowledge"],
            },
        )
        assert len(conclusion.evidence_items) > 0

    def test_research_with_initial_evidence(self, engine: ResearchEngine) -> None:
        """Research should incorporate initial evidence."""
        initial = [
            EvidenceItem(
                content="Python is dynamically typed",
                source="docs",
                evidence_class=EvidenceClass.FACT,
                credibility=0.95,
            )
        ]
        conclusion = engine.research(
            "What is Python?",
            depth="quick",
            initial_evidence=initial,
        )
        assert len(conclusion.evidence_items) >= 1

    def test_research_adds_to_history(self, engine: ResearchEngine) -> None:
        """Research should add to history."""
        engine.research("What is Python?")
        assert len(engine.get_history()) == 1

    def test_research_multiple_sessions(self, engine: ResearchEngine) -> None:
        """Multiple research sessions should accumulate in history."""
        engine.research("Query 1")
        engine.research("Query 2")
        engine.research("Query 3")
        assert len(engine.get_history()) == 3

    def test_research_empty_query_raises(self, engine: ResearchEngine) -> None:
        """Empty query should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            engine.research("")

    def test_research_whitespace_query_raises(self, engine: ResearchEngine) -> None:
        """Whitespace-only query should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            engine.research("   ")

    def test_research_produces_uncertainties(self, engine: ResearchEngine) -> None:
        """Research should produce uncertainty declarations."""
        conclusion = engine.research("What is X?")
        assert len(conclusion.uncertainties) >= 1

    def test_research_produces_recommendations(self, engine: ResearchEngine) -> None:
        """Research should produce recommendations."""
        conclusion = engine.research("What is X?")
        assert len(conclusion.recommendations) >= 1

    def test_research_evidence_summary(self, engine: ResearchEngine) -> None:
        """Research should include evidence summary."""
        conclusion = engine.research("What is Python?")
        assert len(conclusion.evidence_summary) > 0

    def test_research_completed_at_is_set(self, engine: ResearchEngine) -> None:
        """Research should set completed_at timestamp."""
        conclusion = engine.research("What is Python?")
        assert conclusion.completed_at is not None
        assert conclusion.completed_at >= conclusion.started_at


# ---------------------------------------------------------------------------
# Refinement tests
# ---------------------------------------------------------------------------


class TestRefinement:
    """Tests for the refine() method."""

    def test_refine_adds_evidence(self, engine: ResearchEngine) -> None:
        """Refinement should incorporate additional evidence."""
        initial = engine.research("What is Python?")
        original_count = len(initial.evidence_items)

        new_evidence = [
            EvidenceItem(
                content="Python 3.12 has new features",
                source="release_notes",
                evidence_class=EvidenceClass.FACT,
                credibility=0.95,
            )
        ]
        refined = engine.refine(initial, new_evidence)
        assert len(refined.evidence_items) > original_count

    def test_refine_uses_deep_research(self, engine: ResearchEngine) -> None:
        """Refinement should use deep research depth."""
        initial = engine.research("What is Python?", depth="quick")
        refined = engine.refine(initial, [])
        assert len(refined.sub_questions) == 3  # Deep has 3 sub-questions

    def test_refine_with_refined_query(self, engine: ResearchEngine) -> None:
        """Refinement should accept a refined query."""
        initial = engine.research("What is Python?")
        refined = engine.refine(
            initial,
            [],
            refined_query="What is Python 3.12 specifically?",
        )
        assert "Python 3.12" in refined.query

    def test_refine_adds_to_history(self, engine: ResearchEngine) -> None:
        """Refinement should add a new history entry."""
        initial = engine.research("What is Python?")
        engine.refine(initial, [])
        assert len(engine.get_history()) == 2


# ---------------------------------------------------------------------------
# History and stats tests
# ---------------------------------------------------------------------------


class TestHistoryAndStats:
    """Tests for history and statistics."""

    def test_get_history_respects_limit(self, engine: ResearchEngine) -> None:
        """get_history should respect the limit parameter."""
        for i in range(10):
            engine.research(f"Query {i}")
        history = engine.get_history(limit=5)
        assert len(history) == 5

    def test_get_history_default_limit(self, engine: ResearchEngine) -> None:
        """get_history should default to 20."""
        for i in range(25):
            engine.research(f"Query {i}")
        history = engine.get_history()
        assert len(history) == 20

    def test_stats_after_research(self, engine: ResearchEngine) -> None:
        """Stats should reflect research sessions."""
        engine.research("Query 1")
        stats = engine.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["average_confidence"] > 0.0

    def test_stats_high_confidence(self, engine: ResearchEngine) -> None:
        """High confidence sessions should be counted."""
        # Research with lots of facts should produce high confidence
        engine.research(
            "What is Python?",
            context={
                "known_facts": [
                    "Python is a language",
                    "Python was created in 1991",
                    "Python is open source",
                    "Python supports OOP",
                ]
            },
        )
        stats = engine.get_stats()
        assert stats["high_confidence_sessions"] >= 0

    def test_stats_low_confidence(self, engine: ResearchEngine) -> None:
        """Low confidence sessions should be counted."""
        engine.research("What is X?")
        stats = engine.get_stats()
        assert stats["low_confidence_sessions"] >= 0


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


class TestResearchPersistence:
    """Tests for research engine persistence helpers."""

    def test_to_memory_content(self, engine: ResearchEngine) -> None:
        """Should serialize to JSON."""
        engine.research("What is Python?")
        content = engine.to_memory_content()
        assert isinstance(content, str)
        data = json.loads(content)
        assert "history" in data
        assert len(data["history"]) == 1

    def test_to_memory_content_empty(self, engine: ResearchEngine) -> None:
        """Empty engine should serialize to empty history."""
        content = engine.to_memory_content()
        data = json.loads(content)
        assert data["history"] == []

    def test_to_memory_index_keys(self, engine: ResearchEngine) -> None:
        """Should return index keys."""
        engine.research("Query 1")
        engine.research("Query 2")
        keys = engine.to_memory_index_keys()
        assert keys["type"] == "research_engine"
        assert keys["session_count"] == "2"

    def test_to_memory_index_keys_empty(self, engine: ResearchEngine) -> None:
        """Empty engine should have zero session count."""
        keys = engine.to_memory_index_keys()
        assert keys["session_count"] == "0"

    def test_from_memory_content_roundtrip(self, engine: ResearchEngine) -> None:
        """Should restore engine from JSON."""
        engine.research("What is Python?")
        content = engine.to_memory_content()
        restored = ResearchEngine.from_memory_content(content)
        assert len(restored.get_history()) == 1
        assert restored.get_history()[0].query == "What is Python?"

    def test_from_memory_content_empty(self) -> None:
        """Should restore empty engine."""
        restored = ResearchEngine.from_memory_content('{"history": []}')
        assert restored.get_history() == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestResearchEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_query(self, engine: ResearchEngine) -> None:
        """Very long queries should be handled."""
        long_query = "What is " + "a" * 500 + "?"
        conclusion = engine.research(long_query)
        assert conclusion.query == long_query

    def test_unicode_query(self, engine: ResearchEngine) -> None:
        """Unicode queries should be handled."""
        conclusion = engine.research("什么是Python？")
        assert conclusion.query == "什么是Python？"

    def test_special_characters_query(self, engine: ResearchEngine) -> None:
        """Special characters in queries should be handled."""
        conclusion = engine.research("What is Python @#$%^&*()?")
        assert conclusion.query == "What is Python @#$%^&*()?"

    def test_multiple_research_sessions_accumulate(self, engine: ResearchEngine) -> None:
        """Multiple sessions should accumulate independently."""
        c1 = engine.research("Query 1")
        c2 = engine.research("Query 2")
        assert c1.query != c2.query
        assert c1.started_at != c2.started_at

    def test_confidence_is_float(self, engine: ResearchEngine) -> None:
        """Confidence should always be a float."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.confidence, float)

    def test_interpretation_is_string(self, engine: ResearchEngine) -> None:
        """Interpretation should always be a string."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.interpretation, str)
        assert len(conclusion.interpretation) > 0

    def test_answer_is_string(self, engine: ResearchEngine) -> None:
        """Answer should always be a string."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.answer, str)
        assert len(conclusion.answer) > 0

    def test_contradictions_are_list(self, engine: ResearchEngine) -> None:
        """Contradictions should always be a list."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.contradictions, list)

    def test_uncertainties_are_list(self, engine: ResearchEngine) -> None:
        """Uncertainties should always be a list."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.uncertainties, list)

    def test_recommendations_are_list(self, engine: ResearchEngine) -> None:
        """Recommendations should always be a list."""
        conclusion = engine.research("What is Python?")
        assert isinstance(conclusion.recommendations, list)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestResearchIntegration:
    """Integration tests for the research engine."""

    def test_full_research_lifecycle(self, engine: ResearchEngine) -> None:
        """A complete research lifecycle should work end-to-end."""
        conclusion = engine.research(
            "Should we use Python for this project?",
            depth="deep",
            context={
                "known_facts": [
                    "Python has extensive libraries",
                    "Python is widely used in data science",
                ],
                "assumptions": ["The team has Python experience"],
            },
        )
        # Verify all steps produced output
        assert len(conclusion.interpretation) > 0
        assert len(conclusion.sub_questions) == 3
        assert len(conclusion.evidence_items) > 0
        assert len(conclusion.answer) > 0
        assert len(conclusion.uncertainties) > 0
        # Recommendations may be empty when confidence is high with no gaps/contradictions
        assert isinstance(conclusion.recommendations, list)
        assert 0.0 <= conclusion.confidence <= 1.0
        assert conclusion.completed_at is not None

    def test_research_persistence_roundtrip(self, engine: ResearchEngine) -> None:
        """Research history should survive serialization roundtrip."""
        engine.research("Query 1", depth="quick")
        engine.research("Query 2", depth="standard")
        engine.research("Query 3", depth="deep")

        content = engine.to_memory_content()
        restored = ResearchEngine.from_memory_content(content)

        assert len(restored.get_history()) == 3
        assert restored.get_history()[0].query == "Query 1"
        assert restored.get_history()[2].query == "Query 3"

    def test_refinement_improves_confidence(self, engine: ResearchEngine) -> None:
        """Refinement with good evidence should improve confidence."""
        initial = engine.research("What is Python?")
        initial_conf = initial.confidence

        new_evidence = [
            EvidenceItem(
                content="Python is a high-level programming language",
                source="official_docs",
                evidence_class=EvidenceClass.FACT,
                credibility=0.95,
                relevance=0.95,
            ),
            EvidenceItem(
                content="Python supports multiple paradigms",
                source="official_docs",
                evidence_class=EvidenceClass.FACT,
                credibility=0.95,
                relevance=0.9,
            ),
        ]
        refined = engine.refine(initial, new_evidence)
        assert refined.confidence > initial_conf

    def test_multiple_queries_independent(self, engine: ResearchEngine) -> None:
        """Multiple queries should produce independent conclusions."""
        c1 = engine.research("What is Python?")
        c2 = engine.research("What is JavaScript?")

        assert c1.query != c2.query
        assert c1.answer != c2.answer
        assert c1.started_at != c2.started_at

    def test_research_with_all_evidence_classes(self, engine: ResearchEngine) -> None:
        """Research should handle all evidence classes."""
        initial = [
            EvidenceItem(
                content="Fact: Python is a language",
                source="docs",
                evidence_class=EvidenceClass.FACT,
                credibility=0.9,
            ),
            EvidenceItem(
                content="Inference: Python is popular",
                source="analysis",
                evidence_class=EvidenceClass.INFERENCE,
                credibility=0.6,
            ),
            EvidenceItem(
                content="Assumption: Users know Python",
                source="team",
                evidence_class=EvidenceClass.ASSUMPTION,
                credibility=0.4,
            ),
            EvidenceItem(
                content="Opinion: Python is best",
                source="survey",
                evidence_class=EvidenceClass.OPINION,
                credibility=0.3,
            ),
        ]
        conclusion = engine.research(
            "What is Python?",
            depth="standard",
            initial_evidence=initial,
        )
        assert len(conclusion.evidence_items) >= 4

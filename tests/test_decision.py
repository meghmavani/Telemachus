"""Tests for the DecisionFramework — multi-criteria option ranking."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from telemachus.governance.decision import (
    DecisionFramework,
    _DecisionResult,
    _OptionScore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def framework() -> DecisionFramework:
    """Provide a fresh DecisionFramework for each test."""
    return DecisionFramework()


@pytest.fixture
def sample_options() -> list[str]:
    """Provide a set of sample options for testing."""
    return [
        "Option A: refactor module for better performance",
        "Option B: add comprehensive tests to improve reliability",
        "Option C: document all public APIs for clarity",
    ]


# ---------------------------------------------------------------------------
# Option Score Tests
# ---------------------------------------------------------------------------


class TestOptionScore:
    """Tests for _OptionScore dataclass."""

    def test_option_score_is_frozen(self) -> None:
        """_OptionScore should be immutable."""
        score = _OptionScore(
            option="test",
            purpose_fit=0.5,
            tradeoff_clarity=0.5,
            outcome_quality=0.5,
            context_fit=0.5,
        )
        with pytest.raises(FrozenInstanceError):
            score.purpose_fit = 0.8  # type: ignore[misc]

    def test_composite_is_weighted_average(
        self, framework: DecisionFramework
    ) -> None:
        """Composite score should be a weighted average of dimensions."""
        result = framework.evaluate(
            options=["test option with clear goals and high impact"],
            context={"goal": "test option"},
        )
        score = result.ranked_options[0]
        expected = (
            score.purpose_fit * 0.30
            + score.tradeoff_clarity * 0.20
            + score.outcome_quality * 0.25
            + score.context_fit * 0.25
        )
        assert abs(score.composite - expected) < 0.001

    def test_all_dimensions_in_range(
        self, framework: DecisionFramework
    ) -> None:
        """All dimension scores should be between 0.0 and 1.0."""
        result = framework.evaluate(options=["test option"])
        score = result.ranked_options[0]
        assert 0.0 <= score.purpose_fit <= 1.0
        assert 0.0 <= score.tradeoff_clarity <= 1.0
        assert 0.0 <= score.outcome_quality <= 1.0
        assert 0.0 <= score.context_fit <= 1.0
        assert 0.0 <= score.composite <= 1.0


# ---------------------------------------------------------------------------
# Evaluation Tests
# ---------------------------------------------------------------------------


class TestEvaluation:
    """Tests for the main evaluate method."""

    def test_evaluate_returns_decision_result(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """evaluate should return a _DecisionResult."""
        result = framework.evaluate(options=sample_options)
        assert isinstance(result, _DecisionResult)

    def test_empty_options_raises(self, framework: DecisionFramework) -> None:
        """Empty options list should raise ValueError."""
        with pytest.raises(ValueError, match="At least one option"):
            framework.evaluate(options=[])

    def test_single_option_is_best(
        self, framework: DecisionFramework
    ) -> None:
        """With one option, it should be selected as best."""
        result = framework.evaluate(options=["only option"])
        assert result.best_option == "only option"
        assert len(result.ranked_options) == 1

    def test_options_ranked_by_composite(
        self, framework: DecisionFramework
    ) -> None:
        """Options should be ranked by composite score descending."""
        result = framework.evaluate(
            options=[
                "mediocre option",
                "excellent option with clear goals, high impact, proven, appropriate timing",
            ]
        )
        scores = [s.composite for s in result.ranked_options]
        assert scores == sorted(scores, reverse=True)

    def test_best_option_has_highest_score(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """The best option should have the highest composite score."""
        result = framework.evaluate(options=sample_options)
        max_score = max(s.composite for s in result.ranked_options)
        assert result.best_score == max_score
        assert result.ranked_options[0].composite == max_score

    def test_result_includes_reasoning(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """Decision result should include reasoning."""
        result = framework.evaluate(options=sample_options)
        assert len(result.reasoning) > 0
        assert "Best option" in result.reasoning

    def test_result_includes_uncertainty_level(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """Decision result should include uncertainty level."""
        result = framework.evaluate(options=sample_options)
        assert result.uncertainty_level in ("low", "moderate", "high")


# ---------------------------------------------------------------------------
# Purpose Fit Tests
# ---------------------------------------------------------------------------


class TestPurposeFit:
    """Tests for purpose fit dimension evaluation."""

    def test_goal_aligned_scores_higher(
        self, framework: DecisionFramework
    ) -> None:
        """Options aligned with goals should score higher."""
        result = framework.evaluate(
            options=[
                "align with project goals and vision",
                "unrelated tangential distraction",
            ],
            context={"goal": "project goals"},
        )
        aligned = result.ranked_options[0]
        assert aligned.purpose_fit > 0.5

    def test_misalignment_flag_reduces_score(
        self, framework: DecisionFramework
    ) -> None:
        """Misalignment context flag should reduce purpose fit."""
        result = framework.evaluate(
            options=["some option"],
            context={"misaligned_with_goals": True},
        )
        assert result.ranked_options[0].purpose_fit < 0.5

    def test_explicit_goal_match_boosts_score(
        self, framework: DecisionFramework
    ) -> None:
        """Explicit goal match should boost purpose fit."""
        result = framework.evaluate(
            options=["improve code quality"],
            context={"goal": "improve code quality"},
        )
        assert result.ranked_options[0].purpose_fit >= 0.7


# ---------------------------------------------------------------------------
# Tradeoff Clarity Tests
# ---------------------------------------------------------------------------


class TestTradeoffClarity:
    """Tests for tradeoff clarity dimension evaluation."""

    def test_explicit_tradeoffs_score_higher(
        self, framework: DecisionFramework
    ) -> None:
        """Options discussing tradeoffs explicitly should score higher."""
        result = framework.evaluate(
            options=[
                "option with clear benefit and cost tradeoff analysis",
                "vague option with unclear costs",
            ]
        )
        clear = result.ranked_options[0]
        assert clear.tradeoff_clarity > 0.5

    def test_tradeoffs_analyzed_flag_boosts_score(
        self, framework: DecisionFramework
    ) -> None:
        """Tradeoffs analyzed context flag should boost score."""
        result = framework.evaluate(
            options=["some option"],
            context={"tradeoffs_analyzed": True},
        )
        assert result.ranked_options[0].tradeoff_clarity >= 0.7

    def test_high_uncertainty_reduces_score(
        self, framework: DecisionFramework
    ) -> None:
        """High tradeoff uncertainty should reduce score."""
        result = framework.evaluate(
            options=["some option"],
            context={"tradeoff_uncertainty": "high"},
        )
        assert result.ranked_options[0].tradeoff_clarity < 0.5


# ---------------------------------------------------------------------------
# Outcome Quality Tests
# ---------------------------------------------------------------------------


class TestOutcomeQuality:
    """Tests for outcome quality dimension evaluation."""

    def test_high_impact_scores_higher(
        self, framework: DecisionFramework
    ) -> None:
        """Options with high impact indicators should score higher."""
        result = framework.evaluate(
            options=[
                "effective robust scalable solution with high impact",
                "fragile temporary hack with minimal effect",
            ]
        )
        good = result.ranked_options[0]
        assert good.outcome_quality > 0.5

    def test_expected_impact_context_affects_score(
        self, framework: DecisionFramework
    ) -> None:
        """Expected impact context should affect outcome quality."""
        high_result = framework.evaluate(
            options=["some option"],
            context={"expected_impact": "high"},
        )
        low_result = framework.evaluate(
            options=["some option"],
            context={"expected_impact": "low"},
        )
        assert (
            high_result.ranked_options[0].outcome_quality
            > low_result.ranked_options[0].outcome_quality
        )

    def test_sustainability_concern_reduces_score(
        self, framework: DecisionFramework
    ) -> None:
        """Sustainability concern should reduce outcome quality."""
        result = framework.evaluate(
            options=["some option"],
            context={"sustainability_concern": True},
        )
        assert result.ranked_options[0].outcome_quality < 0.5


# ---------------------------------------------------------------------------
# Context Fit Tests
# ---------------------------------------------------------------------------


class TestContextFit:
    """Tests for context fit dimension evaluation."""

    def test_appropriate_timing_scores_higher(
        self, framework: DecisionFramework
    ) -> None:
        """Options with appropriate timing should score higher."""
        result = framework.evaluate(
            options=[
                "timely appropriate solution that fits within constraints",
                "inappropriate premature solution that violates constraints",
            ]
        )
        good = result.ranked_options[0]
        assert good.context_fit > 0.5

    def test_optimal_timing_boosts_score(
        self, framework: DecisionFramework
    ) -> None:
        """Optimal timing context should boost context fit."""
        result = framework.evaluate(
            options=["some option"],
            context={"timing": "optimal"},
        )
        assert result.ranked_options[0].context_fit >= 0.7

    def test_poor_timing_reduces_score(
        self, framework: DecisionFramework
    ) -> None:
        """Poor timing context should reduce context fit."""
        result = framework.evaluate(
            options=["some option"],
            context={"timing": "poor"},
        )
        assert result.ranked_options[0].context_fit < 0.5

    def test_priority_alignment_affects_score(
        self, framework: DecisionFramework
    ) -> None:
        """Priority alignment context should affect context fit."""
        aligned_result = framework.evaluate(
            options=["some option"],
            context={"aligns_with_priorities": True},
        )
        misaligned_result = framework.evaluate(
            options=["some option"],
            context={"aligns_with_priorities": False},
        )
        assert (
            aligned_result.ranked_options[0].context_fit
            > misaligned_result.ranked_options[0].context_fit
        )


# ---------------------------------------------------------------------------
# Discussion and Uncertainty Tests
# ---------------------------------------------------------------------------


class TestDiscussionAndUncertainty:
    """Tests for discussion recommendation and uncertainty assessment."""

    def test_close_scores_trigger_discussion(
        self, framework: DecisionFramework
    ) -> None:
        """Close scores between top options should trigger discussion."""
        # Two very similar options
        result = framework.evaluate(
            options=[
                "option one with good alignment",
                "option two with good alignment",
            ]
        )
        if len(result.ranked_options) >= 2:
            diff = abs(
                result.ranked_options[0].composite
                - result.ranked_options[1].composite
            )
            if diff < 0.1:
                assert result.requires_discussion is True

    def test_clear_winner_no_discussion(
        self, framework: DecisionFramework
    ) -> None:
        """Clear winner should not require discussion."""
        result = framework.evaluate(
            options=[
                "excellent option with clear goals, high impact, proven, appropriate timing",
                "mediocre option",
            ]
        )
        # The excellent option should be clearly better
        if len(result.ranked_options) >= 2:
            diff = abs(
                result.ranked_options[0].composite
                - result.ranked_options[1].composite
            )
            if diff > 0.2:
                assert result.requires_discussion is False

    def test_request_discussion_flag(self, framework: DecisionFramework) -> None:
        """Request discussion context flag should trigger discussion."""
        result = framework.evaluate(
            options=["clearly best option with excellent alignment and high impact"],
            context={"request_discussion": True},
        )
        assert result.requires_discussion is True

    def test_single_option_low_uncertainty(
        self, framework: DecisionFramework
    ) -> None:
        """Single option should have low uncertainty."""
        result = framework.evaluate(options=["only option"])
        assert result.uncertainty_level == "low"

    def test_multiple_strong_options_moderate_uncertainty(
        self, framework: DecisionFramework
    ) -> None:
        """Multiple strong options should have at least moderate uncertainty."""
        result = framework.evaluate(
            options=[
                "excellent option A with clear goals and high impact",
                "excellent option B with clear goals and high impact",
            ]
        )
        assert result.uncertainty_level in ("moderate", "high")


# ---------------------------------------------------------------------------
# Rank Options Tests
# ---------------------------------------------------------------------------


class TestRankOptions:
    """Tests for the rank_options method."""

    def test_rank_options_returns_sorted_list(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """rank_options should return options sorted by composite descending."""
        ranked = framework.rank_options(options=sample_options)
        scores = [s.composite for s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_options_empty_returns_empty(
        self, framework: DecisionFramework
    ) -> None:
        """Empty options should return empty list."""
        ranked = framework.rank_options(options=[])
        assert ranked == []

    def test_rank_options_preserves_all_options(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """All input options should appear in ranked output."""
        ranked = framework.rank_options(options=sample_options)
        assert len(ranked) == len(sample_options)


# ---------------------------------------------------------------------------
# Compare Two Tests
# ---------------------------------------------------------------------------


class TestCompareTwo:
    """Tests for the compare_two method."""

    def test_compare_two_returns_comparison_dict(
        self, framework: DecisionFramework
    ) -> None:
        """compare_two should return a dict with both scores and tradeoffs."""
        result = framework.compare_two(
            option_a="excellent option with clear goals and high impact",
            option_b="mediocre option",
        )
        assert "option_a" in result
        assert "option_b" in result
        assert "winner" in result
        assert "tradeoffs" in result
        assert "discussion_recommended" in result

    def test_clear_winner_detected(
        self, framework: DecisionFramework
    ) -> None:
        """Clear winner should be identified correctly."""
        result = framework.compare_two(
            option_a="excellent option with clear goals, high impact, proven and tested",
            option_b="mediocre option",
        )
        assert result["winner"] == "A"

    def test_close_options_recommend_discussion(
        self, framework: DecisionFramework
    ) -> None:
        """Close options should recommend discussion."""
        result = framework.compare_two(
            option_a="option one with good alignment",
            option_b="option two with good alignment",
        )
        # Similar options should have close scores
        assert result["discussion_recommended"] is True

    def test_tradeoffs_listed(self, framework: DecisionFramework) -> None:
        """Tradeoffs between options should be listed."""
        result = framework.compare_two(
            option_a="excellent option with clear goals, high impact, proven, appropriate timing",
            option_b="mediocre fragile temporary hack",
        )
        assert len(result["tradeoffs"]) > 0


# ---------------------------------------------------------------------------
# Custom Weights Tests
# ---------------------------------------------------------------------------


class TestCustomWeights:
    """Tests for custom dimension weights."""

    def test_custom_weights_accepted(self) -> None:
        """Custom weights should be accepted if they sum to 1.0."""
        fw = DecisionFramework(
            weights={
                "purpose_fit": 0.40,
                "tradeoff_clarity": 0.10,
                "outcome_quality": 0.25,
                "context_fit": 0.25,
            }
        )
        assert fw is not None

    def test_invalid_weights_raise(self) -> None:
        """Weights not summing to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            DecisionFramework(
                weights={
                    "purpose_fit": 0.5,
                    "tradeoff_clarity": 0.5,
                    "outcome_quality": 0.5,
                    "context_fit": 0.5,
                }
            )

    def test_custom_weights_affect_composite(self) -> None:
        """Custom weights should change composite scores."""
        default_fw = DecisionFramework()
        custom_fw = DecisionFramework(
            weights={
                "purpose_fit": 0.70,
                "tradeoff_clarity": 0.10,
                "outcome_quality": 0.10,
                "context_fit": 0.10,
            }
        )

        option = "align with goals and vision"
        default_result = default_fw.evaluate(options=[option])
        custom_result = custom_fw.evaluate(options=[option])

        # With purpose_fit weighted higher, composite should differ
        assert (
            default_result.ranked_options[0].composite
            != custom_result.ranked_options[0].composite
        )


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_none_context(self, framework: DecisionFramework) -> None:
        """None context should be treated as empty dict."""
        result = framework.evaluate(
            options=["test option"],
            context=None,
        )
        assert isinstance(result, _DecisionResult)

    def test_very_long_option(self, framework: DecisionFramework) -> None:
        """Very long option descriptions should be handled."""
        long_option = "excellent option with clear goals " * 50
        result = framework.evaluate(options=[long_option])
        assert isinstance(result, _DecisionResult)

    def test_many_options(self, framework: DecisionFramework) -> None:
        """Many options should be handled."""
        many_options = [f"option {i}" for i in range(20)]
        result = framework.evaluate(options=many_options)
        assert len(result.ranked_options) == 20

    def test_decision_result_is_frozen(self) -> None:
        """_DecisionResult should be immutable."""
        result = _DecisionResult(
            ranked_options=[],
            best_option="test",
            best_score=0.5,
            requires_discussion=False,
            uncertainty_level="low",
            reasoning="test",
        )
        with pytest.raises(FrozenInstanceError):
            result.best_option = "changed"  # type: ignore[misc]

    def test_all_dimensions_scored_for_each_option(
        self, framework: DecisionFramework, sample_options: list[str]
    ) -> None:
        """Every option should have all four dimensions scored."""
        result = framework.evaluate(options=sample_options)
        for score in result.ranked_options:
            assert score.purpose_fit >= 0.0
            assert score.tradeoff_clarity >= 0.0
            assert score.outcome_quality >= 0.0
            assert score.context_fit >= 0.0

    def test_option_score_includes_reasoning(
        self, framework: DecisionFramework
    ) -> None:
        """Each option score should include per-dimension reasoning."""
        result = framework.evaluate(options=["test option"])
        score = result.ranked_options[0]
        assert len(score.reasoning) > 0
        assert "Purpose fit" in score.reasoning
        assert "Tradeoff clarity" in score.reasoning
        assert "Outcome quality" in score.reasoning
        assert "Context fit" in score.reasoning

    def test_goal_included_in_reasoning(
        self, framework: DecisionFramework
    ) -> None:
        """When goal is provided, it should appear in reasoning."""
        result = framework.evaluate(
            options=["test option"],
            context={"goal": "improve performance"},
        )
        assert "improve performance" in result.reasoning

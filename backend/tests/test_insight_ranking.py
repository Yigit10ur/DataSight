import numpy as np
import pandas as pd
import pytest

from app.analysis import analyze_dataset
from app.insights import build_insights, generate_insights, rank_insights
from app.insights.insight_ranker import (
    HALF_RELIABILITY_ROWS,
    MAX_INSIGHTS,
    MAX_PER_TYPE,
    TYPE_WEIGHTS,
    reliability,
)
from app.insights.models import Insight
from app.profiling import profile_dataset
from app.quality import check_dataset_quality
from app.visualization import build_charts


def insight(
    insight_id: str,
    insight_type: str = "correlation",
    columns: list[str] | None = None,
    strength: float = 1.0,
    confidence: float = 1.0,
    sample_size: int = 1000,
) -> Insight:
    return Insight(
        id=insight_id,
        insight_type=insight_type,
        columns=columns if columns is not None else ["a", "b"],
        message="m",
        metrics={},
        strength=strength,
        confidence=confidence,
        sample_size=sample_size,
        caveats=[],
        chart_id=None,
    )


def ranked_for(frame: pd.DataFrame):
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    return build_insights(profile, analysis, quality, charts.charts).insights


def test_a_larger_effect_outranks_a_smaller_one():
    weak = insight("weak", strength=0.3)
    strong = insight("strong", strength=0.9, columns=["c", "d"])

    assert [found.id for found in rank_insights([weak, strong])] == ["strong", "weak"]


def test_the_same_effect_on_more_rows_outranks_it_on_fewer():
    small = insight("small", sample_size=20)
    large = insight("large", sample_size=5000, columns=["c", "d"])
    ranked = rank_insights([small, large])

    assert [found.id for found in ranked] == ["large", "small"]
    assert ranked[0].importance > ranked[1].importance


def test_reliability_grows_with_the_sample_and_never_reaches_one():
    assert reliability(0) == 0
    assert reliability(HALF_RELIABILITY_ROWS) == pytest.approx(0.5)
    assert reliability(10) < reliability(100) < reliability(10000) < 1


def test_an_undermined_finding_drops_below_an_equal_one():
    doubted = insight("doubted", confidence=0.6)
    plain = insight("plain", columns=["c", "d"])
    ranked = rank_insights([doubted, plain])

    assert [found.id for found in ranked] == ["plain", "doubted"]
    assert ranked[1].importance == pytest.approx(ranked[0].importance * 0.6)


def test_the_kind_of_finding_breaks_a_tie():
    trivia = insight("trivia", insight_type="rare_categories", columns=["c"])
    difference = insight("difference", insight_type="group_difference", columns=["d", "e"])

    assert [found.id for found in rank_insights([trivia, difference])] == [
        "difference",
        "trivia",
    ]


def test_importance_is_the_product_of_its_four_parts():
    found = rank_insights([insight("x", strength=0.8, confidence=0.5, sample_size=50)])[0]

    assert found.importance == pytest.approx(0.8 * 0.5 * 0.5 * TYPE_WEIGHTS["correlation"])


def test_ranking_does_not_depend_on_the_order_it_was_given():
    findings = [
        insight("a", strength=0.4, columns=["a", "b"]),
        insight("b", strength=0.9, columns=["c", "d"]),
        insight("c", strength=0.6, columns=["e", "f"]),
    ]
    forwards = [found.id for found in rank_insights(list(findings))]
    backwards = [found.id for found in rank_insights(list(reversed(findings)))]

    assert forwards == backwards == ["b", "c", "a"]


def test_equal_findings_keep_a_stable_order():
    findings = [insight("z", columns=["c", "d"]), insight("a")]
    assert [found.id for found in rank_insights(findings)] == ["a", "z"]


def test_a_step_change_and_the_trend_it_causes_are_one_finding():
    values = np.concatenate([np.full(60, 100.0), np.full(60, 300.0)])
    frame = pd.DataFrame(
        {"day": pd.date_range("2024-01-01", periods=120).astype(str), "revenue": values}
    )
    generated = {found.insight_type for found in _generated(frame)}
    ranked = [found.insight_type for found in ranked_for(frame)]

    assert {"trend", "sudden_change"} <= generated
    assert ranked.count("trend") + ranked.count("sudden_change") == 1


def test_a_long_tail_is_not_reported_as_both_skew_and_outliers():
    # A real spread in the body of the column, so the quartiles are not identical
    # and the tail sits outside them.
    frame = pd.DataFrame(
        {"revenue": [*np.linspace(90, 110, 180), *np.linspace(1000, 9000, 20)]}
    )
    generated = {found.insight_type for found in _generated(frame)}
    ranked = [found.insight_type for found in ranked_for(frame)]

    assert {"outliers", "skewed_distribution"} <= generated
    assert ranked.count("outliers") + ranked.count("skewed_distribution") == 1


def test_the_same_phenomenon_in_different_columns_is_kept():
    first = insight("first", insight_type="outliers", columns=["revenue"])
    second = insight("second", insight_type="skewed_distribution", columns=["age"])

    assert len(rank_insights([first, second])) == 2


def test_a_correlation_implied_by_two_stronger_ones_is_dropped():
    # a-b and b-c both hold, so a-c follows and says nothing new.
    findings = [
        insight("ab", columns=["a", "b"], strength=0.98),
        insight("bc", columns=["b", "c"], strength=0.96),
        insight("ac", columns=["a", "c"], strength=0.94),
    ]
    assert [found.id for found in rank_insights(findings)] == ["ab", "bc"]


def test_a_correlation_bringing_in_a_new_column_is_kept():
    findings = [
        insight("ab", columns=["a", "b"], strength=0.98),
        insight("cd", columns=["c", "d"], strength=0.96),
    ]
    assert len(rank_insights(findings)) == 2


def test_three_mutually_correlated_columns_are_explained_by_two_relationships():
    base = np.linspace(1, 400, 400)
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "spend": base + rng.normal(0, 5, 400),
            "visits": base + rng.normal(0, 5, 400),
            "revenue": base + rng.normal(0, 5, 400),
        }
    )
    correlations = [found for found in ranked_for(frame) if found.insight_type == "correlation"]

    assert len(correlations) == 2


def test_no_more_than_a_few_findings_of_one_kind():
    findings = [
        insight(f"c{index}", columns=[f"x{index}", f"y{index}"], strength=0.9 - index / 100)
        for index in range(8)
    ]
    assert len(rank_insights(findings)) == MAX_PER_TYPE


def test_the_list_stays_short_enough_to_read():
    findings = [
        insight(
            f"{kind}-{index}",
            insight_type=kind,
            columns=[f"{kind}{index}"],
            strength=0.9,
        )
        for kind in TYPE_WEIGHTS
        for index in range(3)
    ]
    ranked = rank_insights(findings)

    assert len(findings) > MAX_INSIGHTS
    assert len(ranked) == MAX_INSIGHTS
    assert ranked == sorted(ranked, key=lambda found: -found.importance)


def test_the_strongest_finding_leads_the_real_dashboard_list():
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {
            "segment": ["enterprise"] * 150 + ["smb"] * 150,
            "revenue": [*rng.normal(240, 10, 150), *rng.normal(100, 10, 150)],
            "note": [f"row {index}" for index in range(300)],
        }
    )
    ranked = ranked_for(frame)

    assert ranked[0].insight_type == "group_difference"
    assert ranked == sorted(ranked, key=lambda found: -found.importance)


def _generated(frame: pd.DataFrame):
    profile = profile_dataset("x", "f.csv", frame)
    analysis = analyze_dataset(frame, profile)
    charts = build_charts(frame, profile, analysis)
    quality = check_dataset_quality(frame, profile)
    return generate_insights(profile, analysis, quality, charts.charts)

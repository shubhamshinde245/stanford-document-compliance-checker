"""Regression tests for the two-part match rule (DESIGN.md decision 15).

The bug this guards: `MATCH_THRESHOLD = 50.0` sat far below anything ada-002
produces, so `matched` was true for every input including a document with no
security content. The floor alone cannot separate the three committed fixtures.
The lead over the runner-up can, and these tests pin that down in both
directions -- the rule must reject the unrelated document *and* still accept the
two real procedures.
"""

from __future__ import annotations

import math

import pytest

from backend.llm.store import load_settings, save_settings
from backend.retrieve.match import IndexNotReady, check_upload, top_and_gap

# The measured field from the DESIGN.md "Verified behavior" table: the top two
# confidences each fixture produced against the real 36-policy index.
FIXTURES = {
    "01-compliant": (91.5, 85.8),
    "02-noncompliant": (88.1, 83.0),
    "03-unrelated": (71.6, 70.8),
}


def vector_for(similarity: float) -> list[float]:
    """A unit vector whose cosine against [1, 0] is exactly ``similarity``."""
    return [similarity, math.sqrt(max(0.0, 1.0 - similarity * similarity))]


async def run_check(parked_index, summary_row, fake_llm, confidences: list[float]):
    """Rank a document against a synthetic field with the given confidences."""
    rows = [summary_row(f"policy-{i}") for i in range(len(confidences))]
    parked_index(rows, [vector_for(c / 100) for c in confidences])
    fake_llm.vectors = [[1.0, 0.0]]
    return await check_upload("procedure.md", b"Some uploaded procedure text.")


# --------------------------------------------------------------------------
# top_and_gap
# --------------------------------------------------------------------------


def test_gap_is_distance_to_runner_up(make_match):
    top, gap = top_and_gap([make_match("a", 91.5), make_match("b", 85.8)])
    assert top == 91.5
    assert gap == pytest.approx(5.7)


def test_single_candidate_counts_its_whole_score_as_separation(make_match):
    """Nothing to be confused with, so the score itself is the separation."""
    top, gap = top_and_gap([make_match("only", 64.0)])
    assert (top, gap) == (64.0, 64.0)


def test_empty_field_has_no_top_and_no_gap():
    assert top_and_gap([]) == (0.0, 0.0)


def test_gap_ignores_everything_below_the_runner_up(make_match):
    """A long tail of near-ties must not change the verdict."""
    matches = [make_match(f"p{i}", c) for i, c in enumerate([91.5, 85.8, 85.7, 85.6])]
    assert top_and_gap(matches)[1] == pytest.approx(5.7)


# --------------------------------------------------------------------------
# The rule on the committed fixtures
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected_match"),
    [("01-compliant", True), ("02-noncompliant", True), ("03-unrelated", False)],
)
async def test_shipped_rule_separates_the_three_fixtures(
    fixture, expected_match, parked_index, summary_row, fake_llm, empty_catalog
):
    top, second = FIXTURES[fixture]
    response = await run_check(parked_index, summary_row, fake_llm, [top, second])
    assert response.matched is expected_match


async def test_old_floor_only_rule_would_have_matched_all_three(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """The defect, stated as a test: `top >= 50.0` separates nothing."""
    for top, second in FIXTURES.values():
        response = await run_check(parked_index, summary_row, fake_llm, [top, second])
        assert response.matches[0].confidence >= 50.0


async def test_unrelated_document_reports_the_gap_that_failed(
    parked_index, summary_row, fake_llm, empty_catalog
):
    top, second = FIXTURES["03-unrelated"]
    response = await run_check(parked_index, summary_row, fake_llm, [top, second])
    assert response.matched is False
    assert response.match_gap == pytest.approx(0.8, abs=0.05)
    assert response.match_gap < response.match_min_gap
    # The floor passed; only the lead test rejected it. This is the distinction
    # the UI reports back to the reviewer.
    assert response.matches[0].confidence > response.match_threshold


# --------------------------------------------------------------------------
# Both tests are load-bearing
# --------------------------------------------------------------------------


async def test_high_score_with_no_lead_is_not_a_match(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """Two standards tied at the top is exactly the case the floor misses."""
    response = await run_check(parked_index, summary_row, fake_llm, [95.0, 94.5])
    assert response.matched is False


async def test_big_lead_below_the_floor_is_not_a_match(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """A clear winner in a uniformly weak field is still not a match."""
    response = await run_check(parked_index, summary_row, fake_llm, [30.0, 10.0])
    assert response.matched is False
    assert response.match_gap == pytest.approx(20.0, abs=0.05)


async def test_empty_index_is_an_error_not_a_no_match(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """An unbuilt index must not be reported as "nothing matched".

    The two mean different things to a reviewer: one is "run `make index`", the
    other is "this document has no standard". The 503 keeps them apart.
    """
    with pytest.raises(IndexNotReady):
        await run_check(parked_index, summary_row, fake_llm, [])


# --------------------------------------------------------------------------
# The thresholds are live settings, not constants
# --------------------------------------------------------------------------


async def test_raising_the_lead_unmatches_the_compliant_fixture(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """DESIGN.md claims raising the lead to 6.0 un-matches fixture 01 (lead 5.7).

    This is what makes the Settings control real rather than cosmetic.
    """
    top, second = FIXTURES["01-compliant"]
    before = await run_check(parked_index, summary_row, fake_llm, [top, second])
    assert before.matched is True

    save_settings({**load_settings(), "match_min_gap": 6.0})

    after = await run_check(parked_index, summary_row, fake_llm, [top, second])
    assert after.matched is False
    assert after.match_min_gap == 6.0


async def test_lowering_the_lead_matches_the_unrelated_fixture(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """The gate opens both ways -- a reviewer can widen it until noise passes."""
    top, second = FIXTURES["03-unrelated"]
    save_settings({**load_settings(), "match_min_gap": 0.5})
    response = await run_check(parked_index, summary_row, fake_llm, [top, second])
    assert response.matched is True


async def test_response_echoes_the_live_thresholds(
    parked_index, summary_row, fake_llm, empty_catalog
):
    """The UI states the rule on screen, so it has to be told what the rule is."""
    save_settings({**load_settings(), "match_min_confidence": 61.0, "match_min_gap": 3.5})
    response = await run_check(parked_index, summary_row, fake_llm, [91.5, 85.8])
    assert response.match_threshold == 61.0
    assert response.match_min_gap == 3.5

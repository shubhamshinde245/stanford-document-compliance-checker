"""Saved-report persistence.

Report ids come in off the URL, so the id validation here is the boundary that
keeps a request from addressing a file outside ``data/reports``.
"""

from __future__ import annotations

import json

import pytest

from backend.models import EvaluateCounts, EvaluateFinding, EvaluateResponse
from backend.retrieve.reports import (
    ReportError,
    delete_report,
    list_reports,
    load_report,
    save_report,
)


def make_evaluation(slug: str = "access-management-policy", score: float = 75.0):
    return EvaluateResponse(
        slug=slug,
        title=slug.replace("-", " ").title(),
        category="Policy",
        source_url=f"https://example.test/{slug}",
        pdf_url=f"https://example.test/{slug}.pdf",
        model="gpt-5.6-sol",
        reasoning_effort="high",
        score=score,
        counts=EvaluateCounts(aligned=3, contradicted=1, missing=0, flagged=0),
        rows=[
            EvaluateFinding(
                requirement_id="REQ-1",
                definition="Accounts must be reviewed quarterly.",
                verdict="aligned",
                requirement_quote="Accounts must be reviewed quarterly.",
                evidence_quote="We review accounts every quarter.",
                rationale="Stated directly.",
            )
        ],
    )


def save_one(matches=None, **kwargs):
    return save_report(
        filename=kwargs.pop("filename", "procedure.md"),
        check_id=kwargs.pop("check_id", "check-123"),
        matches=matches or [],
        evaluation=kwargs.pop("evaluation", make_evaluation()),
    )


# --------------------------------------------------------------------------
# Round-trip
# --------------------------------------------------------------------------


def test_save_returns_a_report_carrying_its_own_id():
    saved = save_one()
    assert saved.id
    assert saved.evaluation.report_id == saved.id


def test_the_returned_evaluation_is_what_the_endpoint_hands_back():
    """`evaluate_upload` returns `saved.evaluation`, so the id must be stamped."""
    saved = save_one()
    assert saved.evaluation.report_id is not None
    assert saved.evaluation.slug == saved.slug
    assert saved.evaluation.rows == saved.evaluation.rows


def test_save_writes_one_json_file_named_by_id(isolated_reports):
    saved = save_one()
    files = list(isolated_reports.glob("*.json"))
    assert [path.name for path in files] == [f"{saved.id}.json"]


def test_load_round_trips_every_field():
    saved = save_one(filename="quarterly-review.md")
    loaded = load_report(saved.id)
    assert loaded is not None
    assert loaded.filename == "quarterly-review.md"
    assert loaded.check_id == "check-123"
    assert loaded.score == saved.score
    assert loaded.counts == saved.counts
    assert loaded.evaluation.rows[0].requirement_id == "REQ-1"


def test_summary_mirrors_the_evaluation_it_was_built_from():
    saved = save_one(evaluation=make_evaluation(slug="log-management-policy", score=42.5))
    assert saved.slug == "log-management-policy"
    assert saved.score == 42.5
    assert saved.counts.aligned == 3


def test_top_matches_are_stored_alongside_the_verdicts(make_match):
    saved = save_one(matches=[make_match("a", 91.5), make_match("b", 85.8)])
    assert [item.slug for item in saved.matches] == ["a", "b"]
    assert saved.matches[0].confidence == 91.5


def test_only_the_top_five_matches_are_kept(make_match):
    saved = save_one(matches=[make_match(f"p{i}", 90 - i) for i in range(12)])
    assert len(saved.matches) == 5


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------


def test_listing_is_empty_before_anything_is_saved():
    assert list_reports() == []


def test_listing_returns_newest_first(monkeypatch):
    stamps = iter(
        [
            "2026-01-01T00:00:00+00:00",
            "2026-06-01T00:00:00+00:00",
            "2026-03-01T00:00:00+00:00",
        ]
    )
    monkeypatch.setattr("backend.retrieve.reports.utc_now", lambda: next(stamps))
    save_one(filename="oldest.md")
    save_one(filename="newest.md")
    save_one(filename="middle.md")
    assert [row.filename for row in list_reports()] == [
        "newest.md",
        "middle.md",
        "oldest.md",
    ]


def test_listing_skips_a_corrupt_file_instead_of_failing(isolated_reports):
    """One bad file must not take out the whole Reports page."""
    good = save_one(filename="good.md")
    (isolated_reports / "broken.json").write_text("{not json", encoding="utf-8")
    (isolated_reports / "wrong-shape.json").write_text(
        json.dumps({"unexpected": True}), encoding="utf-8"
    )
    rows = list_reports()
    assert [row.id for row in rows] == [good.id]


def test_listing_ignores_non_json_files(isolated_reports):
    save_one()
    (isolated_reports / "notes.txt").write_text("scratch", encoding="utf-8")
    assert len(list_reports()) == 1


# --------------------------------------------------------------------------
# Id validation -- the path-traversal boundary
# --------------------------------------------------------------------------


TRAVERSAL_IDS = [
    "../../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "/etc/passwd",
    "..",
    "report",
    "",
    "a" * 200,
    "12345678-1234-1234-1234-12345678901Z",
]


@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_load_rejects_anything_that_is_not_a_uuid(bad_id):
    with pytest.raises(ReportError) as caught:
        load_report(bad_id)
    assert caught.value.status_code == 400


@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_delete_rejects_anything_that_is_not_a_uuid(bad_id):
    with pytest.raises(ReportError):
        delete_report(bad_id)


def test_a_valid_uuid_that_was_never_saved_is_absent_not_an_error():
    """Absent and malformed are different answers: 404 versus 400."""
    assert load_report("3f2504e0-4f89-11d3-9a0c-0305e82c3301") is None


# --------------------------------------------------------------------------
# Deletion
# --------------------------------------------------------------------------


def test_delete_removes_the_file(isolated_reports):
    saved = save_one()
    assert delete_report(saved.id) is True
    assert list(isolated_reports.glob("*.json")) == []


def test_delete_is_not_idempotent_it_reports_the_second_call_as_absent():
    saved = save_one()
    assert delete_report(saved.id) is True
    assert delete_report(saved.id) is False


def test_delete_leaves_the_other_reports_alone():
    first = save_one(filename="first.md")
    second = save_one(filename="second.md")
    delete_report(first.id)
    assert [row.id for row in list_reports()] == [second.id]


def test_saving_twice_produces_two_distinct_reports():
    first = save_one()
    second = save_one()
    assert first.id != second.id
    assert len(list_reports()) == 2

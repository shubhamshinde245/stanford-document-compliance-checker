"""Verdict normalization -- the layer that refuses to trust the model.

Every rule here exists so a reviewer can trace a verdict back to a real sentence
in a real document. A claim the model cannot support with a quote from a chunk
it was actually given must not survive as `aligned`.
"""

from __future__ import annotations

import pytest

from backend.retrieve.chunk import Chunk
from backend.retrieve.evaluate import (
    _counts,
    _normalize_finding,
    _parse_rows,
    quote_in_text,
)

REQUIREMENT = {
    "requirement_id": "REQ-1",
    "definition": "Privileged accounts must be reviewed quarterly.",
}

CHUNK = Chunk(
    chunk_id="doc:p1:c1",
    text="Section 4. We review all privileged accounts every quarter and log the outcome.",
    page=1,
    index=1,
)


def normalize(row, allowed=(CHUNK,), requirement=None):
    return _normalize_finding(requirement or REQUIREMENT, row, list(allowed))


def good_row(**overrides):
    row = {
        "requirement_id": "REQ-1",
        "verdict": "aligned",
        "requirement_quote": "Privileged accounts must be reviewed quarterly.",
        "evidence_quote": "We review all privileged accounts every quarter",
        "rationale": "The procedure states the quarterly review.",
        "sources": [{"chunk_id": "doc:p1:c1", "quote": "every quarter"}],
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------
# quote_in_text
# --------------------------------------------------------------------------


def test_quote_matches_verbatim():
    assert quote_in_text("every quarter", CHUNK.text) is True


def test_quote_matches_across_reflowed_whitespace():
    """PDF extraction reflows lines; a quote must survive that."""
    assert quote_in_text("every    quarter", "we review\nevery quarter") is True
    assert quote_in_text("we review every quarter", "we review\n  every\tquarter") is True


def test_an_absent_quote_does_not_match():
    assert quote_in_text("annually", CHUNK.text) is False


@pytest.mark.parametrize("empty", ["", "   ", "\n"])
def test_an_empty_quote_never_matches(empty):
    assert quote_in_text(empty, CHUNK.text) is False


def test_matching_is_case_sensitive():
    """Verbatim means verbatim; a case change is a paraphrase."""
    assert quote_in_text("EVERY QUARTER", CHUNK.text) is False


# --------------------------------------------------------------------------
# A well-formed row survives intact
# --------------------------------------------------------------------------


def test_a_grounded_aligned_row_is_kept():
    finding = normalize(good_row())
    assert finding.verdict == "aligned"
    assert finding.evidence_quote == "We review all privileged accounts every quarter"
    assert [source.chunk_id for source in finding.sources] == ["doc:p1:c1"]


def test_a_grounded_contradicted_row_is_kept():
    finding = normalize(good_row(verdict="contradicted"))
    assert finding.verdict == "contradicted"


# --------------------------------------------------------------------------
# Ungrounded claims are downgraded
# --------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["aligned", "contradicted"])
def test_a_quote_not_in_any_chunk_is_flagged(verdict):
    """The core anti-hallucination rule."""
    finding = normalize(
        good_row(
            verdict=verdict,
            evidence_quote="We review accounts annually.",
            rationale="",
        )
    )
    assert finding.verdict == "flagged"
    assert "not found in the retrieved chunks" in finding.rationale


def test_a_downgrade_keeps_the_model_rationale_when_it_gave_one():
    finding = normalize(
        good_row(
            evidence_quote="Nowhere in the document.",
            rationale="My own explanation.",
        )
    )
    assert finding.verdict == "flagged"
    assert finding.rationale == "My own explanation."


@pytest.mark.parametrize("verdict", ["aligned", "contradicted"])
def test_citing_a_chunk_that_was_not_supplied_is_flagged(verdict):
    """A real quote plus an invented chunk id is still not traceable."""
    finding = normalize(
        good_row(
            verdict=verdict,
            sources=[{"chunk_id": "doc:p9:c9", "quote": "invented"}],
        )
    )
    assert finding.verdict == "flagged"


def test_unknown_sources_are_dropped_from_the_output():
    finding = normalize(
        good_row(
            sources=[
                {"chunk_id": "doc:p1:c1", "quote": "every quarter"},
                {"chunk_id": "doc:p9:c9", "quote": "invented"},
            ]
        )
    )
    assert [source.chunk_id for source in finding.sources] == ["doc:p1:c1"]


def test_an_empty_evidence_quote_cannot_support_an_aligned_verdict():
    finding = normalize(good_row(evidence_quote=""))
    assert finding.verdict == "flagged"


# --------------------------------------------------------------------------
# missing
# --------------------------------------------------------------------------


def test_missing_clears_evidence_that_was_never_grounded():
    finding = normalize(
        good_row(verdict="missing", evidence_quote="Something invented.", rationale="")
    )
    assert finding.verdict == "missing"
    assert finding.evidence_quote == ""
    assert finding.sources == []
    assert finding.rationale == "No supporting passage was found in the uploaded document."


def test_missing_keeps_evidence_that_is_grounded():
    """A grounded quote can legitimately accompany 'the procedure never says'."""
    finding = normalize(good_row(verdict="missing"))
    assert finding.verdict == "missing"
    assert finding.evidence_quote == "We review all privileged accounts every quarter"


def test_a_requirement_the_model_skipped_becomes_missing():
    finding = normalize(None)
    assert finding.verdict == "missing"
    assert finding.requirement_quote == REQUIREMENT["definition"]
    assert finding.evidence_quote == ""
    assert finding.rationale == "The model did not return a row for this requirement."


# --------------------------------------------------------------------------
# Field defaults
# --------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["approved", "", None, "ALIGNED?", 42])
def test_an_unrecognized_verdict_becomes_flagged(verdict):
    finding = normalize(good_row(verdict=verdict, evidence_quote=""))
    assert finding.verdict == "flagged"


@pytest.mark.parametrize("verdict", ["ALIGNED", "  aligned  ", "Aligned"])
def test_verdict_case_and_padding_are_tolerated(verdict):
    assert normalize(good_row(verdict=verdict)).verdict == "aligned"


def test_a_blank_requirement_quote_falls_back_to_the_definition():
    finding = normalize(good_row(requirement_quote=""))
    assert finding.requirement_quote == REQUIREMENT["definition"]


def test_the_requirement_id_always_comes_from_the_requirement_not_the_model():
    """The model must never be able to relabel which requirement it answered."""
    finding = normalize(good_row(requirement_id="REQ-SOMETHING-ELSE"))
    assert finding.requirement_id == "REQ-1"


@pytest.mark.parametrize("sources", [None, "not-a-list", 42, [1, 2], [{}]])
def test_malformed_sources_degrade_to_an_empty_list(sources):
    finding = normalize(good_row(sources=sources))
    assert finding.sources == []


# --------------------------------------------------------------------------
# Parsing the model's reply
# --------------------------------------------------------------------------


def test_parses_a_plain_rows_object():
    assert _parse_rows('{"rows": [{"requirement_id": "R1"}]}') == [
        {"requirement_id": "R1"}
    ]


def test_parses_a_bare_array():
    assert _parse_rows('[{"requirement_id": "R1"}]') == [{"requirement_id": "R1"}]


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"rows": [{"requirement_id": "R1"}]}\n```',
        '```\n{"rows": [{"requirement_id": "R1"}]}\n```',
        'Here you go:\n```json\n{"rows": [{"requirement_id": "R1"}]}\n```\nHope that helps.',
    ],
)
def test_parses_through_a_markdown_fence(content):
    """Providers without strict json_schema wrap their JSON in a fence."""
    assert _parse_rows(content) == [{"requirement_id": "R1"}]


@pytest.mark.parametrize(
    "content", ["", "   ", "not json", "{broken", '{"rows": "not-a-list"}', "null", "42"]
)
def test_unparseable_content_yields_no_rows(content):
    assert _parse_rows(content) == []


def test_non_object_entries_are_dropped():
    assert _parse_rows('{"rows": [{"a": 1}, "junk", 5, null]}') == [{"a": 1}]


# --------------------------------------------------------------------------
# Counts
# --------------------------------------------------------------------------


def test_counts_tally_each_verdict():
    rows = [
        normalize(good_row()),
        normalize(good_row(verdict="contradicted")),
        normalize(good_row(verdict="missing", evidence_quote="")),
        normalize(good_row(verdict="nonsense", evidence_quote="")),
    ]
    counts = _counts(rows)
    assert (counts.aligned, counts.contradicted, counts.missing, counts.flagged) == (
        1,
        1,
        1,
        1,
    )


def test_counts_of_nothing_are_all_zero():
    counts = _counts([])
    assert (counts.aligned, counts.contradicted, counts.missing, counts.flagged) == (
        0,
        0,
        0,
        0,
    )

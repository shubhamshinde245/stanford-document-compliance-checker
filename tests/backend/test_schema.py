"""Output-column normalization and the compiled json_schema.

The four locked columns are what the exercise grades, so the invariant under
test is that no saved settings file can remove them, rename them, or move them
out of first position.
"""

from __future__ import annotations

import pytest

from backend.llm.schema import (
    LOCKED_COLUMNS,
    MAX_COLUMNS,
    VERDICTS,
    build_system_prompt,
    compile_json_schema,
    default_columns,
    normalize_columns,
)

LOCKED_ORDER = [column["name"] for column in LOCKED_COLUMNS]


# --------------------------------------------------------------------------
# Locked columns
# --------------------------------------------------------------------------


def test_defaults_lead_with_the_locked_columns():
    names = [column["name"] for column in default_columns()]
    assert names[: len(LOCKED_ORDER)] == LOCKED_ORDER


def test_locked_columns_are_restored_when_absent():
    merged = normalize_columns([{"name": "notes", "description": "Free text."}], strict=False)
    names = [column["name"] for column in merged]
    assert names[: len(LOCKED_ORDER)] == LOCKED_ORDER
    assert "notes" in names


def test_a_saved_locked_column_overrides_only_its_description():
    merged = normalize_columns(
        [{"name": "verdict", "description": "My own wording."}], strict=True
    )
    verdict = next(item for item in merged if item["name"] == "verdict")
    assert verdict["description"] == "My own wording."
    assert [column["name"] for column in merged][: len(LOCKED_ORDER)] == LOCKED_ORDER


def test_a_locked_column_cannot_be_reordered_ahead_of_the_others():
    merged = normalize_columns(
        [
            {"name": "evidence_quote", "description": "Moved to the front."},
            {"name": "requirement_id", "description": "Now second."},
        ],
        strict=True,
    )
    assert [column["name"] for column in merged][: len(LOCKED_ORDER)] == LOCKED_ORDER


def test_custom_columns_keep_their_relative_order():
    merged = normalize_columns(
        [
            {"name": "beta", "description": "Second custom."},
            {"name": "alpha", "description": "First custom."},
        ],
        strict=True,
    )
    custom = [c["name"] for c in merged if c["name"] not in LOCKED_ORDER]
    assert custom == ["beta", "alpha"]


# --------------------------------------------------------------------------
# strict=True rejects, strict=False drops
# --------------------------------------------------------------------------


BAD_ROWS = [
    pytest.param({"name": "Bad Name", "description": "x"}, id="uppercase-and-space"),
    pytest.param({"name": "9lives", "description": "x"}, id="leading-digit"),
    pytest.param({"name": "", "description": "x"}, id="empty-name"),
    pytest.param({"name": "ok", "description": "   "}, id="blank-description"),
    pytest.param({"name": "ok", "description": "x" * 601}, id="description-too-long"),
    pytest.param("not-a-dict", id="not-an-object"),
    pytest.param({"name": "a" * 41, "description": "x"}, id="name-too-long"),
]


@pytest.mark.parametrize("row", BAD_ROWS)
def test_strict_rejects_a_bad_row(row):
    with pytest.raises(ValueError):
        normalize_columns([row], strict=True)


@pytest.mark.parametrize("row", BAD_ROWS)
def test_non_strict_drops_a_bad_row_and_still_returns_the_locked_set(row):
    merged = normalize_columns([row], strict=False)
    assert [column["name"] for column in merged] == LOCKED_ORDER


def test_strict_rejects_a_duplicate_name():
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_columns(
            [
                {"name": "notes", "description": "First."},
                {"name": "notes", "description": "Second."},
            ],
            strict=True,
        )


def test_non_strict_keeps_the_first_of_a_duplicate_pair():
    merged = normalize_columns(
        [
            {"name": "notes", "description": "First."},
            {"name": "notes", "description": "Second."},
        ],
        strict=False,
    )
    notes = [c for c in merged if c["name"] == "notes"]
    assert len(notes) == 1 and notes[0]["description"] == "First."


def test_strict_rejects_too_many_columns():
    rows = [{"name": f"c{i}", "description": "x"} for i in range(MAX_COLUMNS + 1)]
    with pytest.raises(ValueError, match="Too many columns"):
        normalize_columns(rows, strict=True)


def test_non_strict_truncates_to_the_limit():
    rows = [{"name": f"c{i}", "description": "x"} for i in range(MAX_COLUMNS + 5)]
    merged = normalize_columns(rows, strict=False)
    assert len(merged) == MAX_COLUMNS


def test_description_whitespace_is_collapsed():
    merged = normalize_columns(
        [{"name": "notes", "description": "  two\n\nlines   here  "}], strict=True
    )
    notes = next(item for item in merged if item["name"] == "notes")
    assert notes["description"] == "two lines here"


def test_a_name_is_lowercased_before_matching_a_locked_one():
    merged = normalize_columns(
        [{"name": "  VERDICT  ", "description": "Shouted."}], strict=True
    )
    verdict = next(item for item in merged if item["name"] == "verdict")
    assert verdict["description"] == "Shouted."
    assert len(merged) == len(default_columns()) - 1  # rationale not supplied


@pytest.mark.parametrize("value", [None, "string", 42, {"a": 1}])
def test_a_non_list_value_yields_the_locked_set(value):
    assert [c["name"] for c in normalize_columns(value, strict=False)] == LOCKED_ORDER


# --------------------------------------------------------------------------
# Compiled schema
# --------------------------------------------------------------------------


def test_schema_is_strict_and_closed():
    schema = compile_json_schema(default_columns())
    assert schema["strict"] is True
    row = schema["schema"]["properties"]["rows"]["items"]
    assert row["additionalProperties"] is False
    assert schema["schema"]["additionalProperties"] is False


def test_every_column_is_required():
    columns = default_columns()
    row = compile_json_schema(columns)["schema"]["properties"]["rows"]["items"]
    for column in columns:
        assert column["name"] in row["required"]


def test_verdict_is_an_enum_of_the_four_verdicts():
    row = compile_json_schema(default_columns())["schema"]["properties"]["rows"]["items"]
    assert row["properties"]["verdict"]["enum"] == list(VERDICTS)


def test_sources_is_always_present_even_though_it_is_not_a_column():
    """Provenance is not user-configurable; every row must cite its chunks."""
    columns = [{"name": "requirement_id", "description": "Only this one."}]
    row = compile_json_schema(normalize_columns(columns, strict=True))["schema"][
        "properties"
    ]["rows"]["items"]
    assert "sources" in row["properties"]
    assert "sources" in row["required"]
    assert row["properties"]["sources"]["type"] == "array"


def test_a_custom_column_reaches_the_schema_with_its_description():
    columns = normalize_columns(
        [{"name": "severity", "description": "How bad it is."}], strict=True
    )
    row = compile_json_schema(columns)["schema"]["properties"]["rows"]["items"]
    assert row["properties"]["severity"]["description"] == "How bad it is."


# --------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------


def test_system_prompt_lists_every_column_and_the_grounding_rules():
    columns = normalize_columns(
        [{"name": "severity", "description": "How bad it is."}], strict=True
    )
    prompt = build_system_prompt(columns)
    for column in columns:
        assert column["name"] in prompt
    assert "Quote verbatim" in prompt
    assert "sources" in prompt

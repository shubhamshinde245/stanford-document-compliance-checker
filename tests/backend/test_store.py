"""Settings load/save.

The asymmetry under test: the save path rejects bad input with a message the UI
shows, the load path silently falls back so a hand-edited file cannot brick
startup. Both halves matter, and they are easy to accidentally unify.
"""

from __future__ import annotations

import json

import pytest

from backend.llm.store import DEFAULTS, LLMConfigError, load_settings, save_settings


def valid_payload(**overrides):
    payload = {
        "provider": "stanford",
        "chat_model": "gpt-5.6-sol",
        "embedding_model": "text-embedding-ada-002",
        "reasoning_effort": "medium",
        "match_min_confidence": 50.0,
        "match_min_gap": 2.5,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# Defaults and round-trip
# --------------------------------------------------------------------------


def test_missing_file_yields_defaults(isolated_settings):
    isolated_settings.unlink()
    data = load_settings()
    assert data["provider"] in {"stanford", "openai", "anthropic"}
    assert data["match_min_confidence"] == DEFAULTS["match_min_confidence"]
    assert data["match_min_gap"] == DEFAULTS["match_min_gap"]


def test_save_then_load_round_trips(isolated_settings):
    save_settings(valid_payload(match_min_confidence=61.5, match_min_gap=4.25))
    data = load_settings()
    assert data["match_min_confidence"] == 61.5
    assert data["match_min_gap"] == 4.25


def test_save_persists_to_disk(isolated_settings):
    save_settings(valid_payload(chat_model="gpt-5.6-sol", match_min_gap=3.0))
    written = json.loads(isolated_settings.read_text(encoding="utf-8"))
    assert written["match_min_gap"] == 3.0


# --------------------------------------------------------------------------
# Save path: reject loudly
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.1, 100.1, 1000, -5])
def test_save_rejects_out_of_range_bounds(bad):
    with pytest.raises(LLMConfigError, match="between"):
        save_settings(valid_payload(match_min_confidence=bad))


@pytest.mark.parametrize("bad", ["abc", None, [], {}])
def test_save_rejects_non_numeric_bounds(bad):
    with pytest.raises(LLMConfigError, match="must be a number"):
        save_settings(valid_payload(match_min_gap=bad))


def test_error_message_names_the_field_in_words():
    """The message goes straight to a form field, so it cannot say 'match_min_gap'."""
    with pytest.raises(LLMConfigError) as caught:
        save_settings(valid_payload(match_min_gap="nope"))
    assert "match min gap" in str(caught.value)


def test_save_rejects_unknown_provider():
    with pytest.raises(LLMConfigError):
        save_settings(valid_payload(provider="hal9000"))


def test_save_rejects_unknown_effort():
    with pytest.raises(LLMConfigError, match="none, low, medium, or high"):
        save_settings(valid_payload(reasoning_effort="extreme"))


def test_save_rounds_to_two_decimals():
    save_settings(valid_payload(match_min_gap=2.5555))
    assert load_settings()["match_min_gap"] == 2.56


def test_bounds_accept_the_inclusive_edges():
    save_settings(valid_payload(match_min_confidence=0, match_min_gap=100))
    data = load_settings()
    assert (data["match_min_confidence"], data["match_min_gap"]) == (0.0, 100.0)


# --------------------------------------------------------------------------
# Load path: fall back quietly
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["not-a-number", None, -12, 900, [1, 2], {"a": 1}])
def test_load_falls_back_on_a_bad_bound(isolated_settings, bad):
    """A hand-edited file must still start the app."""
    isolated_settings.write_text(
        json.dumps({"match_min_confidence": bad, "match_min_gap": bad}),
        encoding="utf-8",
    )
    data = load_settings()
    assert data["match_min_confidence"] == DEFAULTS["match_min_confidence"]
    assert data["match_min_gap"] == DEFAULTS["match_min_gap"]


def test_json_true_is_read_as_one_not_rejected(isolated_settings):
    """Known quirk, pinned so a change to it is deliberate.

    `float(True)` is 1.0 and 1.0 is in range, so a JSON `true` slips through
    both the load and save paths as a valid bound rather than falling back.
    Harmless today -- a 1.0 lead is a plausible setting -- but it means the
    bounds do not reject every wrong *type*, only every wrong *value*.
    """
    isolated_settings.write_text(
        json.dumps({"match_min_gap": True}), encoding="utf-8"
    )
    assert load_settings()["match_min_gap"] == 1.0


def test_load_falls_back_on_a_bad_effort(isolated_settings):
    isolated_settings.write_text(
        json.dumps({"reasoning_effort": "extreme"}), encoding="utf-8"
    )
    assert load_settings()["reasoning_effort"] == "medium"


def test_load_survives_corrupt_json(isolated_settings):
    isolated_settings.write_text("{not json at all", encoding="utf-8")
    assert load_settings()["match_min_gap"] == DEFAULTS["match_min_gap"]


def test_load_keeps_a_good_value_beside_a_bad_one(isolated_settings):
    """One bad field must not discard the whole file."""
    isolated_settings.write_text(
        json.dumps({"match_min_confidence": 66.0, "match_min_gap": "broken"}),
        encoding="utf-8",
    )
    data = load_settings()
    assert data["match_min_confidence"] == 66.0
    assert data["match_min_gap"] == DEFAULTS["match_min_gap"]


def test_partial_save_leaves_other_fields_alone():
    save_settings(valid_payload(match_min_gap=7.0))
    save_settings({"match_min_confidence": 55.0})
    data = load_settings()
    assert data["match_min_confidence"] == 55.0
    assert data["match_min_gap"] == 7.0

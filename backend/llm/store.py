from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from backend.llm.schema import default_columns, normalize_columns
from backend.settings import LLM_PROVIDER, ROOT

SETTINGS_PATH = ROOT / "data" / "llm-settings.json"

ProviderId = Literal["stanford", "openai", "anthropic"]
EffortLevel = Literal["none", "low", "medium", "high"]

VALID_PROVIDERS = {"stanford", "openai", "anthropic"}
VALID_EFFORTS = {"none", "low", "medium", "high"}

DEFAULTS: dict[str, Any] = {
    "provider": "stanford",
    "chat_model": "gpt-5.6-sol",
    "embedding_model": "text-embedding-ada-002",
    "reasoning_effort": "medium",
    "match_min_confidence": 50.0,
    "match_min_gap": 2.5,
    "output_columns": default_columns(),
}

# Cosine similarity from text-embedding-ada-002 is compressed into a narrow band,
# so an absolute floor alone cannot separate a real match from noise. The gap
# between the best policy and the runner-up can: it is near zero when nothing
# genuinely matches. The floor is kept as a cheap sanity check for models with
# better separation.
MIN_BOUND = 0.0
MAX_BOUND = 100.0


class LLMConfigError(ValueError):
    """Invalid saved or requested LLM settings."""


def _normalize_provider(value: str) -> str:
    provider = value.strip().lower()
    if provider == "ollama":
        raise LLMConfigError(
            "Ollama is a placeholder fallback and cannot be selected yet."
        )
    if provider not in VALID_PROVIDERS:
        raise LLMConfigError("Provider must be stanford, openai, or anthropic.")
    return provider


def _coerce_bound(value: Any, fallback: float) -> float:
    """Load path: a bad value falls back so a hand-edited file cannot brick startup."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if number < MIN_BOUND or number > MAX_BOUND:
        return float(fallback)
    return round(number, 2)


def _require_bound(value: Any, key: str) -> float:
    """Save path: a bad value is rejected with a message the UI can show."""
    label = key.replace("_", " ")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LLMConfigError(f"{label} must be a number.") from None
    if number < MIN_BOUND or number > MAX_BOUND:
        raise LLMConfigError(
            f"{label} must be between {MIN_BOUND:g} and {MAX_BOUND:g}."
        )
    return round(number, 2)


def default_settings() -> dict[str, Any]:
    provider = LLM_PROVIDER if LLM_PROVIDER in VALID_PROVIDERS else "stanford"
    return {
        **DEFAULTS,
        "provider": provider,
    }


def load_settings() -> dict[str, Any]:
    data = default_settings()
    if SETTINGS_PATH.is_file():
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            data.update({key: loaded[key] for key in DEFAULTS if key in loaded})
    try:
        data["provider"] = _normalize_provider(str(data.get("provider") or "stanford"))
    except LLMConfigError:
        data["provider"] = default_settings()["provider"]
    data["chat_model"] = str(data.get("chat_model") or DEFAULTS["chat_model"]).strip()
    data["embedding_model"] = str(
        data.get("embedding_model") or DEFAULTS["embedding_model"]
    ).strip()
    effort = str(data.get("reasoning_effort") or DEFAULTS["reasoning_effort"]).strip()
    data["reasoning_effort"] = effort if effort in VALID_EFFORTS else "medium"
    for key in ("match_min_confidence", "match_min_gap"):
        data[key] = _coerce_bound(data.get(key), DEFAULTS[key])
    data["output_columns"] = normalize_columns(data.get("output_columns"), strict=False)
    return data


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    if "provider" in payload:
        current["provider"] = _normalize_provider(str(payload["provider"]))
    if "chat_model" in payload:
        chat_model = str(payload["chat_model"]).strip()
        if not chat_model:
            raise LLMConfigError("Chat model is required.")
        current["chat_model"] = chat_model
    if "embedding_model" in payload:
        embedding_model = str(payload["embedding_model"]).strip()
        if not embedding_model:
            raise LLMConfigError("Embedding model is required.")
        current["embedding_model"] = embedding_model
    if "reasoning_effort" in payload:
        effort = str(payload["reasoning_effort"]).strip()
        if effort not in VALID_EFFORTS:
            raise LLMConfigError("Effort must be none, low, medium, or high.")
        current["reasoning_effort"] = effort
    for key in ("match_min_confidence", "match_min_gap"):
        if key in payload:
            current[key] = _require_bound(payload[key], key)
    if payload.get("output_columns") is not None:
        try:
            current["output_columns"] = normalize_columns(
                payload["output_columns"], strict=True
            )
        except ValueError as exc:
            raise LLMConfigError(str(exc)) from exc
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(current, indent=2) + "\n",
        encoding="utf-8",
    )
    return current

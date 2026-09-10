"""Shared fixtures.

Two rules hold for every test in this package:

1. Nothing touches the network. The LLM router is replaced by a deterministic
   fake, so a missing API key can never turn into a skipped or flaky test.
2. Nothing touches real ``data/``. Settings, reports, and the parked index are
   redirected into ``tmp_path``, so a run cannot clobber a scraped catalog or a
   saved report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from backend.llm import store
from backend.models import PolicyMatch
from backend.retrieve import index as index_module
from backend.retrieve import reports as reports_module
from backend.retrieve.text import PageText

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "documents"


# --------------------------------------------------------------------------
# Isolation
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the settings store at a scratch file seeded with the defaults."""
    path = tmp_path / "llm-settings.json"
    path.write_text(
        json.dumps(
            {
                "provider": "stanford",
                "chat_model": "gpt-5.6-sol",
                "embedding_model": "text-embedding-ada-002",
                "reasoning_effort": "medium",
                "match_min_confidence": 50.0,
                "match_min_gap": 2.5,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "SETTINGS_PATH", path)
    return path


@pytest.fixture(autouse=True)
def isolated_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "reports"
    path.mkdir()
    monkeypatch.setattr(reports_module, "REPORTS_DIR", path)
    return path


@pytest.fixture(autouse=True)
def no_real_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every provider reports configured so tests exercise logic, not key checks."""
    monkeypatch.setattr(
        "backend.llm.providers.configured_providers",
        lambda: {
            "stanford": True,
            "openai": True,
            "anthropic": True,
            "ollama": False,
        },
    )


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    """Check sessions live in a module-level dict; keep tests independent."""
    from backend.retrieve import session

    session._SESSIONS.clear()


# --------------------------------------------------------------------------
# Fake embeddings
# --------------------------------------------------------------------------


def unit_vector(*values: float) -> list[float]:
    array = np.asarray(values, dtype=np.float32)
    return (array / np.linalg.norm(array)).tolist()


class FakeLLM:
    """Deterministic stand-in for ``backend.llm.router.llm``.

    ``embed_many`` returns a caller-supplied vector per input text so a test can
    dictate the exact similarity field it wants to assert on. ``chat`` replays a
    queue of canned JSON bodies.
    """

    def __init__(self) -> None:
        self.vectors: list[list[float]] = []
        self.chat_replies: list[str] = []
        self.chat_calls: list[dict[str, Any]] = []
        self.embed_calls: list[list[str]] = []
        self.model = "text-embedding-ada-002"

    async def embed_many(self, texts: list[str], **_: Any) -> dict[str, Any]:
        self.embed_calls.append(list(texts))
        if not self.vectors:
            raise AssertionError("FakeLLM.vectors was not primed for this call.")
        # Cycle so a caller priming one vector can embed any number of chunks.
        picked = [self.vectors[i % len(self.vectors)] for i in range(len(texts))]
        return {"model": self.model, "embeddings": picked}

    async def embed(self, text: str, **_: Any) -> dict[str, Any]:
        result = await self.embed_many([text])
        return {
            "model": result["model"],
            "dimensions": len(result["embeddings"][0]),
            "preview": result["embeddings"][0][:8],
        }

    async def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.chat_calls.append({"prompt": prompt, **kwargs})
        content = self.chat_replies.pop(0) if self.chat_replies else '{"rows": []}'
        return {
            "model": kwargs.get("model") or "gpt-5.6-sol",
            "content": content,
            "reasoning_effort": kwargs.get("reasoning_effort"),
        }


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Install the fake everywhere the real router was imported by name."""
    fake = FakeLLM()
    for module in (
        "backend.retrieve.match",
        "backend.retrieve.evaluate",
        "backend.retrieve.safeguards",
    ):
        monkeypatch.setattr(f"{module}.llm", fake, raising=False)
    return fake


# --------------------------------------------------------------------------
# Fake parked index
# --------------------------------------------------------------------------


@pytest.fixture
def parked_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Write a tiny Purpose/Scope index and point the loader at it.

    The real index is gitignored and rebuilt by ``make index``, so tests must
    never depend on it being present.
    """

    def build(rows: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        meta = {
            "format": index_module.INDEX_FORMAT,
            "embedding_model": "text-embedding-ada-002",
            "built_at": "2026-01-01T00:00:00+00:00",
            "rows": rows,
        }
        json_path = tmp_path / "index.json"
        npz_path = tmp_path / "index.npz"
        json_path.write_text(json.dumps(meta), encoding="utf-8")
        np.savez(npz_path, embeddings=np.asarray(vectors, dtype=np.float32))
        monkeypatch.setattr(index_module, "INDEX_JSON", json_path)
        monkeypatch.setattr(index_module, "INDEX_NPZ", npz_path)

    return build


@pytest.fixture
def summary_row():
    def build(slug: str, title: str = "", category: str = "") -> dict[str, Any]:
        return {
            "slug": slug,
            "chunk_kind": "summary",
            "chunk_id": f"{slug}:summary",
            "title": title or slug.replace("-", " ").title(),
            "category": category or "Policy",
            "text": f"Purpose: {slug} purpose. Scope: {slug} scope.",
            "pdf_sha256": "0" * 64,
        }

    return build


@pytest.fixture
def empty_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """No live catalog, so ranking falls back to the values parked in the index."""
    monkeypatch.setattr(
        "backend.retrieve.match.load_catalog",
        lambda: {"policies": []},
    )


# --------------------------------------------------------------------------
# Small builders
# --------------------------------------------------------------------------


@pytest.fixture
def make_match():
    def build(slug: str, confidence: float, **overrides: Any) -> PolicyMatch:
        payload: dict[str, Any] = {
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "category": "Policy",
            "confidence": confidence,
            "score": round(confidence / 100, 4),
            "snippet": f"{slug} snippet",
            "chunk_id": f"{slug}:summary",
            "source_url": f"https://example.test/{slug}",
            "pdf_url": f"https://example.test/{slug}.pdf",
            "pdf_path": None,
            "pdf_bytes": None,
            "published_on": None,
            "summary": f"{slug} summary",
        }
        payload.update(overrides)
        return PolicyMatch.model_validate(payload)

    return build


@pytest.fixture
def pages():
    def build(*texts: str) -> list[PageText]:
        return [PageText(page=i, text=text) for i, text in enumerate(texts, start=1)]

    return build

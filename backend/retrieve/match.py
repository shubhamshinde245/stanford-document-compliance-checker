from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from backend.llm.router import llm
from backend.models import CheckResponse, PolicyMatch
from backend.retrieve.chunk import chunk_pages
from backend.retrieve.index import inspect_index, load_parked_index
from backend.retrieve.text import ExtractError, extract_document
from backend.scraper.catalog import load_catalog

SNIPPET_CHARS = 320
SLUG_RE = re.compile(r"[^a-z0-9]+")


class IndexNotReady(RuntimeError):
    """Parked index is missing or was built with a different embedding model."""


def slug_from_filename(filename: str) -> str:
    stem = Path(filename).stem.lower()
    slug = SLUG_RE.sub("-", stem).strip("-")
    return slug or "document"


def snippet_from(text: str, limit: int = SNIPPET_CHARS) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms


def rank_policies(
    query_vectors: np.ndarray,
    index_matrix: np.ndarray,
    rows: list[dict[str, Any]],
    catalog_by_slug: dict[str, dict[str, Any]],
) -> list[PolicyMatch]:
    if query_vectors.size == 0 or index_matrix.size == 0:
        return []
    query = l2_normalize(np.asarray(query_vectors, dtype=np.float32))
    parked = l2_normalize(np.asarray(index_matrix, dtype=np.float32))
    similarities = query @ parked.T
    best_per_row = similarities.max(axis=0)

    best_by_slug: dict[str, PolicyMatch] = {}
    for index, row in enumerate(rows):
        slug = str(row.get("slug") or "")
        if not slug:
            continue
        score = float(best_per_row[index])
        current = best_by_slug.get(slug)
        if current is not None and score <= current.score:
            continue
        live = catalog_by_slug.get(slug, {})
        snippet_source = str(row.get("text") or "")
        summary = str(live.get("summary") or "") or snippet_from(snippet_source)
        pdf_bytes = live.get("pdf_bytes")
        best_by_slug[slug] = PolicyMatch(
            slug=slug,
            title=live.get("title") or str(row.get("title") or slug),
            category=live.get("category") or str(row.get("category") or ""),
            confidence=round(score * 100, 1),
            score=round(score, 4),
            snippet=snippet_from(snippet_source),
            chunk_id=str(row.get("chunk_id") or ""),
            source_url=live.get("source_url") or str(row.get("source_url") or ""),
            pdf_url=live.get("pdf_url") or str(row.get("pdf_url") or ""),
            pdf_path=live.get("pdf_path") or None,
            pdf_bytes=int(pdf_bytes) if isinstance(pdf_bytes, (int, float)) else None,
            published_on=live.get("published_on") or None,
            summary=summary,
        )
    return sorted(best_by_slug.values(), key=lambda item: item.score, reverse=True)


def _catalog_by_slug() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in load_catalog().get("policies", []):
        if not isinstance(item, dict) or not item.get("slug"):
            continue
        lookup[str(item["slug"])] = {
            "title": str(item.get("title") or ""),
            "category": str(item.get("category") or ""),
            "source_url": str(item.get("source_url") or ""),
            "pdf_url": str(item.get("pdf_url") or ""),
            "pdf_path": str(item.get("pdf_path") or "") or None,
            "summary": str(item.get("summary") or ""),
            "published_on": str(item.get("published_on") or "") or None,
            "pdf_bytes": item.get("pdf_bytes"),
        }
    return lookup


async def check_upload(filename: str, data: bytes) -> CheckResponse:
    status = inspect_index()
    if not status.ready:
        raise IndexNotReady(status.message)

    try:
        pages = extract_document(filename, data)
    except ExtractError:
        raise

    chunks = chunk_pages(pages, slug_from_filename(filename))
    if not chunks:
        raise ExtractError("Could not extract text from the document.")

    result = await llm.embed_many([chunk.text for chunk in chunks])
    query = np.asarray(result["embeddings"], dtype=np.float32)

    meta, matrix = load_parked_index()
    rows = meta.get("rows") if isinstance(meta.get("rows"), list) else []
    summary_rows: list[dict[str, Any]] = []
    summary_vectors: list[np.ndarray] = []
    for index, row in enumerate(rows):
        if isinstance(row, dict) and str(row.get("chunk_kind") or "") == "summary":
            summary_rows.append(row)
            summary_vectors.append(matrix[index])
    if not summary_rows:
        raise IndexNotReady(
            "Policy index is not Purpose/Scope summaries. Run `make index`."
        )
    parked = np.vstack(summary_vectors).astype(np.float32)
    if query.ndim != 2 or query.shape[1] != parked.shape[1]:
        raise IndexNotReady(
            "Query embeddings do not match the parked index dimensions. Run `make index`."
        )
    matches = rank_policies(
        query,
        parked,
        summary_rows,
        _catalog_by_slug(),
    )
    return CheckResponse(
        filename=filename,
        model=str(result.get("model") or status.settings_model),
        matches=matches,
    )

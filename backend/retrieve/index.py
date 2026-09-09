from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from backend.llm.router import llm
from backend.llm.store import load_settings
from backend.retrieve.sections import build_summary_text, extract_purpose_and_scope
from backend.retrieve.text import extract_document
from backend.scraper.catalog import CATALOG_DIR, PDF_DIR, load_catalog, pdf_path_for, save_catalog

INDEX_JSON = CATALOG_DIR / "index.json"
INDEX_NPZ = CATALOG_DIR / "index.npz"
INDEX_FORMAT = "summary-v1"
INDEX_LOCK = threading.Lock()


@dataclass(frozen=True)
class IndexStatus:
    exists: bool
    ready: bool
    stale_model: bool
    parked_model: str | None
    settings_model: str
    rows: int
    slugs: int
    dimensions: int | None
    built_at: str | None
    message: str


class IndexBuildError(RuntimeError):
    """Policy index could not be built."""


def inspect_index() -> IndexStatus:
    settings_model = str(load_settings()["embedding_model"])
    loaded = _read_files()
    if loaded is None:
        return IndexStatus(
            exists=False,
            ready=False,
            stale_model=False,
            parked_model=None,
            settings_model=settings_model,
            rows=0,
            slugs=0,
            dimensions=None,
            built_at=None,
            message="Policy index is not built. Run `make index`.",
        )
    meta, matrix = loaded
    parked_model = str(meta.get("embedding_model") or "")
    rows = meta.get("rows") if isinstance(meta.get("rows"), list) else []
    summaries = [row for row in rows if _is_summary_row(row)]
    stale_format = str(meta.get("format") or "") != INDEX_FORMAT or not summaries
    stale_model = parked_model != settings_model
    ready = (
        bool(summaries)
        and not stale_format
        and not stale_model
        and matrix.shape[0] == len(rows)
    )
    if stale_format:
        message = (
            "Policy index is not Purpose/Scope summaries. Run `make index`."
        )
    elif stale_model:
        message = (
            f"Policy index was built with {parked_model} but Settings uses "
            f"{settings_model}. Run `make index`."
        )
    elif not summaries:
        message = "Policy index is empty. Run `make index`."
    elif matrix.shape[0] != len(rows):
        message = "Policy index files are out of sync. Run `make index`."
        ready = False
    else:
        message = (
            f"Policy index ready: {len(summaries)} summaries, "
            f"{_slug_count(summaries)} policies, model {parked_model}."
        )
    return IndexStatus(
        exists=True,
        ready=ready,
        stale_model=stale_model,
        parked_model=parked_model or None,
        settings_model=settings_model,
        rows=len(summaries),
        slugs=_slug_count(summaries),
        dimensions=int(meta["dimensions"]) if meta.get("dimensions") else None,
        built_at=str(meta.get("built_at") or "") or None,
        message=message,
    )


def describe_index() -> str:
    return inspect_index().message


def load_parked_index() -> tuple[dict[str, Any], np.ndarray]:
    loaded = _read_files()
    if loaded is None:
        raise FileNotFoundError("Policy index is not built. Run `make index`.")
    return loaded


def pdf_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def upsert_summary_chunk_sync(item: dict[str, Any], path: Path) -> dict[str, Any]:
    """Sync wrapper for scrape (Playwright loop has no running asyncio loop)."""
    return asyncio.run(upsert_summary_chunk(item, path))


async def upsert_summary_chunk(item: dict[str, Any], path: Path) -> dict[str, Any]:
    """Embed Purpose/Scope for one policy and park it. Never called from /api/check."""
    slug = str(item.get("slug") or "")
    if not slug:
        raise IndexBuildError("Policy slug is missing.")
    sha = pdf_sha256(path)
    settings_model = str(load_settings()["embedding_model"])

    with INDEX_LOCK:
        parked = _read_files()
        if parked is not None:
            meta, matrix = parked
            if _current_summary_index(meta, matrix, settings_model):
                for row in meta.get("rows") or []:
                    if (
                        _is_summary_row(row)
                        and str(row.get("slug")) == slug
                        and str(row.get("pdf_sha256") or "") == sha
                    ):
                        return {
                            "purpose": str(row.get("purpose") or ""),
                            "scope": str(row.get("scope") or ""),
                            "chunk_id": str(row.get("chunk_id") or f"{slug}:summary"),
                            "skipped": True,
                        }

    pages = extract_document(path.name, path.read_bytes())
    sections = extract_purpose_and_scope(pages)
    title = str(item.get("title") or slug)
    category = str(item.get("category") or "")
    text = build_summary_text(
        title=title,
        category=category,
        purpose=sections.purpose,
        scope=sections.scope,
    )
    if not text.strip():
        raise IndexBuildError(f"No Purpose/Scope text for {slug}.")
    result = await llm.embed(text)
    model_name = str(result.get("model") or settings_model)
    vector = np.asarray(result["embedding"], dtype=np.float32)
    row = _summary_row(
        item,
        sections.purpose,
        sections.scope,
        text,
        sections.page,
        sha,
        model_name,
    )

    with INDEX_LOCK:
        _merge_write(
            settings_model=settings_model,
            replace_slugs={slug},
            new_rows=[row],
            new_vectors=[vector],
            model_name=model_name,
            dimensions=int(result.get("dimensions") or vector.shape[0]),
        )
    return {
        "purpose": sections.purpose,
        "scope": sections.scope,
        "chunk_id": row["chunk_id"],
        "skipped": False,
    }


async def ensure_index(*, force: bool = False) -> IndexStatus:
    """Rebuild missing or stale summary slugs. Never called from POST /api/check."""
    catalog = load_catalog()
    policies = [
        item
        for item in catalog.get("policies", [])
        if isinstance(item, dict) and item.get("slug")
    ]
    available = [
        (item, path)
        for item, path in ((item, _pdf_for(item)) for item in policies)
        if path is not None
    ]
    if not available:
        raise IndexBuildError("No policy PDFs found. Run `make scrape` first.")

    settings_model = str(load_settings()["embedding_model"])
    with INDEX_LOCK:
        stale_jobs = _stale_jobs(available, settings_model, force=force)

    if not stale_jobs:
        print(
            f"Policy index already up to date: {inspect_index().message}"
        )
        return inspect_index()

    print(
        f"Embedding {len(stale_jobs)} Purpose/Scope summaries with "
        f"{settings_model}…"
    )
    new_rows: list[dict[str, Any]] = []
    new_vectors: list[np.ndarray] = []
    model_name = settings_model
    dimensions = 0
    rebuilt: set[str] = set()

    for item, path, sha in stale_jobs:
        slug = str(item["slug"])
        try:
            pages = extract_document(path.name, path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {slug}: {exc}")
            continue
        sections = extract_purpose_and_scope(pages)
        title = str(item.get("title") or slug)
        category = str(item.get("category") or "")
        text = build_summary_text(
            title=title,
            category=category,
            purpose=sections.purpose,
            scope=sections.scope,
        )
        if not text.strip():
            print(f"  skip {slug}: no extractable text")
            continue
        try:
            result = await llm.embed(text)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {slug}: {exc}")
            continue
        model_name = str(result.get("model") or settings_model)
        dimensions = int(result.get("dimensions") or 0)
        new_rows.append(
            _summary_row(
                item,
                sections.purpose,
                sections.scope,
                text,
                sections.page,
                sha,
                model_name,
            )
        )
        new_vectors.append(np.asarray(result["embedding"], dtype=np.float32))
        rebuilt.add(slug)
        note = " (first-page fallback)" if sections.fallback else ""
        print(f"  {slug}: summary chunk{note}")

    if not new_rows and not inspect_index().ready:
        raise IndexBuildError("No policy summaries could be indexed.")
    if not new_rows:
        return inspect_index()

    with INDEX_LOCK:
        _merge_write(
            settings_model=settings_model,
            replace_slugs=rebuilt,
            new_rows=new_rows,
            new_vectors=new_vectors,
            model_name=model_name,
            dimensions=dimensions,
        )
    return inspect_index()


def _stale_jobs(
    available: list[tuple[dict[str, Any], Path]],
    settings_model: str,
    *,
    force: bool,
) -> list[tuple[dict[str, Any], Path, str]]:
    parked = _read_files()
    keep_slugs: set[str] = set()
    if parked is not None and not force:
        meta, matrix = parked
        rows = meta.get("rows") if isinstance(meta.get("rows"), list) else []
        if _current_summary_index(meta, matrix, settings_model):
            by_slug = _rows_by_slug(rows, matrix)
            for item, path in available:
                slug = str(item["slug"])
                sha = pdf_sha256(path)
                existing = [
                    row
                    for row, _vector in by_slug.get(slug, [])
                    if _is_summary_row(row)
                ]
                if existing and str(existing[0].get("pdf_sha256") or "") == sha:
                    keep_slugs.add(slug)
    jobs: list[tuple[dict[str, Any], Path, str]] = []
    for item, path in available:
        slug = str(item["slug"])
        if slug in keep_slugs:
            continue
        jobs.append((item, path, pdf_sha256(path)))
    return jobs


def _merge_write(
    *,
    settings_model: str,
    replace_slugs: set[str],
    new_rows: list[dict[str, Any]],
    new_vectors: list[np.ndarray],
    model_name: str,
    dimensions: int,
) -> None:
    if not new_rows:
        return
    parked = _read_files()
    keep_rows: list[dict[str, Any]] = []
    keep_vectors: list[np.ndarray] = []
    if parked is not None:
        meta, matrix = parked
        rows = meta.get("rows") if isinstance(meta.get("rows"), list) else []
        if _current_summary_index(meta, matrix, settings_model):
            for index, row in enumerate(rows):
                if not _is_summary_row(row):
                    continue
                slug = str(row.get("slug") or "")
                if slug in replace_slugs:
                    continue
                keep_rows.append(row)
                keep_vectors.append(matrix[index])

    if keep_vectors and keep_vectors[0].shape[0] != new_vectors[0].shape[0]:
        raise IndexBuildError(
            "Parked embeddings have a different dimension than the current model. "
            "Re-run `make index` after switching models."
        )

    rows = keep_rows + new_rows
    vectors = keep_vectors + new_vectors
    matrix = np.vstack(vectors).astype(np.float32)
    if dimensions <= 0:
        dimensions = int(matrix.shape[1])
    _write_files(
        {
            "format": INDEX_FORMAT,
            "embedding_model": model_name or settings_model,
            "dimensions": dimensions,
            "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "rows": rows,
        },
        matrix,
    )
    _stamp_catalog_sections(new_rows)


def _stamp_catalog_sections(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    catalog = load_catalog()
    by_slug = {
        str(item.get("slug")): item
        for item in catalog.get("policies", [])
        if isinstance(item, dict) and item.get("slug")
    }
    changed = False
    for row in rows:
        item = by_slug.get(str(row.get("slug") or ""))
        if item is None:
            continue
        purpose = str(row.get("purpose") or "")
        scope = str(row.get("scope") or "")
        if (
            item.get("purpose") != purpose
            or item.get("scope") != scope
            or item.get("index_error")
        ):
            item["purpose"] = purpose
            item["scope"] = scope
            item["index_error"] = None
            changed = True
    if changed:
        save_catalog(catalog)


def _summary_row(
    item: dict[str, Any],
    purpose: str,
    scope: str,
    text: str,
    page: int,
    sha: str,
    model_name: str,
) -> dict[str, Any]:
    slug = str(item["slug"])
    return {
        "slug": slug,
        "title": str(item.get("title") or slug),
        "category": str(item.get("category") or ""),
        "kind": str(item.get("kind") or "Policy template"),
        "published_on": str(item.get("published_on") or "") or None,
        "source_url": str(item.get("source_url") or ""),
        "chunk_id": f"{slug}:summary",
        "chunk_kind": "summary",
        "text": text,
        "purpose": purpose,
        "scope": scope,
        "page": page,
        "pdf_sha256": sha,
        "embedding_model": model_name,
    }


def _current_summary_index(
    meta: dict[str, Any],
    matrix: np.ndarray,
    settings_model: str,
) -> bool:
    rows = meta.get("rows") if isinstance(meta.get("rows"), list) else []
    return (
        str(meta.get("format") or "") == INDEX_FORMAT
        and str(meta.get("embedding_model") or "") == settings_model
        and matrix.ndim == 2
        and matrix.shape[0] == len(rows)
        and any(_is_summary_row(row) for row in rows)
    )


def _is_summary_row(row: Any) -> bool:
    return isinstance(row, dict) and str(row.get("chunk_kind") or "") == "summary"


def _pdf_for(item: dict[str, Any]) -> Path | None:
    slug = str(item.get("slug") or "")
    relative = item.get("pdf_path")
    path = PDF_DIR / Path(str(relative)).name if relative else pdf_path_for(slug)
    if path.is_file():
        return path
    fallback = pdf_path_for(slug)
    return fallback if fallback.is_file() else None


def _rows_by_slug(
    rows: list[Any],
    matrix: np.ndarray,
) -> dict[str, list[tuple[dict[str, Any], np.ndarray]]]:
    grouped: dict[str, list[tuple[dict[str, Any], np.ndarray]]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("slug"):
            continue
        grouped.setdefault(str(row["slug"]), []).append((row, matrix[index]))
    return grouped


def _slug_count(rows: list[Any]) -> int:
    return len(
        {
            str(row.get("slug"))
            for row in rows
            if isinstance(row, dict) and row.get("slug")
        }
    )


def _read_files() -> tuple[dict[str, Any], np.ndarray] | None:
    if not INDEX_JSON.is_file() or not INDEX_NPZ.is_file():
        return None
    try:
        meta = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
        payload = np.load(INDEX_NPZ)
        matrix = np.asarray(payload["embeddings"], dtype=np.float32)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(meta, dict):
        return None
    rows = meta.get("rows")
    if not isinstance(rows, list) or matrix.ndim != 2 or matrix.shape[0] != len(rows):
        return None
    return meta, matrix


def _write_files(meta: dict[str, Any], matrix: np.ndarray) -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp_json = INDEX_JSON.with_name("index.json.tmp")
    tmp_npz = INDEX_NPZ.with_name("index.tmp.npz")
    tmp_json.write_text(
        json.dumps(meta, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with tmp_npz.open("wb") as handle:
        np.savez(handle, embeddings=np.asarray(matrix, dtype=np.float32))
    tmp_json.replace(INDEX_JSON)
    tmp_npz.replace(INDEX_NPZ)

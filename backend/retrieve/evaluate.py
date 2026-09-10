from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import numpy as np

from backend.llm.router import llm
from backend.llm.schema import VERDICTS, build_system_prompt, compile_json_schema
from backend.llm.store import load_settings
from backend.models import (
    EvaluateCounts,
    EvaluateFinding,
    EvaluateResponse,
    EvaluateSource,
)
from backend.retrieve.chunk import Chunk
from backend.retrieve.match import IndexNotReady, _catalog_by_slug, l2_normalize
from backend.retrieve.safeguards import load_safeguards
from backend.retrieve.session import RankedCheck, get_check

EVAL_MODEL = "gpt-5.6-sol"
EVAL_EFFORT = "high"
TOP_K_CHUNKS = 3
BATCH_SIZE = 6
BATCH_CONCURRENCY = 2
MAX_TOKENS = 8192
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)
VERDICT_SET = set(VERDICTS)


class EvaluateError(RuntimeError):
    """The requirement evaluation could not run."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def quote_in_text(quote: str, text: str) -> bool:
    raw = quote.strip()
    if not raw:
        return False
    if raw in text:
        return True
    collapsed_quote = " ".join(raw.split())
    collapsed_text = " ".join(text.split())
    return collapsed_quote in collapsed_text


async def evaluate_upload(
    filename: str,
    data: bytes,
    slug: str,
    check_id: str | None,
) -> EvaluateResponse:
    session = await _session_for(filename, data, check_id)
    if not session.matched:
        raise EvaluateError(
            "No standard in the library matches this document.",
            status_code=409,
        )

    live = _catalog_by_slug().get(slug) or {}
    match = next((item for item in session.matches if item.slug == slug), None)
    if match is None and not live:
        raise EvaluateError("Policy not found in the library.", status_code=404)

    safeguards = load_safeguards(slug)
    if not safeguards:
        raise EvaluateError(
            "No extracted requirements for this policy. Run make index after a scrape.",
            status_code=404,
        )

    requirements = [
        {
            "requirement_id": str(row.get("category") or f"REQ-{index}").strip()
            or f"REQ-{index}",
            "definition": str(row.get("definition") or "").strip(),
        }
        for index, row in enumerate(safeguards, start=1)
    ]
    retrieved = await _retrieve_chunks(session, requirements)
    findings = await _judge_batches(requirements, retrieved)
    counts = _counts(findings)
    total = len(findings) or 1
    title = (match.title if match else "") or str(live.get("title") or slug)
    return EvaluateResponse(
        slug=slug,
        title=title,
        category=(match.category if match else "") or str(live.get("category") or ""),
        source_url=(match.source_url if match else "")
        or str(live.get("source_url") or ""),
        pdf_url=(match.pdf_url if match else "") or str(live.get("pdf_url") or ""),
        model=EVAL_MODEL,
        reasoning_effort=EVAL_EFFORT,
        score=round(100.0 * counts.aligned / total, 1),
        counts=counts,
        rows=findings,
    )


async def _session_for(
    filename: str, data: bytes, check_id: str | None
) -> RankedCheck:
    cached = get_check(check_id)
    if cached is not None:
        return cached
    from backend.retrieve.match import check_upload

    ranked = await check_upload(filename, data)
    restored = get_check(ranked.check_id)
    if restored is None:
        raise IndexNotReady("Could not rebuild the ranked check session.")
    return restored


async def _retrieve_chunks(
    session: RankedCheck, requirements: list[dict[str, str]]
) -> dict[str, list[Chunk]]:
    texts = [item["definition"] or item["requirement_id"] for item in requirements]
    result = await llm.embed_many(texts)
    req_vectors = l2_normalize(
        np.asarray(result["embeddings"], dtype=np.float32)
    )
    doc_vectors = l2_normalize(np.asarray(session.embeddings, dtype=np.float32))
    similarities = req_vectors @ doc_vectors.T
    by_id: dict[str, list[Chunk]] = {}
    for index, item in enumerate(requirements):
        order = np.argsort(similarities[index])[::-1]
        picked: list[Chunk] = []
        seen: set[str] = set()
        for rank in order:
            chunk = session.chunks[int(rank)]
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            picked.append(chunk)
            if len(picked) >= TOP_K_CHUNKS:
                break
        by_id[item["requirement_id"]] = picked
    return by_id


async def _judge_batches(
    requirements: list[dict[str, str]],
    retrieved: dict[str, list[Chunk]],
) -> list[EvaluateFinding]:
    columns = load_settings()["output_columns"]
    system = build_system_prompt(columns)
    schema = compile_json_schema(columns)
    batches = [
        requirements[start : start + BATCH_SIZE]
        for start in range(0, len(requirements), BATCH_SIZE)
    ]
    lock = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def judge_batch(batch: list[dict[str, str]]) -> list[EvaluateFinding]:
        async with lock:
            prompt = _batch_prompt(batch, retrieved)
            result = await llm.chat(
                prompt,
                model=EVAL_MODEL,
                reasoning_effort=EVAL_EFFORT,
                json_schema=schema,
                system=system,
                max_tokens=MAX_TOKENS,
            )
        parsed = _parse_rows(str(result.get("content") or ""))
        by_id = {
            str(row.get("requirement_id") or "").strip(): row
            for row in parsed
            if str(row.get("requirement_id") or "").strip()
        }
        return [
            _normalize_finding(
                item,
                by_id.get(item["requirement_id"]),
                retrieved.get(item["requirement_id"]) or [],
            )
            for item in batch
        ]

    parts = await asyncio.gather(*(judge_batch(batch) for batch in batches))
    return [finding for part in parts for finding in part]


def _batch_prompt(
    batch: list[dict[str, str]], retrieved: dict[str, list[Chunk]]
) -> str:
    lines = [
        "Judge every requirement below. Return one row per requirement_id, "
        "using the ids exactly as written.",
        "",
        "Requirements:",
    ]
    used: list[Chunk] = []
    seen: set[str] = set()
    for item in batch:
        lines.append(f"- requirement_id: {item['requirement_id']}")
        lines.append(f"  definition: {item['definition']}")
        lines.append("")
        for chunk in retrieved.get(item["requirement_id"]) or []:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            used.append(chunk)
    lines.append("Retrieved chunks from the uploaded procedure:")
    lines.append("")
    for chunk in used:
        lines.append(f"### {chunk.chunk_id}")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines)


def _parse_rows(content: str) -> list[dict[str, Any]]:
    text = content.strip()
    fenced = JSON_FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _normalize_finding(
    requirement: dict[str, str],
    row: dict[str, Any] | None,
    allowed: list[Chunk],
) -> EvaluateFinding:
    allowed_ids = {chunk.chunk_id for chunk in allowed}
    allowed_text = {chunk.chunk_id: chunk.text for chunk in allowed}
    req_id = requirement["requirement_id"]
    definition = requirement["definition"]
    if row is None:
        return EvaluateFinding(
            requirement_id=req_id,
            definition=definition,
            verdict="missing",
            requirement_quote=definition,
            evidence_quote="",
            rationale="The model did not return a row for this requirement.",
        )

    verdict = str(row.get("verdict") or "flagged").strip().lower()
    if verdict not in VERDICT_SET:
        verdict = "flagged"
    requirement_quote = str(row.get("requirement_quote") or "").strip() or definition
    evidence_quote = str(row.get("evidence_quote") or "").strip()
    rationale = str(row.get("rationale") or "").strip()
    sources = _parse_sources(row.get("sources"), allowed_ids)

    evidence_ok = any(
        quote_in_text(evidence_quote, text) for text in allowed_text.values()
    )
    if verdict in {"aligned", "contradicted"} and not evidence_ok:
        verdict = "flagged"
        if not rationale:
            rationale = (
                "Quoted evidence was not found in the retrieved chunks, so this "
                "row was flagged for review."
            )
    if verdict == "missing":
        evidence_quote = evidence_quote if evidence_ok else ""
        sources = [] if not evidence_ok else sources
        if not rationale:
            rationale = "No supporting passage was found in the uploaded document."

    unknown_sources = [
        source
        for source in _raw_sources(row.get("sources"))
        if source["chunk_id"] not in allowed_ids
    ]
    if unknown_sources and verdict in {"aligned", "contradicted"}:
        verdict = "flagged"

    return EvaluateFinding(
        requirement_id=req_id,
        definition=definition,
        verdict=verdict,  # type: ignore[arg-type]
        requirement_quote=requirement_quote,
        evidence_quote=evidence_quote,
        rationale=rationale,
        sources=sources,
    )


def _raw_sources(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        rows.append(
            {
                "chunk_id": chunk_id,
                "quote": str(item.get("quote") or "").strip(),
            }
        )
    return rows


def _parse_sources(value: Any, allowed_ids: set[str]) -> list[EvaluateSource]:
    return [
        EvaluateSource(chunk_id=item["chunk_id"], quote=item["quote"])
        for item in _raw_sources(value)
        if item["chunk_id"] in allowed_ids
    ]


def _counts(findings: list[EvaluateFinding]) -> EvaluateCounts:
    counts = EvaluateCounts()
    for row in findings:
        current = getattr(counts, row.verdict, None)
        if isinstance(current, int):
            setattr(counts, row.verdict, current + 1)
    return counts

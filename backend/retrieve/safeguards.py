from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from backend.llm.router import llm
from backend.retrieve.sections import extract_safeguards_section
from backend.retrieve.text import PageText
from backend.scraper.catalog import CATALOG_DIR, load_catalog, save_catalog

SAFEGUARDS_DIR = CATALOG_DIR / "safeguards"
CSV_FIELDS = ("slug", "title", "pdf_sha256", "category", "definition")
SAFEGUARD_MODEL = "gpt-5.6-sol"
SAFEGUARD_EFFORT = "low"
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)

SAFEGUARD_SCHEMA: dict[str, Any] = {
    "name": "policy_safeguards",
    "schema": {
        "type": "object",
        "properties": {
            "safeguards": {
                "type": "array",
                "description": "Every distinct safeguard or control stated in the policy.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": (
                                "Short name of the safeguard, such as the numbered "
                                "heading or a few-word label."
                            ),
                        },
                        "definition": {
                            "type": "string",
                            "description": (
                                "What the organization must do, quoted or closely "
                                "paraphrased from the source."
                            ),
                        },
                    },
                    "required": ["category", "definition"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["safeguards"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You extract safeguards from university security policy templates. "
    "Return only safeguards that appear in the supplied text. Do not invent "
    "controls. If the text has numbered or bulleted requirements, emit one "
    "row per requirement. Category is a short label; definition is the "
    "requirement itself."
)


def csv_path_for(slug: str) -> Path:
    return SAFEGUARDS_DIR / f"{slug}.csv"


def load_safeguards(slug: str) -> list[dict[str, str]]:
    path = csv_path_for(slug)
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            category = " ".join(str(row.get("category") or "").split())
            definition = " ".join(str(row.get("definition") or "").split())
            if category or definition:
                rows.append({"category": category, "definition": definition})
    return rows


def safeguards_are_current(slug: str, sha: str) -> bool:
    path = csv_path_for(slug)
    if not path.is_file():
        return False
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        first = next(reader, None)
    if not first:
        return False
    return str(first.get("pdf_sha256") or "") == sha


async def extract_and_store_safeguards(
    item: dict[str, Any],
    pages: list[PageText],
    sha: str,
    *,
    force: bool = False,
) -> list[dict[str, str]]:
    slug = str(item.get("slug") or "")
    if not slug:
        return []
    if not force and safeguards_are_current(slug, sha):
        rows = load_safeguards(slug)
        _stamp_catalog(slug, len(rows))
        return rows

    source = extract_safeguards_section(pages)
    if not source.strip():
        _write_csv(slug, str(item.get("title") or slug), sha, [])
        _stamp_catalog(slug, 0)
        return []

    title = str(item.get("title") or slug)
    prompt = (
        f"Policy title: {title}\n"
        f"Policy slug: {slug}\n\n"
        "Extract every safeguard from this section:\n\n"
        f"{source}"
    )
    result = await llm.chat(
        prompt,
        model=SAFEGUARD_MODEL,
        reasoning_effort=SAFEGUARD_EFFORT,
        json_schema=SAFEGUARD_SCHEMA,
        system=SYSTEM_PROMPT,
        max_tokens=4096,
    )
    rows = _parse_safeguards(result.get("content") or "")
    _write_csv(slug, title, sha, rows)
    _stamp_catalog(slug, len(rows))
    return rows


def _parse_safeguards(content: str) -> list[dict[str, str]]:
    payload = _load_json(content)
    raw = payload.get("safeguards") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        category = " ".join(str(item.get("category") or "").split())
        definition = " ".join(str(item.get("definition") or "").split())
        if not category and not definition:
            continue
        key = (category.lower(), definition.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append({"category": category, "definition": definition})
    return rows


def _load_json(content: str) -> Any:
    text = content.strip()
    fenced = JSON_FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


def _write_csv(
    slug: str,
    title: str,
    sha: str,
    rows: list[dict[str, str]],
) -> Path:
    SAFEGUARDS_DIR.mkdir(parents=True, exist_ok=True)
    path = csv_path_for(slug)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "slug": slug,
                    "title": title,
                    "pdf_sha256": sha,
                    "category": row["category"],
                    "definition": row["definition"],
                }
            )
    tmp.replace(path)
    return path


def _stamp_catalog(slug: str, count: int) -> None:
    catalog = load_catalog()
    changed = False
    for item in catalog.get("policies", []):
        if not isinstance(item, dict) or item.get("slug") != slug:
            continue
        if item.get("safeguard_count") != count:
            item["safeguard_count"] = count
            changed = True
        break
    if changed:
        save_catalog(catalog)

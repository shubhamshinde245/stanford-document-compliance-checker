from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.settings import ROOT, SANS_BASE_URL

CATALOG_DIR = ROOT / "data" / "sans-policies"
CATALOG_PATH = CATALOG_DIR / "catalog.json"
PDF_DIR = CATALOG_DIR / "pdfs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_catalog(source_url: str | None = None) -> dict[str, Any]:
    return {
        "source_url": source_url or SANS_BASE_URL,
        "showing_text": "",
        "listed": 0,
        "total": 0,
        "scraped_at": "",
        "policies": [],
    }


def ensure_dirs() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        return empty_catalog()
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return empty_catalog()
    data.setdefault("policies", [])
    return data


def save_catalog(catalog: dict[str, Any]) -> Path:
    ensure_dirs()
    CATALOG_PATH.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return CATALOG_PATH


def pdf_path_for(slug: str) -> Path:
    return PDF_DIR / f"{slug}.pdf"


def relative_pdf_path(slug: str) -> str:
    return f"pdfs/{slug}.pdf"

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.settings import ROOT, SANS_BASE_URL

CATALOG_DIR = ROOT / "data" / "sans-policies"
CATALOG_PATH = CATALOG_DIR / "catalog.json"
PDF_DIR = CATALOG_DIR / "pdfs"
SCHEDULE_PATH = CATALOG_DIR / "schedule.json"
PACIFIC_TZ = "America/Los_Angeles"
DEFAULT_HOUR = 8
DEFAULT_MINUTE = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_catalog(source_url: str | None = None) -> dict[str, Any]:
    return {
        "source_url": source_url or SANS_BASE_URL,
        "showing_text": "",
        "listed": 0,
        "total": 0,
        "scraped_at": "",
        "last_check": None,
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


def default_schedule() -> dict[str, Any]:
    return {
        "enabled": True,
        "hour": DEFAULT_HOUR,
        "minute": DEFAULT_MINUTE,
        "timezone": PACIFIC_TZ,
        "last_run_at": None,
        "last_run_status": None,
        "last_run_summary": None,
    }


def load_schedule() -> dict[str, Any]:
    data = default_schedule()
    if SCHEDULE_PATH.is_file():
        with SCHEDULE_PATH.open(encoding="utf-8") as handle:
            stored = json.load(handle)
        if isinstance(stored, dict):
            data.update(stored)
    data["timezone"] = PACIFIC_TZ
    data["hour"] = int(data.get("hour", DEFAULT_HOUR))
    data["minute"] = int(data.get("minute", DEFAULT_MINUTE))
    data["enabled"] = bool(data.get("enabled", True))
    return data


def save_schedule(schedule: dict[str, Any]) -> Path:
    ensure_dirs()
    merged = default_schedule()
    merged.update(schedule)
    merged["timezone"] = PACIFIC_TZ
    SCHEDULE_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return SCHEDULE_PATH


def next_run_at(schedule: dict[str, Any] | None = None) -> str | None:
    data = schedule or load_schedule()
    if not data.get("enabled"):
        return None
    tz = ZoneInfo(str(data.get("timezone") or PACIFIC_TZ))
    hour = int(data.get("hour", DEFAULT_HOUR))
    minute = int(data.get("minute", DEFAULT_MINUTE))
    now = datetime.now(tz).replace(second=0, microsecond=0)
    candidate = now.replace(hour=hour, minute=minute)
    if candidate <= datetime.now(tz):
        candidate = candidate + timedelta(days=1)
    return candidate.replace(microsecond=0).isoformat()

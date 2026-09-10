from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from backend.models import (
    EvaluateResponse,
    PolicyMatch,
    SavedMatch,
    SavedReport,
    SavedReportSummary,
)
from backend.settings import ROOT

REPORTS_DIR = ROOT / "data" / "reports"


class ReportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def safe_report_id(report_id: str) -> str:
    try:
        return str(UUID(report_id))
    except ValueError as exc:
        raise ReportError("Invalid report id.", status_code=400) from exc


def save_report(
    *,
    filename: str,
    check_id: str,
    matches: list[PolicyMatch],
    evaluation: EvaluateResponse,
) -> SavedReport:
    ensure_dir()
    report_id = str(uuid4())
    stored = evaluation.model_copy(update={"report_id": report_id})
    payload = SavedReport(
        id=report_id,
        created_at=utc_now(),
        filename=filename,
        check_id=check_id,
        slug=stored.slug,
        title=stored.title,
        category=stored.category,
        score=stored.score,
        counts=stored.counts,
        evaluation=stored,
        matches=[
            SavedMatch(
                slug=item.slug,
                title=item.title,
                category=item.category,
                confidence=item.confidence,
            )
            for item in matches[:5]
        ],
    )
    path = REPORTS_DIR / f"{report_id}.json"
    path.write_text(
        json.dumps(payload.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def list_reports() -> list[SavedReportSummary]:
    ensure_dir()
    rows: list[SavedReportSummary] = []
    for path in REPORTS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows.append(SavedReportSummary.model_validate(data))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return sorted(rows, key=lambda item: item.created_at, reverse=True)


def load_report(report_id: str) -> SavedReport | None:
    report_id = safe_report_id(report_id)
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.is_file():
        return None
    try:
        return SavedReport.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def delete_report(report_id: str) -> bool:
    report_id = safe_report_id(report_id)
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True

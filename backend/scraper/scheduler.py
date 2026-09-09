from __future__ import annotations

import threading
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.scraper.catalog import (
    load_schedule,
    next_run_at,
    save_schedule,
    utc_now,
)

JOB_ID = "sans_policy_refresh"
_scheduler: BackgroundScheduler | None = None
_run_lock = threading.Lock()


def is_running() -> bool:
    return _run_lock.locked()


def _summary_from_catalog(catalog: dict[str, Any]) -> str:
    check = catalog.get("last_check") or {}
    return (
        f"{check.get('added', 0)} added, {check.get('updated', 0)} updated, "
        f"{check.get('unchanged', 0)} unchanged, {check.get('kept', 0)} kept"
    )


def run_refresh(incremental: bool = True) -> dict[str, Any]:
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("A policy refresh is already running.")
    try:
        from backend.scraper.sans import scrape

        catalog = scrape(incremental=incremental)
        schedule = load_schedule()
        schedule["last_run_at"] = utc_now()
        schedule["last_run_status"] = "ok"
        schedule["last_run_summary"] = _summary_from_catalog(catalog)
        save_schedule(schedule)
        threading.Thread(
            target=_rebuild_index_safe,
            name="sans-index",
            daemon=True,
        ).start()
        return catalog
    except Exception as exc:
        schedule = load_schedule()
        schedule["last_run_at"] = utc_now()
        schedule["last_run_status"] = "error"
        schedule["last_run_summary"] = str(exc)
        save_schedule(schedule)
        raise
    finally:
        _run_lock.release()


def _rebuild_index_safe() -> None:
    try:
        import asyncio

        from backend.retrieve.index import ensure_index

        status = asyncio.run(ensure_index())
        print(status.message)
    except Exception as exc:  # noqa: BLE001 — scrape must still succeed
        print(f"Policy index update failed: {exc}")


def _job() -> None:
    try:
        run_refresh(incremental=True)
    except Exception as exc:  # noqa: BLE001 — scheduled jobs must not crash the app
        print(f"Scheduled SANS refresh failed: {exc}")


def apply_schedule() -> None:
    if _scheduler is None:
        return
    schedule = load_schedule()
    if _scheduler.get_job(JOB_ID):
        _scheduler.remove_job(JOB_ID)
    if not schedule.get("enabled"):
        return
    _scheduler.add_job(
        _job,
        CronTrigger(
            hour=int(schedule["hour"]),
            minute=int(schedule["minute"]),
            timezone=schedule["timezone"],
        ),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    from backend.scraper.catalog import SCHEDULE_PATH, default_schedule, save_schedule

    if not SCHEDULE_PATH.is_file():
        save_schedule(default_schedule())
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    apply_schedule()
    nxt = next_run_at()
    print(f"SANS policy scheduler started. Next run: {nxt or 'disabled'}")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None

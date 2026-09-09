from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.checks import RULES, check_html
from backend.models import (
    CheckRequest,
    CheckResponse,
    HealthResponse,
    PolicyCatalog,
    PolicySchedule,
    PolicyScheduleUpdate,
    RuleInfo,
)
from backend.scraper.catalog import (
    PDF_DIR,
    load_catalog,
    load_schedule,
    next_run_at,
    pdf_path_for,
    save_schedule,
)
from backend.scraper.scheduler import (
    apply_schedule,
    is_running,
    run_refresh,
    start_scheduler,
    stop_scheduler,
)
from backend.settings import AI_GATEWAY_API_KEY


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Stanford Document Compliance Checker",
    version="0.1.0",
    description="Checks HTML documents against Stanford accessibility and identity rules.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _schedule_response() -> PolicySchedule:
    data = load_schedule()
    data["next_run_at"] = next_run_at(data)
    data["running"] = is_running()
    return PolicySchedule.model_validate(data)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="stanford-document-compliance-checker",
        ai_gateway="configured" if AI_GATEWAY_API_KEY else "missing",
    )


@app.get("/api/rules", response_model=list[RuleInfo])
def list_rules() -> list[RuleInfo]:
    return RULES


@app.post("/api/check", response_model=CheckResponse)
def check_document(payload: CheckRequest) -> CheckResponse:
    html = payload.html.strip()
    if not html:
        raise HTTPException(status_code=400, detail="HTML document is empty.")
    return check_html(html, payload.filename)


@app.get("/api/policies", response_model=PolicyCatalog)
def list_policies() -> PolicyCatalog:
    return PolicyCatalog.model_validate(load_catalog())


@app.get("/api/policies/schedule", response_model=PolicySchedule)
def get_policy_schedule() -> PolicySchedule:
    return _schedule_response()


@app.put("/api/policies/schedule", response_model=PolicySchedule)
def update_policy_schedule(payload: PolicyScheduleUpdate) -> PolicySchedule:
    current = load_schedule()
    current["enabled"] = payload.enabled
    current["hour"] = payload.hour
    current["minute"] = payload.minute
    save_schedule(current)
    apply_schedule()
    return _schedule_response()


@app.post("/api/policies/scrape", response_model=PolicyCatalog)
async def scrape_policies() -> PolicyCatalog:
    if is_running():
        raise HTTPException(
            status_code=409,
            detail="A policy refresh is already running.",
        )
    try:
        catalog = await asyncio.to_thread(run_refresh, True)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PolicyCatalog.model_validate(catalog)


@app.get("/api/policies/{slug}/pdf")
def policy_pdf(slug: str) -> FileResponse:
    if "/" in slug or "\\" in slug or ".." in slug:
        raise HTTPException(status_code=400, detail="Invalid policy slug.")
    catalog = load_catalog()
    record = next(
        (item for item in catalog.get("policies", []) if item.get("slug") == slug),
        None,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Policy not found.")
    relative = record.get("pdf_path")
    path = PDF_DIR / Path(str(relative)).name if relative else pdf_path_for(slug)
    if not path.is_file():
        path = pdf_path_for(slug)
    if not path.is_file():
        detail = record.get("error") or "PDF is not available for this policy."
        raise HTTPException(status_code=404, detail=detail)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{slug}.pdf",
    )

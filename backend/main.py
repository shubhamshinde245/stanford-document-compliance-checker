from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.checks import RULES, check_html
from backend.models import (
    CheckRequest,
    CheckResponse,
    HealthResponse,
    PolicyCatalog,
    RuleInfo,
)
from backend.scraper.catalog import PDF_DIR, load_catalog, pdf_path_for
from backend.settings import AI_GATEWAY_API_KEY

app = FastAPI(
    title="Stanford Document Compliance Checker",
    version="0.1.0",
    description="Checks HTML documents against Stanford accessibility and identity rules.",
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

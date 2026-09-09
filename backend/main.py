from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.checks import RULES, check_html
from backend.models import CheckRequest, CheckResponse, HealthResponse, RuleInfo
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

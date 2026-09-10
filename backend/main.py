from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.llm.providers import LLMError, configured_providers
from backend.llm.router import llm
from backend.llm.store import LLMConfigError, save_settings
from backend.models import (
    CheckResponse,
    EvaluateResponse,
    HealthResponse,
    LLMChatRequest,
    LLMChatResponse,
    LLMEmbedRequest,
    LLMEmbedResponse,
    LLMModelInfo,
    LLMProviderStatus,
    LLMSettings,
    LLMSettingsUpdate,
    OutputColumn,
    OutputSchemaPreview,
    PolicyCatalog,
    PolicySafeguardsResponse,
    PolicySchedule,
    PolicyScheduleUpdate,
)
from backend.retrieve import IndexNotReady, check_upload, describe_index
from backend.retrieve.evaluate import EvaluateError, evaluate_upload
from backend.retrieve.safeguards import load_safeguards
from backend.retrieve.text import ExtractError, SUPPORTED_SUFFIXES
from backend.llm.schema import (
    LOCKED_NAMES,
    VERDICTS,
    build_system_prompt,
    compile_json_schema,
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


MAX_UPLOAD_BYTES = 12 * 1024 * 1024


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    print(describe_index())
    yield
    stop_scheduler()


app = FastAPI(
    title="Stanford Document Compliance Checker",
    version="0.1.0",
    description="Ranks uploaded procedures against parked SANS policy embeddings.",
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


def _llm_http_error(exc: LLMError | LLMConfigError) -> HTTPException:
    status = getattr(exc, "status_code", 400)
    return HTTPException(status_code=status, detail=str(exc))


def _settings_response() -> LLMSettings:
    data = llm.settings()
    return LLMSettings(
        provider=data["provider"],
        chat_model=data["chat_model"],
        embedding_model=data["embedding_model"],
        reasoning_effort=data["reasoning_effort"],
        output_columns=[
            OutputColumn.model_validate(item) for item in data["output_columns"]
        ],
        locked_columns=sorted(LOCKED_NAMES),
        configured=LLMProviderStatus.model_validate(data["configured"]),
    )


def _require_provider_key(provider: str) -> None:
    configured = configured_providers()
    if provider == "stanford" and not configured["stanford"]:
        raise HTTPException(
            status_code=503,
            detail="Stanford Gateway is not configured. Add AI_GATEWAY_API_KEY.",
        )
    if provider == "openai" and not configured["openai"]:
        raise HTTPException(
            status_code=400,
            detail="OpenAI is not configured. Add OPENAI_API_KEY on the server.",
        )
    if provider == "anthropic" and not configured["anthropic"]:
        raise HTTPException(
            status_code=400,
            detail="Anthropic is not configured. Add ANTHROPIC_API_KEY on the server.",
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


@app.post("/api/check", response_model=CheckResponse)
async def check_document(file: UploadFile = File(...)) -> CheckResponse:
    filename = Path(file.filename or "document").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, DOCX, HTML, Markdown, or text file.",
        )
    length = file.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 12 MB.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 12 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return await check_upload(filename, data)
    except IndexNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as extra:
        raise _llm_http_error(extra) from extra


@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate_document(
    file: UploadFile = File(...),
    slug: str = Form(...),
    check_id: str | None = Form(None),
) -> EvaluateResponse:
    filename = Path(file.filename or "document").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, DOCX, HTML, Markdown, or text file.",
        )
    if "/" in slug or "\\" in slug or ".." in slug:
        raise HTTPException(status_code=400, detail="Invalid policy slug.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 12 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return await evaluate_upload(filename, data, slug, check_id)
    except EvaluateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except IndexNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as extra:
        raise _llm_http_error(extra) from extra


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


@app.get("/api/policies/{slug}/safeguards", response_model=PolicySafeguardsResponse)
def policy_safeguards(slug: str) -> PolicySafeguardsResponse:
    if "/" in slug or "\\" in slug or ".." in slug:
        raise HTTPException(status_code=400, detail="Invalid policy slug.")
    catalog = load_catalog()
    record = next(
        (item for item in catalog.get("policies", []) if item.get("slug") == slug),
        None,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Policy not found.")
    return PolicySafeguardsResponse(
        slug=slug,
        title=str(record.get("title") or slug),
        safeguards=load_safeguards(slug),
    )


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


@app.get("/api/llm/settings", response_model=LLMSettings)
def get_llm_settings() -> LLMSettings:
    return _settings_response()


@app.put("/api/llm/settings", response_model=LLMSettings)
def update_llm_settings(payload: LLMSettingsUpdate) -> LLMSettings:
    _require_provider_key(payload.provider)
    try:
        save_settings(payload.model_dump())
    except LLMConfigError as exc:
        raise _llm_http_error(exc) from exc
    return _settings_response()


@app.get("/api/llm/output-schema", response_model=OutputSchemaPreview)
def get_output_schema() -> OutputSchemaPreview:
    """The exact prompt and json_schema every verdict call is sent with."""
    columns = llm.settings()["output_columns"]
    return OutputSchemaPreview(
        system_prompt=build_system_prompt(columns),
        json_schema=compile_json_schema(columns),
        verdicts=list(VERDICTS),
    )


@app.get("/api/llm/models", response_model=list[LLMModelInfo])
async def list_llm_models() -> list[LLMModelInfo]:
    try:
        models = await llm.list_models()
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    return [LLMModelInfo.model_validate(item) for item in models]


@app.post("/api/llm/chat", response_model=LLMChatResponse)
async def test_llm_chat(payload: LLMChatRequest) -> LLMChatResponse:
    try:
        result = await llm.chat(
            payload.prompt,
            model=payload.model,
            reasoning_effort=payload.reasoning_effort,
        )
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    return LLMChatResponse.model_validate(result)


@app.post("/api/llm/embeddings", response_model=LLMEmbedResponse)
async def test_llm_embeddings(payload: LLMEmbedRequest) -> LLMEmbedResponse:
    try:
        result = await llm.embed(payload.input, model=payload.model)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    return LLMEmbedResponse.model_validate(result)

from typing import Literal

from pydantic import BaseModel, Field


class PolicyMatch(BaseModel):
    slug: str
    title: str
    category: str = ""
    confidence: float
    score: float
    snippet: str
    chunk_id: str


class CheckResponse(BaseModel):
    filename: str
    model: str
    matches: list[PolicyMatch]


class HealthResponse(BaseModel):
    status: str
    service: str
    ai_gateway: str


class PolicyRecord(BaseModel):
    slug: str
    title: str
    category: str = ""
    kind: str = "Policy template"
    published_on: str | None = None
    source_url: str
    pdf_path: str | None = None
    pdf_bytes: int | None = None
    summary: str = ""
    purpose: str = ""
    scope: str = ""
    scraped_at: str = ""
    error: str | None = None
    index_error: str | None = None
    refresh_status: str | None = None
    previous_published_on: str | None = None


class ScrapeCheck(BaseModel):
    checked_at: str = ""
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    kept: int = 0
    failed: int = 0


class PolicyCatalog(BaseModel):
    source_url: str
    showing_text: str = ""
    listed: int = 0
    total: int = 0
    scraped_at: str = ""
    last_check: ScrapeCheck | None = None
    policies: list[PolicyRecord] = Field(default_factory=list)


class PolicySchedule(BaseModel):
    enabled: bool = True
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    timezone: str = "America/Los_Angeles"
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_summary: str | None = None
    next_run_at: str | None = None
    running: bool = False


class PolicyScheduleUpdate(BaseModel):
    enabled: bool = True
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)


LLMProvider = Literal["stanford", "openai", "anthropic"]
LLMEffort = Literal["none", "low", "medium", "high"]
LLMModelKind = Literal["chat", "embedding", "other"]


class LLMModelInfo(BaseModel):
    id: str
    kind: LLMModelKind
    owned_by: str = ""


class LLMProviderStatus(BaseModel):
    stanford: bool = False
    openai: bool = False
    anthropic: bool = False
    ollama: bool = False


class OutputColumn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=600)


class LLMSettings(BaseModel):
    provider: LLMProvider
    chat_model: str
    embedding_model: str
    reasoning_effort: LLMEffort
    output_columns: list[OutputColumn] = Field(default_factory=list)
    locked_columns: list[str] = Field(default_factory=list)
    configured: LLMProviderStatus


class LLMSettingsUpdate(BaseModel):
    provider: LLMProvider
    chat_model: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    reasoning_effort: LLMEffort
    output_columns: list[OutputColumn] | None = None


class OutputSchemaPreview(BaseModel):
    system_prompt: str
    json_schema: dict
    verdicts: list[str]


class LLMChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    reasoning_effort: LLMEffort | None = None


class LLMChatResponse(BaseModel):
    model: str
    content: str
    reasoning_effort: LLMEffort | None = None


class LLMEmbedRequest(BaseModel):
    input: str = Field(min_length=1)
    model: str | None = None


class LLMEmbedResponse(BaseModel):
    model: str
    dimensions: int
    preview: list[float]

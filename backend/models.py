from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["pass", "fail", "warn"]


class Finding(BaseModel):
    id: str
    title: str
    severity: Severity
    message: str
    details: str | None = None


class CheckSummary(BaseModel):
    passed: int
    failed: int
    warnings: int
    score: int = Field(ge=0, le=100)


class CheckRequest(BaseModel):
    html: str = Field(min_length=1)
    filename: str = "document.html"


class CheckResponse(BaseModel):
    filename: str
    summary: CheckSummary
    findings: list[Finding]


class RuleInfo(BaseModel):
    id: str
    title: str
    description: str


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
    scraped_at: str = ""
    error: str | None = None
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

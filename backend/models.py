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

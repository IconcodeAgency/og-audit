from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Finding(BaseModel):
    code: str
    severity: Severity
    category: str
    title: str
    message: str
    value: str | int | bool | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class RedirectHop(BaseModel):
    status_code: int
    source: str
    target: str


class PageMetadata(BaseModel):
    title: str | None = None
    description: str | None = None
    canonical: str | None = None
    robots: list[str] = Field(default_factory=list)
    open_graph: dict[str, list[str]] = Field(default_factory=dict)
    twitter: dict[str, list[str]] = Field(default_factory=dict)
    json_ld_types: list[str] = Field(default_factory=list)
    language: str | None = None
    h1: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    tool_version: str = "0.1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requested_url: str
    final_url: str
    status_code: int
    redirects: list[RedirectHop] = Field(default_factory=list)
    metadata: PageMetadata
    findings: list[Finding]
    resources: dict[str, Any] = Field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        return {
            severity.value: sum(item.severity == severity for item in self.findings)
            for severity in Severity
        }

    @property
    def score(self) -> int:
        deduction = self.counts["error"] * 15 + self.counts["warning"] * 5
        return max(0, 100 - deduction)

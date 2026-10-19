"""Pydantic request/response models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import Role, RootCause, Severity, Status, TestStage


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    full_name: str
    role: Role


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DefectCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(default="", max_length=10_000)
    severity: Severity
    product: str = Field(min_length=1, max_length=64)
    component: str = Field(min_length=1, max_length=64)
    failure_mode: str = Field(min_length=1, max_length=128)
    found_in: TestStage
    assignee: str | None = None


class DefectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    severity: Severity | None = None
    component: str | None = Field(default=None, min_length=1, max_length=64)
    failure_mode: str | None = Field(default=None, min_length=1, max_length=128)
    assignee: str | None = None
    root_cause_category: RootCause | None = None
    root_cause: str | None = Field(default=None, max_length=10_000)
    verification_notes: str | None = Field(default=None, max_length=10_000)


class ActionCreate(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    owner: str
    due_date: date | None = None


class ActionOut(BaseModel):
    id: int
    description: str
    owner: str
    due_date: date | None
    done: bool
    completed_at: datetime | None


class EventOut(BaseModel):
    action: str
    actor: str
    from_status: str | None
    to_status: str | None
    details: str
    at: datetime


class DefectOut(BaseModel):
    key: str
    title: str
    description: str
    severity: Severity
    status: Status
    product: str
    component: str
    failure_mode: str
    found_in: TestStage
    reporter: str
    assignee: str | None
    root_cause_category: RootCause | None
    root_cause: str
    verification_notes: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    actions: list[ActionOut]


class DefectSummary(BaseModel):
    key: str
    title: str
    severity: Severity
    status: Status
    product: str
    failure_mode: str
    assignee: str | None
    created_at: datetime
    age_days: int


class DefectPage(BaseModel):
    items: list[DefectSummary]
    total: int
    page: int
    page_size: int


class TransitionIn(BaseModel):
    to: Status
    reason: str = Field(default="", max_length=2000)


class TransitionOption(BaseModel):
    to: Status
    allowed: bool
    problems: list[str]


class Metrics(BaseModel):
    total: int
    open: int
    by_status: dict[str, int]
    open_by_severity: dict[str, int]
    pareto: list[dict]
    root_causes: dict[str, int]
    aging: dict[str, int]
    mean_days_to_close: float | None
    weekly: list[dict]

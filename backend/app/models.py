"""SQLAlchemy models."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes; they were stored as UTC
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    viewer = "viewer"
    engineer = "engineer"
    lead = "lead"
    admin = "admin"

    @property
    def rank(self) -> int:
        return list(Role).index(self)


class Status(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    root_cause_identified = "root_cause_identified"
    corrective_action = "corrective_action"
    verification = "verification"
    closed = "closed"
    rejected = "rejected"


class Severity(str, enum.Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


class TestStage(str, enum.Enum):
    __test__ = False  # not a pytest class

    unit = "unit"
    integration = "integration"
    system = "system"
    acceptance = "acceptance"
    field = "field"


class RootCause(str, enum.Enum):
    design = "design"
    software = "software"
    material = "material"
    workmanship = "workmanship"
    test_equipment = "test_equipment"
    process = "process"
    environment = "environment"
    documentation = "documentation"


def _enum(kind) -> Enum:
    # stored as plain strings so the schema is identical on SQLite and PostgreSQL
    return Enum(kind, native_enum=False, length=32, validate_strings=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.engineer)
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Defect(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[Severity] = mapped_column(_enum(Severity), index=True)
    status: Mapped[Status] = mapped_column(_enum(Status), default=Status.open, index=True)
    product: Mapped[str] = mapped_column(String(64), index=True)
    component: Mapped[str] = mapped_column(String(64))
    failure_mode: Mapped[str] = mapped_column(String(128), index=True)
    found_in: Mapped[TestStage] = mapped_column(_enum(TestStage))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    root_cause_category: Mapped[RootCause | None] = mapped_column(_enum(RootCause), nullable=True)
    root_cause: Mapped[str] = mapped_column(Text, default="")
    verification_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    actions: Mapped[list[CorrectiveAction]] = relationship(
        back_populates="defect", cascade="all, delete-orphan", order_by="CorrectiveAction.id")
    events: Mapped[list[AuditEvent]] = relationship(
        back_populates="defect", cascade="all, delete-orphan", order_by="AuditEvent.id")

    @property
    def key(self) -> str:
        return f"DEF-{self.id:04d}"


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    defect_id: Mapped[int] = mapped_column(ForeignKey("defects.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    defect: Mapped[Defect] = relationship(back_populates="actions")
    owner: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    defect_id: Mapped[int] = mapped_column(ForeignKey("defects.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    defect: Mapped[Defect] = relationship(back_populates="events")
    actor: Mapped[User] = relationship()

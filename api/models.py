"""Tally portal data model — six tables, source of truth for Phase 1.4 migration."""

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import Enum as SAEnum
from sqlmodel import Field, SQLModel


# --- Enums --------------------------------------------------------------------


class Role(str, enum.Enum):
    employee = "employee"
    manager = "manager"
    admin = "admin"


class CyclePhase(str, enum.Enum):
    closed = "closed"
    goal_setting = "goal_setting"
    q1 = "q1"
    q2 = "q2"
    q3 = "q3"
    q4_annual = "q4_annual"


class UoMType(str, enum.Enum):
    numeric_min = "numeric_min"
    numeric_max = "numeric_max"
    percent_min = "percent_min"
    percent_max = "percent_max"
    timeline = "timeline"
    zero = "zero"


class GoalStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    locked = "locked"


class AchievementStatus(str, enum.Enum):
    not_started = "not_started"
    on_track = "on_track"
    completed = "completed"


class Quarter(str, enum.Enum):
    q1 = "q1"
    q2 = "q2"
    q3 = "q3"
    q4 = "q4"


# --- Helpers ------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_col(e: type[enum.Enum], *, length: int = 20, nullable: bool = False) -> Column:
    return Column(SAEnum(e, native_enum=False, length=length), nullable=nullable)


def _ts_col(*, on_update: bool = False, nullable: bool = False) -> Column:
    kwargs: dict = {"nullable": nullable, "default": _utcnow}
    if on_update:
        kwargs["onupdate"] = _utcnow
    return Column(DateTime(timezone=True), **kwargs)


# --- Tables -------------------------------------------------------------------


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(
        sa_column=Column(String(255), unique=True, index=True, nullable=False)
    )
    name: str = Field(sa_column=Column(String(255), nullable=False))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    role: Role = Field(sa_column=_enum_col(Role))
    manager_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    department: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_ts_col())


class Cycle(SQLModel, table=True):
    __tablename__ = "cycles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(64), unique=True, nullable=False))
    goal_setting_opens: date
    q1_opens: date
    q2_opens: date
    q3_opens: date
    q4_opens: date
    current_phase: CyclePhase = Field(sa_column=_enum_col(CyclePhase))
    is_active: bool = Field(default=False)


class ThrustArea(SQLModel, table=True):
    __tablename__ = "thrust_areas"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(128), unique=True, nullable=False))


class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employee_id: uuid.UUID = Field(foreign_key="users.id", index=True, nullable=False)
    cycle_id: uuid.UUID = Field(foreign_key="cycles.id", index=True, nullable=False)
    thrust_area_id: uuid.UUID = Field(foreign_key="thrust_areas.id", nullable=False)

    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: str = Field(sa_column=Column(Text, nullable=False))

    uom_type: UoMType = Field(sa_column=_enum_col(UoMType))
    target_value: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(18, 4), nullable=True)
    )
    target_date: Optional[date] = Field(default=None)
    weightage: int = Field(ge=10, le=100)

    status: GoalStatus = Field(
        default=GoalStatus.draft, sa_column=_enum_col(GoalStatus)
    )
    shared_parent_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="goals.id"
    )
    manager_comment: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    created_at: datetime = Field(default_factory=_utcnow, sa_column=_ts_col())
    updated_at: datetime = Field(
        default_factory=_utcnow, sa_column=_ts_col(on_update=True)
    )


class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("goal_id", "quarter", name="uq_achievement_goal_quarter"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    goal_id: uuid.UUID = Field(foreign_key="goals.id", index=True, nullable=False)
    quarter: Quarter = Field(sa_column=_enum_col(Quarter))

    actual_value: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(18, 4), nullable=True)
    )
    actual_date: Optional[date] = Field(default=None)
    status: AchievementStatus = Field(
        default=AchievementStatus.not_started, sa_column=_enum_col(AchievementStatus)
    )
    manager_comment: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    created_at: datetime = Field(default_factory=_utcnow, sa_column=_ts_col())
    updated_at: datetime = Field(
        default_factory=_utcnow, sa_column=_ts_col(on_update=True)
    )


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_goal_id_timestamp", "goal_id", "timestamp"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    goal_id: uuid.UUID = Field(foreign_key="goals.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)

    action: str = Field(sa_column=Column(String(64), nullable=False))
    field_changed: Optional[str] = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    old_value: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    new_value: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    timestamp: datetime = Field(default_factory=_utcnow, sa_column=_ts_col())

"""Database tables.

A table class describes the columns; Alembic turns changes to these classes into
migrations (versioned scripts that change the real database).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobPostingRow(Base):
    __tablename__ = "job_postings"
    # One row per job per platform: fetching the same job twice updates it instead of adding it.
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_job_postings_source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(2), default="gb", server_default="gb", index=True)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_is_predicted: Mapped[bool] = mapped_column(default=False)
    contract_type: Mapped[str | None] = mapped_column(String(32))
    contract_time: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # JSONB on Postgres (indexable, compact); plain JSON elsewhere.
    raw: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Filled in by services/tagging.py after each fetch.
    sponsor_status: Mapped[str | None] = mapped_column(String(16))  # see SponsorStatus
    sponsor_match: Mapped[str | None] = mapped_column(Text)  # register name it matched
    sponsor_score: Mapped[float | None] = mapped_column(Float)  # 0-100 name similarity
    seniority: Mapped[str | None] = mapped_column(String(16))  # see Seniority
    seniority_reason: Mapped[str | None] = mapped_column(Text)
    # Filled in by services/market_rules.py: per-country flags, one note each, yearly pay.
    market_flags: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, server_default="[]"
    )
    market_notes: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, server_default="[]"
    )
    salary_year: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class SponsorRow(Base):
    """One row of the Home Office register of licensed sponsors (workers)."""

    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(Text, index=True)  # normalised for matching
    town: Mapped[str | None] = mapped_column(Text)
    county: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[str] = mapped_column(Text)  # e.g. "Worker (A rating)"
    route: Mapped[str] = mapped_column(Text)  # e.g. "Skilled Worker"
    register_date: Mapped[date] = mapped_column(Date)


_JSON = JSON().with_variant(JSONB(), "postgresql")


class UserRow(Base):
    """Someone who can log in: with Google (no password stored) or, for admins, a password.

    Passwords are stored only as salted scrypt hashes. `plan` is "free" for now; it is where
    paid tiers will hang later.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    auth_provider: Mapped[str] = mapped_column(
        String(16), default="password", server_default="password"
    )
    plan: Mapped[str] = mapped_column(String(16), default="free", server_default="free")
    is_admin: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LifeProfileRow(Base):
    """Everything a user has told us about their life: one JSON document per user."""

    __tablename__ = "life_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(_JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApplicationRow(Base):
    """One job a user is applying to, with the tailored documents."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft, applied, rejected...
    cv: Mapped[str] = mapped_column(Text, default="")
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    warnings: Mapped[list[str]] = mapped_column(_JSON, default=list)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiUsageRow(Base):
    """One AI call: who, what for, which model, tokens and list-price cost (for pricing)."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job_postings.id", ondelete="SET NULL"))
    feature: Mapped[str] = mapped_column(String(32))  # "tailor"
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileVersionRow(Base):
    """A copy of a profile before it was changed, so any save can be undone."""

    __tablename__ = "profile_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(_JSON)
    reason: Mapped[str] = mapped_column(Text, default="")  # what change came after this copy
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewRow(Base):
    """One upcoming interview: the company, role and job description to prepare for."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(Text, default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    when: Mapped[str] = mapped_column(Text, default="")  # free text, e.g. "Tue 2 Dec 10:00"
    notes: Mapped[str] = mapped_column(Text, default="")  # interviewers, format, research
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewAnswerRow(Base):
    """A question and the user's prepared answer. No interview id means a general question."""

    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    interview_id: Mapped[int | None] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, default="", server_default="")
    answer: Mapped[str] = mapped_column(Text, default="")  # the one the user chose and edited
    warnings: Mapped[list[str]] = mapped_column(_JSON, default=list)
    # AI drafts to choose from: [{"text", "warnings", "model"}]
    drafts: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, default=list, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""Database tables.

A table class describes the columns; Alembic turns changes to these classes into
migrations (versioned scripts that change the real database).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, String, Text, UniqueConstraint, func
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

"""Track which jobs a user is applying to, with the tailored documents."""

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from life200.db.models import ApplicationRow, JobPostingRow

STATUSES = ("draft", "applied", "interview", "offer", "rejected")


def get_application(session: Session, user_id: int, job_id: int) -> ApplicationRow | None:
    return session.scalar(
        select(ApplicationRow).where(
            ApplicationRow.user_id == user_id, ApplicationRow.job_id == job_id
        )
    )


def save_draft(
    session: Session, user_id: int, job_id: int, cv: str, cover_letter: str, warnings: list[str]
) -> ApplicationRow:
    app = get_application(session, user_id, job_id)
    if app is None:
        app = ApplicationRow(user_id=user_id, job_id=job_id, status="draft")
        session.add(app)
    app.cv, app.cover_letter, app.warnings = cv, cover_letter, warnings
    session.flush()
    return app


def set_status(session: Session, user_id: int, job_id: int, status: str) -> ApplicationRow:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    app = get_application(session, user_id, job_id)
    if app is None:
        app = ApplicationRow(user_id=user_id, job_id=job_id, cv="", cover_letter="", warnings=[])
        session.add(app)
    app.status = status
    if status == "applied" and app.applied_at is None:
        app.applied_at = datetime.now(UTC)
    session.flush()
    return app


def list_applications(session: Session, user_id: int) -> pd.DataFrame:
    rows = session.execute(
        select(
            JobPostingRow.id,
            JobPostingRow.title,
            JobPostingRow.company,
            JobPostingRow.country,
            ApplicationRow.status,
            ApplicationRow.applied_at,
            JobPostingRow.url,
        )
        .join(JobPostingRow, JobPostingRow.id == ApplicationRow.job_id)
        .where(ApplicationRow.user_id == user_id)
        .order_by(ApplicationRow.created_at.desc())
    ).all()
    return pd.DataFrame(
        rows, columns=["Job id", "Title", "Company", "Market", "Status", "Applied", "Link"]
    )

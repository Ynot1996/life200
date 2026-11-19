"""Save job postings to the database without creating duplicates.

Uses an "upsert" (update or insert): Postgres tries to insert each job, and if a row with
the same (source, source_id) already exists, it updates that row instead.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from life200.db.models import JobPostingRow
from life200.domain.job import JobPosting

# Columns refreshed when a job is fetched again. first_seen is deliberately not here.
_UPDATABLE = (
    "title",
    "company",
    "location",
    "salary_min",
    "salary_max",
    "salary_is_predicted",
    "contract_type",
    "contract_time",
    "category",
    "description",
    "url",
    "posted_at",
    "raw",
)


@dataclass(frozen=True, slots=True)
class SaveResult:
    received: int  # jobs passed in
    new: int  # rows that did not exist before
    updated: int  # rows that already existed and were refreshed


def save_jobs(session: Session, jobs: Iterable[JobPosting]) -> SaveResult:
    # The same job can appear twice in one fetch (e.g. across pages); keep the last copy.
    unique = {(j.source, j.source_id): j for j in jobs}
    if not unique:
        return SaveResult(received=0, new=0, updated=0)

    before = session.scalar(select(func.count()).select_from(JobPostingRow)) or 0
    stmt = insert(JobPostingRow).values([j.model_dump() for j in unique.values()])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_job_postings_source_id",
        set_={**{c: stmt.excluded[c] for c in _UPDATABLE}, "last_seen": func.now()},
    )
    session.execute(stmt)
    after = session.scalar(select(func.count()).select_from(JobPostingRow)) or 0

    new = after - before
    return SaveResult(received=len(unique), new=new, updated=len(unique) - new)

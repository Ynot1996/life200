from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from life200.db.models import JobPostingRow
from life200.services.ingest import save_jobs
from life200.sources.adzuna import parse_job


def count_rows(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(JobPostingRow)) or 0


def test_jobs_are_saved(db_session: Session, adzuna_response: dict[str, Any]) -> None:
    jobs = [parse_job(item) for item in adzuna_response["results"]]

    result = save_jobs(db_session, jobs)

    assert (result.received, result.new, result.updated) == (3, 3, 0)
    row = db_session.scalars(select(JobPostingRow).where(JobPostingRow.source_id == "5001")).one()
    assert row.company == "Example Fintech Ltd"
    assert row.raw["title"] == "Junior Python Developer"


def test_fetching_twice_adds_no_duplicates(
    db_session: Session, adzuna_response: dict[str, Any]
) -> None:
    jobs = [parse_job(item) for item in adzuna_response["results"]]

    save_jobs(db_session, jobs)
    second = save_jobs(db_session, jobs)

    assert count_rows(db_session) == 3
    assert (second.new, second.updated) == (0, 3)


def test_changed_job_is_updated(db_session: Session, adzuna_response: dict[str, Any]) -> None:
    original = parse_job(adzuna_response["results"][0])
    save_jobs(db_session, [original])

    changed = original.model_copy(update={"title": "Junior Python Engineer"})
    save_jobs(db_session, [changed])

    row = db_session.scalars(select(JobPostingRow)).one()
    assert row.title == "Junior Python Engineer"


def test_same_job_twice_in_one_batch_is_saved_once(
    db_session: Session, adzuna_response: dict[str, Any]
) -> None:
    job = parse_job(adzuna_response["results"][0])

    result = save_jobs(db_session, [job, job])

    assert result.received == 1
    assert count_rows(db_session) == 1


def test_empty_batch_does_nothing(db_session: Session) -> None:
    assert save_jobs(db_session, []).received == 0

from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from life200.db.models import JobPostingRow, SponsorRow
from life200.services.ingest import save_jobs
from life200.services.jobs_view import load_jobs
from life200.services.sponsors import replace_register
from life200.services.tagging import tag_jobs
from life200.sources.adzuna import parse_job
from life200.sources.sponsor_register import (
    CONTENT_API,
    download_register,
    latest_csv_url,
    parse_register,
)

REGISTER = (Path(__file__).parent / "fixtures" / "sponsor_register.csv").read_text()
CSV_URL = "https://assets.example/SP_-_Worker_Register_-_2026-11-19.csv"


def fake_gov_uk(request: httpx.Request) -> httpx.Response:
    if str(request.url) == CONTENT_API:
        return httpx.Response(
            200, json={"details": {"attachments": [{"url": "x.pdf"}, {"url": CSV_URL}]}}
        )
    return httpx.Response(200, content=b"\xef\xbb\xbf" + REGISTER.encode())


def test_parse_register_trims_and_skips_blank_names() -> None:
    sponsors = list(parse_register(REGISTER))
    assert len(sponsors) == 4
    assert sponsors[1].name == "EXAMPLE BANK PLC"
    assert sponsors[1].town == "London"
    assert sponsors[0].county is None


def test_latest_csv_url_finds_the_csv_and_its_date() -> None:
    http = httpx.Client(transport=httpx.MockTransport(fake_gov_uk))
    assert latest_csv_url(http) == (CSV_URL, date(2026, 11, 19))


def test_latest_csv_url_fails_clearly_without_a_csv() -> None:
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"details": {"attachments": []}})
        )
    )
    with pytest.raises(RuntimeError, match="no CSV"):
        latest_csv_url(http)


def test_download_register_strips_byte_order_mark() -> None:
    sponsors, when = download_register(httpx.Client(transport=httpx.MockTransport(fake_gov_uk)))
    assert sponsors[0].name == "Example Fintech Limited"
    assert when == date(2026, 11, 19)


def test_register_is_replaced_not_appended(db_session: Session) -> None:
    sponsors = list(parse_register(REGISTER))
    replace_register(db_session, sponsors, date(2026, 11, 18))
    replace_register(db_session, sponsors, date(2026, 11, 19))

    assert db_session.scalar(select(func.count()).select_from(SponsorRow)) == 4


def test_jobs_are_tagged(db_session: Session, adzuna_response: dict[str, Any]) -> None:
    replace_register(db_session, list(parse_register(REGISTER)), date(2026, 11, 19))
    save_jobs(db_session, [parse_job(item) for item in adzuna_response["results"]])

    assert tag_jobs(db_session) == 3
    rows = {r.source_id: r for r in db_session.scalars(select(JobPostingRow))}
    assert rows["5001"].sponsor_status == "licensed"  # Example Fintech Ltd
    assert rows["5002"].sponsor_status == "licensed"  # Example Bank PLC
    assert rows["5003"].sponsor_status == "unknown"  # no company
    assert rows["5001"].seniority == "junior"


def test_load_jobs_returns_a_table(db_engine: Engine, adzuna_response: dict[str, Any]) -> None:
    with Session(db_engine) as session, session.begin():
        save_jobs(session, [parse_job(item) for item in adzuna_response["results"]])
    try:
        df = load_jobs(db_engine)
        assert len(df) == 3
        assert {"Title", "Company", "Sponsor", "Level", "Link"} <= set(df.columns)
        assert df["Salary from"].dtype.kind == "f"
    finally:
        with db_engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE job_postings CASCADE")

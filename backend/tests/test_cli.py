from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from life200 import cli
from life200.core.config import Settings
from life200.domain.job import JobPosting
from life200.sources.adzuna import parse_job


def test_fetch_without_keys_explains_what_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None))

    assert cli.main(["fetch", "junior python"]) == 1
    assert "LIFE200_ADZUNA_APP_ID" in capsys.readouterr().err


def test_fetch_saves_jobs_and_reports(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    db_engine: Engine,
    adzuna_response: dict[str, Any],
) -> None:
    class FakeClient:
        def __init__(self, app_id: str, app_key: str) -> None:
            assert app_key == "secret"

        def search(self, what: str, **kwargs: Any) -> Iterator[JobPosting]:
            yield from (parse_job(item) for item in adzuna_response["results"])

    settings = Settings(_env_file=None, adzuna_app_id="id", adzuna_app_key=SecretStr("secret"))
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "AdzunaClient", FakeClient)
    monkeypatch.setattr(cli, "get_sessionmaker", lambda: sessionmaker(db_engine))

    assert cli.main(["fetch", "junior python", "--pages", "1"]) == 0
    assert "Fetched 3 jobs" in capsys.readouterr().out

    # This test commits for real, so clean up for the other tests.
    with db_engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE job_postings")

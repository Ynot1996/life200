from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from life200.sources.adzuna import AdzunaClient, AdzunaError, parse_job


def make_client(handler: Any) -> AdzunaClient:
    """An AdzunaClient whose HTTP calls go to `handler` instead of the internet."""
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return AdzunaClient("test-id", "test-key", http=http, backoff_seconds=0)


# ---------- parse_job: turning one result into a JobPosting ----------


def test_parse_full_record(adzuna_response: dict[str, Any]) -> None:
    job = parse_job(adzuna_response["results"][0])

    assert job.source == "adzuna"
    assert job.source_id == "5001"
    assert job.title == "Junior Python Developer"
    assert job.company == "Example Fintech Ltd"
    assert job.location == "London, UK"
    assert job.salary_min == Decimal("35000")
    assert job.salary_max == Decimal("42000")
    assert job.salary_is_predicted is False
    assert job.category == "IT Jobs"
    assert job.posted_at == datetime(2026, 11, 18, 9, 12, 45, tzinfo=UTC)
    assert job.raw["id"] == "5001"  # the original is kept


def test_parse_predicted_salary(adzuna_response: dict[str, Any]) -> None:
    job = parse_job(adzuna_response["results"][1])
    assert job.salary_is_predicted is True
    assert job.salary_min == Decimal("38500.5")


def test_parse_minimal_record(adzuna_response: dict[str, Any]) -> None:
    job = parse_job(adzuna_response["results"][2])
    assert job.company is None
    assert job.salary_min is None
    assert job.posted_at is None


# ---------- AdzunaClient: calling the API ----------


def test_search_sends_auth_and_query(adzuna_response: dict[str, Any]) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=adzuna_response)

    jobs = list(make_client(handler).search("junior python", where="Leeds", max_days_old=7))

    assert len(jobs) == 3
    params = seen[0].url.params
    assert seen[0].url.path.endswith("/search/1")
    assert params["app_id"] == "test-id"
    assert params["what"] == "junior python"
    assert params["where"] == "Leeds"
    assert params["max_days_old"] == "7"


def test_whole_uk_search_in_a_category(adzuna_response: dict[str, Any]) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=adzuna_response)

    list(make_client(handler).search("junior", where=None, category="it-jobs"))
    assert "where" not in seen[0].url.params
    assert seen[0].url.params["category"] == "it-jobs"


def test_pauses_between_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    full_page = {"results": [{"id": str(i), "title": "t", "redirect_url": "u"} for i in range(50)]}
    sleeps: list[float] = []
    monkeypatch.setattr("life200.sources.adzuna.time.sleep", sleeps.append)
    client = AdzunaClient(
        "id",
        "key",
        http=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=full_page))
        ),
        page_delay_seconds=3,
    )
    assert len(list(client.search("x", pages=2))) == 100
    assert sleeps == [3]


def test_search_stops_when_a_page_is_short(adzuna_response: dict[str, Any]) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=adzuna_response)  # 3 results: less than a full page

    list(make_client(handler).search("x", pages=5))
    assert calls == 1


def test_search_retries_after_rate_limit(adzuna_response: dict[str, Any]) -> None:
    replies = iter([httpx.Response(429), httpx.Response(200, json=adzuna_response)])

    jobs = list(make_client(lambda request: next(replies)).search("x"))
    assert len(jobs) == 3


def test_search_retries_after_network_error(adzuna_response: dict[str, Any]) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json=adzuna_response)

    assert len(list(make_client(handler).search("x"))) == 3


def test_search_gives_up_after_max_retries() -> None:
    with pytest.raises(AdzunaError, match="HTTP 503"):
        list(make_client(lambda request: httpx.Response(503)).search("x"))


def test_network_error_gives_up_after_max_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(AdzunaError, match="network error"):
        list(make_client(handler).search("x"))


def test_bad_credentials_fail_without_retry_or_leaking_the_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    with pytest.raises(AdzunaError) as exc_info:
        list(make_client(handler).search("x"))

    assert calls == 1  # 401 will not fix itself, so no retry
    assert "test-key" not in str(exc_info.value)

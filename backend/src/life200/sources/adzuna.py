"""Fetch job postings from the Adzuna API (UK and Singapore; Adzuna has no Japan or Taiwan).

API docs: https://developer.adzuna.com/docs/search
Terms: listings shown publicly must say "Jobs by Adzuna" and link through Adzuna's URL.
"""

import logging
import time
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from life200.domain.job import JobPosting

log = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search"
SOURCE = "adzuna"
MAX_PER_PAGE = 50  # Adzuna's limit
RETRY_STATUSES = {429, 500, 502, 503, 504}  # worth trying again: rate limit or server trouble


class AdzunaError(RuntimeError):
    """Adzuna returned an error we cannot recover from."""


def parse_job(item: dict[str, Any], country: str = "gb") -> JobPosting:
    """Turn one Adzuna result into a JobPosting. Pure function: easy to test."""
    return JobPosting(
        source=SOURCE,
        source_id=str(item["id"]),
        country=country,
        title=item["title"],
        company=(item.get("company") or {}).get("display_name"),
        location=(item.get("location") or {}).get("display_name"),
        salary_min=_money(item.get("salary_min")),
        salary_max=_money(item.get("salary_max")),
        salary_is_predicted=str(item.get("salary_is_predicted", "0")) == "1",
        contract_type=item.get("contract_type"),
        contract_time=item.get("contract_time"),
        category=(item.get("category") or {}).get("label"),
        description=item.get("description", ""),
        url=item["redirect_url"],
        posted_at=_date(item.get("created")),
        raw=item,
    )


def _money(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _date(value: str | None) -> datetime | None:
    # Adzuna sends "2026-11-18T09:12:45Z"; fromisoformat needs "+00:00" instead of "Z".
    return None if not value else datetime.fromisoformat(value.replace("Z", "+00:00"))


class AdzunaClient:
    def __init__(
        self,
        app_id: str,
        app_key: str,
        http: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        page_delay_seconds: float = 0.0,
    ) -> None:
        self._auth = {"app_id": app_id, "app_key": app_key}
        self._http = http or httpx.Client(timeout=20)
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._page_delay = page_delay_seconds  # pause between pages to respect rate limits

    def search(
        self,
        what: str,
        where: str | None = "London",
        pages: int = 1,
        max_days_old: int | None = None,
        category: str | None = None,
        country: str = "gb",
    ) -> Iterator[JobPosting]:
        """Yield jobs page by page. Stops early when a page comes back short.

        `where=None` searches the whole country; `country` is "gb" or "sg".
        `category` is an Adzuna tag such as "it-jobs".
        """
        for page in range(1, pages + 1):
            if page > 1 and self._page_delay:
                time.sleep(self._page_delay)
            params: dict[str, str | int] = {
                **self._auth,
                "what": what,
                "results_per_page": MAX_PER_PAGE,
                "sort_by": "date",
            }
            if where:
                params["where"] = where
            if max_days_old is not None:
                params["max_days_old"] = max_days_old
            if category:
                params["category"] = category
            results = self._get(f"{BASE_URL.format(country=country)}/{page}", params)["results"]
            log.info("adzuna page %d: %d jobs", page, len(results))
            yield from (parse_job(item, country) for item in results)
            if len(results) < MAX_PER_PAGE:
                return

    def _get(self, url: str, params: dict[str, str | int]) -> dict[str, Any]:
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._http.get(url, params=params)
            except httpx.TransportError as exc:  # network trouble: no response at all
                if attempt == self._max_retries:
                    raise AdzunaError(f"network error after {attempt} attempts: {exc}") from exc
                log.warning("adzuna network error (attempt %d): %s", attempt, exc)
            else:
                if response.status_code == 200:
                    data: dict[str, Any] = response.json()
                    return data
                if response.status_code not in RETRY_STATUSES or attempt == self._max_retries:
                    # Never put the URL in the message: it contains the API key.
                    raise AdzunaError(f"adzuna returned HTTP {response.status_code}")
                log.warning("adzuna HTTP %d (attempt %d)", response.status_code, attempt)
            time.sleep(self._backoff * 2 ** (attempt - 1))  # wait 2s, 4s, 8s…
        raise AssertionError("unreachable")

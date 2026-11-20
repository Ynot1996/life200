"""Fetch job postings from Jooble's Taiwan site (Adzuna does not cover Taiwan).

API: POST https://<country>.jooble.org/api/<key> with {"keywords", "location", "page"}.
Keys are free, and each works only on the site that issued it. Tested 2026-11-20: a
jooble.org key gets 403 on tw.jooble.org, and jp.jooble.org redirects to a 404. Jooble's terms ask
that listings link to Jooble's own URL, which `link` is.
"""

import logging
import re
import time
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import httpx

from life200.domain.job import JobPosting

log = logging.getLogger(__name__)

SOURCE = "jooble"
HOSTS = {"tw": "https://tw.jooble.org"}
_TAGS = re.compile(r"<[^>]+>")


class JoobleError(RuntimeError):
    """Jooble returned an error we cannot recover from."""


def parse_job(item: dict[str, Any], country: str) -> JobPosting:
    return JobPosting(
        source=SOURCE,
        source_id=str(item["id"]),
        country=country,
        title=_TAGS.sub("", item.get("title") or "").strip() or "(no title)",
        company=item.get("company") or None,
        location=item.get("location") or None,
        contract_type=item.get("type") or None,
        description=_TAGS.sub("", item.get("snippet") or "").strip(),
        url=item["link"],
        posted_at=_date(item.get("updated")),
        raw=item,
    )


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class JoobleClient:
    def __init__(
        self,
        country: str,
        key: str,
        http: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        page_delay_seconds: float = 0.0,
    ) -> None:
        if country not in HOSTS:
            raise ValueError(f"no Jooble host for {country!r}")
        self.country = country
        self._url = f"{HOSTS[country]}/api/{key}"
        self._http = http or httpx.Client(timeout=20)
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._page_delay = page_delay_seconds

    def search(self, keywords: str, location: str = "", pages: int = 1) -> Iterator[JobPosting]:
        for page in range(1, pages + 1):
            if page > 1 and self._page_delay:
                time.sleep(self._page_delay)
            jobs = self._post({"keywords": keywords, "location": location, "page": str(page)})
            log.info("jooble %s page %d: %d jobs", self.country, page, len(jobs))
            yield from (parse_job(item, self.country) for item in jobs)
            if not jobs:
                return

    def _post(self, body: dict[str, str]) -> list[dict[str, Any]]:
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._http.post(self._url, json=body)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise JoobleError(f"network error after {attempt} attempts") from exc
            else:
                if response.status_code == 200:
                    jobs: list[dict[str, Any]] = response.json().get("jobs", [])
                    return jobs
                if response.status_code < 500 and response.status_code != 429:
                    # The key is in the URL, so never include the URL in the message.
                    raise JoobleError(f"jooble returned HTTP {response.status_code}")
                if attempt == self._max_retries:
                    raise JoobleError(f"jooble returned HTTP {response.status_code}")
            time.sleep(self._backoff * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

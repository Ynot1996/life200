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
from decimal import Decimal
from typing import Any

import httpx

from life200.domain.job import JobPosting

log = logging.getLogger(__name__)

SOURCE = "jooble"
HOSTS = {"tw": "https://tw.jooble.org"}
_TAGS = re.compile(r"<[^>]+>")


class JoobleError(RuntimeError):
    """Jooble returned an error we cannot recover from."""


# Range separators: 至, ~, -, "to", plus the fullwidth tilde and en dash (by code point,
# so the source stays plain ASCII for the linter).
_SEP = "(?:" + "|".join(["至", "~", "-", "to", chr(0xFF5E), chr(0x2013)]) + ")"
_UNIT = r"(k|萬|万)?"
_K_RANGE = re.compile(r"([\d.,]+)\s*" + _UNIT + r"\s*" + _SEP + r"\s*([\d.,]+)\s*" + _UNIT, re.I)
_K_ONE = re.compile(r"([\d.,]+)\s*" + _UNIT, re.I)
_IN_TEXT = re.compile(
    r"(月薪|年薪)\s*(?:NT\$|新台幣)?\s*([\d.,]+\s*(?:k|萬|万)?"
    r"(?:\s*" + _SEP + r"\s*[\d.,]+\s*(?:k|萬|万)?)?)",
    re.I,
)


def _amount(number: str, unit: str | None) -> Decimal:
    value = Decimal(number.replace(",", ""))
    if unit and unit.casefold() == "k":
        value *= 1000
    elif unit in ("萬", "万"):
        value *= 10000
    return value


def parse_salary(salary: str, snippet: str = "") -> tuple[Decimal | None, Decimal | None]:
    """Monthly or yearly pay in NT$ from Jooble's salary text or the ad itself.

    '47k 至 58k元' -> (47000, 58000) a month. Hourly pay ('時薪 200元') is ignored because
    it cannot be compared with salaried jobs. '年薪 60萬' is returned as a yearly figure.
    """
    text = salary.strip()
    if not text or "時薪" in text:
        m = _IN_TEXT.search(snippet)
        if m is None:
            return None, None
        text = m.group(2)
        if m.group(1) == "年薪":
            low, high = parse_salary(text)
            return low, high
    if m := _K_RANGE.search(text):
        return _amount(m.group(1), m.group(2) or m.group(4)), _amount(m.group(3), m.group(4))
    if m := _K_ONE.search(text):
        value = _amount(m.group(1), m.group(2))
        return value, value
    return None, None


def parse_job(item: dict[str, Any], country: str) -> JobPosting:
    snippet = _TAGS.sub("", item.get("snippet") or "")
    salary_min, salary_max = parse_salary(item.get("salary") or "", snippet)
    return JobPosting(
        source=SOURCE,
        source_id=str(item["id"]),
        country=country,
        title=_TAGS.sub("", item.get("title") or "").strip() or "(no title)",
        company=item.get("company") or None,
        location=item.get("location") or None,
        salary_min=salary_min,
        salary_max=salary_max,
        contract_type=item.get("type") or None,
        description=snippet.strip(),
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

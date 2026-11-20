"""Download and parse the Home Office register of licensed sponsors (workers).

Page: https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers
The CSV is replaced most working days; its URL changes each time, so we look it up through
the GOV.UK content API.
"""

import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import httpx

CONTENT_API = (
    "https://www.gov.uk/api/content/government/publications/register-of-licensed-sponsors-workers"
)


@dataclass(frozen=True, slots=True)
class Sponsor:
    name: str
    town: str | None
    county: str | None
    rating: str
    route: str


def latest_csv_url(http: httpx.Client) -> tuple[str, date]:
    """Return the current register's CSV URL and the date in its file name."""
    response = http.get(CONTENT_API)
    response.raise_for_status()
    for attachment in response.json()["details"]["attachments"]:
        url: str = attachment.get("url", "")
        if url.endswith(".csv"):
            found = re.search(r"(\d{4}-\d{2}-\d{2})", url)
            return url, date.fromisoformat(found.group(1)) if found else date.today()
    raise RuntimeError("no CSV attachment on the sponsor register page")


def parse_register(text: str) -> Iterator[Sponsor]:
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("Organisation Name") or "").strip()
        if not name:
            continue
        yield Sponsor(
            name=name,
            town=_clean(row.get("Town/City")),
            county=_clean(row.get("County")),
            rating=(row.get("Type & Rating") or "").strip(),
            route=(row.get("Route") or "").strip(),
        )


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def download_register(http: httpx.Client) -> tuple[list[Sponsor], date]:
    url, register_date = latest_csv_url(http)
    response = http.get(url, follow_redirects=True)
    response.raise_for_status()
    # utf-8-sig drops the invisible byte-order mark some government CSVs start with.
    text = response.content.decode("utf-8-sig", errors="replace")
    return list(parse_register(text)), register_date

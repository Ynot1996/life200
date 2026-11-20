"""Fetch jobs from Japan Dev (japan-dev.com), a board of English-friendly tech jobs in Japan.

The jobs page embeds its data as Nuxt JSON (`__NUXT_DATA__`): one flat array where objects
and lists refer to other entries by index. `decode_nuxt` rebuilds the real objects. Each job
has structured fields we rely on: japanese_level, candidate_location, sponsors_visas,
seniority_level, salary_min/max (yen per year). The site's robots.txt allows /jobs.
"""

import json
import re
from datetime import datetime
from typing import Any

import httpx

from life200.domain.job import JobPosting

SOURCE = "japandev"
JOBS_URL = "https://japan-dev.com/jobs"
USER_AGENT = "life200-personal-job-search"
_NUXT = re.compile(r'<script type="application/json"[^>]*id="__NUXT_DATA__">(.*?)</script>', re.S)
_WRAPPERS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


class JapanDevError(RuntimeError):
    pass


def decode_nuxt(html: str) -> list[dict[str, Any]]:
    """Every job object found in the page."""
    m = _NUXT.search(html)
    if m is None:
        raise JapanDevError("the page has no __NUXT_DATA__ block (layout changed?)")
    data: list[Any] = json.loads(m.group(1))

    def resolve(i: Any, depth: int = 0) -> Any:
        if not isinstance(i, int) or not 0 <= i < len(data):
            return i  # not a reference: keep as is
        value = data[i]
        if depth > 8:
            return None
        if isinstance(value, dict):
            return {k: resolve(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], str) and value[0] in _WRAPPERS:
                return resolve(value[1], depth)
            return [resolve(v, depth + 1) for v in value]
        return value

    jobs = []
    for i, value in enumerate(data):
        if isinstance(value, dict) and "japanese_level" in value and "slug" in value:
            job = resolve(i)
            if not isinstance(job.get("id"), str | int):  # a search-highlight copy, not a job
                continue
            job.pop("_highlightResult", None)
            jobs.append(job)
    return jobs


def parse_job(item: dict[str, Any]) -> JobPosting:
    company = item.get("company") or {}
    facts = [
        f"Japanese: {item.get('japanese_level') or 'unknown'}",
        f"English: {item.get('english_level') or 'unknown'}",
        f"Candidates: {_label(item.get('candidate_location'))}",
        f"Visa sponsorship: {_label(item.get('sponsors_visas'))}",
        f"Remote: {_label(item.get('remote_level'))}",
        f"Seniority: {_label(item.get('seniority_level'))}",
        "Skills: " + ", ".join(item.get("skill_names") or []),
        "Company: " + ", ".join(item.get("company_tag_names") or []),
    ]
    text = "\n".join(
        x for x in (item.get("intro"), item.get("requirements"), item.get("details")) if x
    )
    return JobPosting(
        source=SOURCE,
        source_id=str(item["id"]),
        country="jp",
        title=item.get("title") or "(no title)",
        company=item.get("company_name") or company.get("name"),
        location=item.get("location"),
        salary_min=item.get("salary_min") or None,
        salary_max=item.get("salary_max") or None,
        contract_type=item.get("contract_type"),
        description="\n".join(facts) + ("\n\n" + text if text else ""),
        url=f"{JOBS_URL}/{company.get('slug', 'company')}/{item['slug']}",
        posted_at=_date(item.get("published_at") or item.get("created_at")),
        raw=item,
    )


def _label(enum: str | None) -> str:
    """'candidate_location_anywhere' -> 'anywhere'."""
    if not enum:
        return "unknown"
    for prefix in ("candidate_location_", "sponsors_visas_", "remote_level_", "seniority_level_"):
        enum = enum.removeprefix(prefix)
    return enum.replace("_", " ")


def _date(value: str | None) -> datetime | None:
    return None if not value else datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_jobs(http: httpx.Client | None = None) -> list[JobPosting]:
    client = http or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
    response = client.get(JOBS_URL)
    if response.status_code != 200:
        raise JapanDevError(f"japan-dev.com returned HTTP {response.status_code}")
    return [parse_job(item) for item in decode_nuxt(response.text)]

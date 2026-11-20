"""Per-country rules and the Japan Dev source."""

import json
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from life200.services.market_rules import (
    ep_minimum_monthly,
    seniority_from_source,
    tag_market,
    yearly_salary,
)
from life200.sources.japandev import JapanDevError, decode_nuxt, fetch_jobs, parse_job

TODAY = date(2026, 11, 20)


def tags(
    country: str,
    text: str = "",
    source: str = "x",
    lo: Any = None,
    hi: Any = None,
    raw: dict[str, Any] | None = None,
) -> Any:
    return tag_market(country, source, "Junior Engineer", text, lo, hi, raw or {}, today=TODAY)


# ---------- Japan ----------


@pytest.mark.parametrize(
    "text",
    ["JLPT N2 or above", "Business level Japanese is required", "日本語ビジネスレベル必須"],
)
def test_japanese_required_from_text(text: str) -> None:
    assert "japanese_required" in tags("jp", text).flags


def test_japan_dev_structured_fields_win() -> None:
    raw = {
        "japanese_level": "Not Required",
        "candidate_location": "candidate_location_anywhere",
        "sponsors_visas": "sponsors_visas_yes",
    }
    result = tags("jp", "JLPT N2 nice to have", source="japandev", raw=raw)
    assert result.flags == ["overseas_ok", "visa_sponsor"]

    raw = {"japanese_level": "Business", "candidate_location": "candidate_location_japan_only"}
    result = tags("jp", source="japandev", raw=raw)
    assert result.flags == ["japanese_required", "japan_residents_only"]


def test_overseas_ok_from_text() -> None:
    assert "overseas_ok" in tags("jp", "We offer relocation support").flags


# ---------- Taiwan ----------


@pytest.mark.parametrize("text", ["台清交成畢業優先", "限頂大", "Top-tier university degree"])
def test_elite_school(text: str) -> None:
    assert tags("tw", text).flags == ["elite_school"]


def test_taiwan_monthly_pay_becomes_yearly() -> None:
    assert yearly_salary("tw", 40000, 60000) == Decimal(720000)
    assert yearly_salary("tw", None, 1_200_000) == Decimal(1_200_000)
    assert yearly_salary("gb", 30000, None) == Decimal(30000)
    assert yearly_salary("sg", None, None) is None


# ---------- Singapore ----------


def test_singapore_local_only_and_ep() -> None:
    assert "local_only" in tags("sg", "Singaporeans only please").flags
    assert "local_only" in tags("sg", "Open to SC/PR only").flags
    assert "ep_ok" in tags("sg", hi=84000).flags  # S$7,000 a month
    below = tags("sg", hi=48000)  # S$4,000 a month
    assert "below_ep" in below.flags
    assert "S$5,600" in below.notes[-1]
    assert "ep_unknown" in tags("sg").flags


def test_ep_minimum_rises_in_2027() -> None:
    assert ep_minimum_monthly(date(2026, 12, 31)) == 5600
    assert ep_minimum_monthly(date(2027, 1, 1)) == 6000


def test_other_markets_only_get_pay() -> None:
    assert tags("gb", "Singaporeans only", hi=30000).flags == []


# ---------- Seniority labels from the board ----------


def test_japan_dev_seniority_labels() -> None:
    assert (
        seniority_from_source("japandev", {"seniority_level": "seniority_level_junior"})[0]
        == "junior"
    )  # type: ignore[index]
    assert (
        seniority_from_source("japandev", {"seniority_level": "seniority_level_senior"})[0]
        == "not_junior"
    )  # type: ignore[index]
    assert seniority_from_source("japandev", {"is_internship": True})[0] == "junior"  # type: ignore[index]
    assert seniority_from_source("japandev", {"seniority_level": "seniority_level_unknown"}) is None
    assert seniority_from_source("adzuna", {}) is None


# ---------- Japan Dev source ----------


def _page() -> str:
    # Nuxt's flat format: objects point at other entries by index.
    data: list[Any] = [
        ["ShallowReactive", 1],
        {"jobs": 2},
        [3],
        {
            "id": 4,
            "title": 5,
            "slug": 6,
            "japanese_level": 7,
            "company_name": 8,
            "company": 9,
            "salary_min": 11,
            "salary_max": 12,
            "published_at": 13,
            "candidate_location": 14,
            "skill_names": 15,
            "_highlightResult": 17,
        },
        "3759",
        "Junior Developer",
        "acme-junior-dev",
        "Not Required",
        "Acme",
        {"slug": 10},
        "acme",
        4000000,
        6500000,
        "2026-11-19T03:59:54.000Z",
        "candidate_location_anywhere",
        [16],
        "Python",
        {"id": 18, "slug": 18, "japanese_level": 18},  # highlight copy: skipped
        {"value": 19},
        "x",
    ]
    return f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(data)}</script>'


def test_decode_and_parse_japan_dev() -> None:
    items = decode_nuxt(_page())
    assert len(items) == 1
    job = parse_job(items[0])
    assert job.country == "jp"
    assert job.title == "Junior Developer"
    assert job.url == "https://japan-dev.com/jobs/acme/acme-junior-dev"
    assert job.salary_max == Decimal(6500000)
    assert "Candidates: anywhere" in job.description
    assert "Skills: Python" in job.description


def test_fetch_japan_dev() -> None:
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=_page())))
    assert len(fetch_jobs(ok)) == 1
    blocked = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(JapanDevError, match="403"):
        fetch_jobs(blocked)
    with pytest.raises(JapanDevError, match="NUXT"):
        decode_nuxt("<html></html>")

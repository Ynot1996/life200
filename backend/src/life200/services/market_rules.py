"""Rules that matter for one job market, on top of the shared junior and sponsor tags.

Each job gets a list of flags plus a human-readable note for each, so the app can filter
and still show why. Flags:

  Japan       japanese_required, overseas_ok, japan_residents_only, visa_sponsor
  Taiwan      elite_school (asks for a top university such as 台清交成)
  Singapore   local_only (citizens/PR only), ep_ok, below_ep, ep_unknown
  Everywhere  salary_year: the top of the salary range per year, in local currency
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

# ---------- Japan ----------
_JAPANESE_REQUIRED = re.compile(
    r"JLPT\s*N[12]|\bN[12]\s*(level|or above|以上)|(business|native|fluent)[- ]level japanese|"
    r"(fluent|native|business) (in )?japanese|japanese (is )?(required|must)|"
    r"日本語(能力)?(ネイティブ|ビジネス|必須|流暢)|ビジネスレベルの日本語",
    re.IGNORECASE,
)
_OVERSEAS_OK = re.compile(
    r"(apply|applicants?|candidates?) (from )?(abroad|overseas|outside (of )?japan)|"
    r"relocation (support|assistance|package)|visa sponsorship|"
    r"海外(在住|から)(の方)?(も)?(応募|歓迎|可)",
    re.IGNORECASE,
)
_JAPANESE_OK_LEVELS = {"not required", "conversational", "basic", "none", ""}

# ---------- Taiwan ----------
_ELITE_SCHOOL = re.compile(
    r"台清交成|台大|清大|交大|成大|頂(尖)?大(學)?|國立大學(以上|優先|畢)|"
    r"top[- ]?(tier|ranked|\d+) universit|prestigious universit|NTU,? NTHU|NTHU|NYCU|NCKU",
    re.IGNORECASE,
)

# ---------- Singapore ----------
_LOCAL_ONLY = re.compile(
    r"singaporeans? only|only singaporeans?|singapore citizens? only|\b(sc|spr)\s*/\s*(pr|spr)\b"
    r"(\s*only)?|citizens? (and|or|/) (permanent residents?|pr) only|"
    r"open to singaporeans|must be (a )?singapore(an| citizen)|no work pass|"
    r"(locals?|singaporean) (candidates )?only",
    re.IGNORECASE,
)


def ep_minimum_monthly(on: date) -> int:
    """Employment Pass minimum monthly salary (S$) for a young applicant outside finance.

    S$5,600 for new applications in 2026, S$6,000 from 1 January 2027 (MOM, Budget 2026).
    Finance needs more (S$6,200 / S$6,600) and the bar rises with age, so this is a floor.
    """
    return 6000 if on >= date(2027, 1, 1) else 5600


@dataclass
class MarketTags:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    salary_year: Decimal | None = None

    def add(self, flag: str, note: str) -> None:
        self.flags.append(flag)
        self.notes.append(note)


def yearly_salary(country: str, salary_min: Any, salary_max: Any) -> Decimal | None:
    """Top of the range per year. Taiwan ads usually give NT$ per month: below 300,000 is
    treated as monthly and multiplied by 12 (Taiwan pays a 13th-month bonus often, ignored)."""
    top = salary_max or salary_min
    if top is None:
        return None
    value = Decimal(str(top))
    if country == "tw" and value < 300_000:
        value *= 12
    return value


def _text(title: str, description: str) -> str:
    return f"{title}\n{description}"


def tag_market(
    country: str,
    source: str,
    title: str,
    description: str,
    salary_min: Any,
    salary_max: Any,
    raw: dict[str, Any],
    today: date | None = None,
) -> MarketTags:
    tags = MarketTags(salary_year=yearly_salary(country, salary_min, salary_max))
    text = _text(title, description)

    if country == "jp":
        if source == "japandev":  # the board states the level, so trust it over ad wording
            level = str(raw.get("japanese_level") or "").casefold()
            if level not in _JAPANESE_OK_LEVELS or raw.get("is_japanese_only") is True:
                tags.add("japanese_required", f"Japanese level: {raw.get('japanese_level')}")
        elif raw.get("is_japanese_only") is True:
            tags.add("japanese_required", "posted as Japanese-only")
        elif m := _JAPANESE_REQUIRED.search(text):
            tags.add("japanese_required", f'asks for "{m.group(0)}"')

        where = raw.get("candidate_location") if source == "japandev" else None
        if where == "candidate_location_anywhere":
            tags.add("overseas_ok", "accepts candidates living outside Japan")
        elif where == "candidate_location_japan_only":
            tags.add("japan_residents_only", "only candidates already in Japan")
        elif m := _OVERSEAS_OK.search(text):
            tags.add("overseas_ok", f'says "{m.group(0)}"')
        if raw.get("sponsors_visas") == "sponsors_visas_yes":
            tags.add("visa_sponsor", "sponsors work visas")

    elif country == "tw":
        if m := _ELITE_SCHOOL.search(text):
            tags.add("elite_school", f'asks for a top university ("{m.group(0)}")')

    elif country == "sg":
        if m := _LOCAL_ONLY.search(text):
            tags.add("local_only", f'says "{m.group(0)}"')
        minimum = ep_minimum_monthly(today or date.today())
        if tags.salary_year is None:
            tags.add("ep_unknown", "no salary given, so Employment Pass chances are unknown")
        elif tags.salary_year / 12 >= minimum:
            tags.add(
                "ep_ok", f"pays up to S${tags.salary_year / 12:,.0f}/month, EP needs S${minimum:,}"
            )
        else:
            tags.add(
                "below_ep",
                f"pays at most S${tags.salary_year / 12:,.0f}/month, EP needs S${minimum:,}",
            )
    return tags


def seniority_from_source(source: str, raw: dict[str, Any]) -> tuple[str, str] | None:
    """Some boards label seniority themselves; trust that over title words."""
    if source == "japandev":
        level = raw.get("seniority_level")
        if level in ("seniority_level_junior", "seniority_level_entry", "seniority_level_new_grad"):
            return "junior", "Japan Dev labels it junior"
        if raw.get("is_internship") is True:
            return "junior", "Japan Dev labels it an internship"
        if level in ("seniority_level_mid_level", "seniority_level_senior", "seniority_level_lead"):
            return (
                "not_junior",
                f"Japan Dev labels it {level.removeprefix('seniority_level_').replace('_', ' ')}",
            )
    return None

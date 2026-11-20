"""Tag each saved job with sponsor status and seniority.

Both are rules, not machine learning, for the MVP. They are deliberately transparent: every
tag stores the reason or the matched name, so a user can see why a job was tagged.
"""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from life200.db.models import JobPostingRow, SponsorRow
from life200.services.market_rules import seniority_from_source, tag_market

# ---------- Sponsor matching ----------


class SponsorStatus(StrEnum):
    LICENSED = "licensed"  # same name as on the register (after normalising)
    LIKELY = "likely"  # register has a longer version of the name, or a near-identical spelling
    AGENCY = "agency"  # posted by a recruiter: the real employer is unknown
    TRAINING = "training"  # a paid course or training scheme advertised as a job
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"  # the job has no company name
    NOT_UK = "not_uk"  # the UK register does not apply outside the UK


# Fuzzy matching on short company names gives false matches ("Radiant" vs "Gradiant"), so
# it is only used for long names, with a very high bar and the same first word.
FUZZY_THRESHOLD = 96
FUZZY_MIN_LENGTH = 10
PREFIX_MIN_LENGTH = 4  # "amazon" may match "amazon services"; "ab" may not

_SUFFIXES = re.compile(
    r"\b(limited|ltd|plc|llp|lp|llc|inc|incorporated|corp|corporation|company|co|"
    r"group|holdings|uk|gb|international|the)\b"
)
_TRADING_AS = re.compile(r"\b(t/a|trading as)\b.*$")
_AGENCY = re.compile(
    r"recruit|staffing|talent|resourcing|personnel|searchability|search ltd|search limited"
)
_TRAINING_COMPANY = re.compile(
    r"career switch|online learning|placemently|back ?(to|2) ?work|training (ltd|limited)|"
    r"academy|bootcamp|learning ltd"
)
_TRAINING_TEXT = re.compile(
    r"\b(course fee|funded course|training course|our course|complete (the|our) training|"
    r"job guarantee|guaranteed (job|interview)|no experience (needed|required).{0,80}train)",
    re.IGNORECASE,
)


def name_key(name: str) -> str:
    """Normalise a company name: 'Monzo Bank Ltd.' and 'MONZO BANK LIMITED' -> 'monzo bank'."""
    key = name.casefold().replace("&", " and ")
    key = _TRADING_AS.sub("", key)
    key = re.sub(r"[^a-z0-9 ]", " ", key)
    key = _SUFFIXES.sub(" ", key)
    return " ".join(key.split())


def is_agency(company: str) -> bool:
    return bool(_AGENCY.search(company.casefold()))


def is_training_ad(company: str | None, title: str, description: str) -> bool:
    if company and _TRAINING_COMPANY.search(company.casefold()):
        return True
    return bool(_TRAINING_TEXT.search(f"{title} {description}"))


@dataclass(frozen=True, slots=True)
class SponsorMatch:
    status: SponsorStatus
    matched_name: str | None = None
    score: float | None = None


class SponsorMatcher:
    def __init__(self, register: Iterable[tuple[str, str]]) -> None:
        """`register` is (name_key, original name) pairs."""
        self._by_key: dict[str, str] = {}
        for key, name in register:
            if key:
                self._by_key.setdefault(key, name)
        # "advance ai" and "advanceai" are the same company written differently.
        self._by_compact = {k.replace(" ", ""): k for k in self._by_key}
        # Register keys grouped by first word, for prefix and fuzzy lookups.
        self._by_first_word: dict[str, list[str]] = defaultdict(list)
        for k in self._by_key:
            self._by_first_word[k.split(" ", 1)[0]].append(k)

    def match(self, company: str | None) -> SponsorMatch:
        if not company or not company.strip():
            return SponsorMatch(SponsorStatus.UNKNOWN)
        key = name_key(company)
        if key in self._by_key:
            return SponsorMatch(SponsorStatus.LICENSED, self._by_key[key], 100.0)
        if is_agency(company):
            return SponsorMatch(SponsorStatus.AGENCY)
        if not key:
            return SponsorMatch(SponsorStatus.NOT_FOUND)

        compact = self._by_compact.get(key.replace(" ", ""))
        if compact:
            return SponsorMatch(SponsorStatus.LIKELY, self._by_key[compact], 99.0)

        same_first_word = self._by_first_word.get(key.split(" ", 1)[0], [])
        if len(key) >= PREFIX_MIN_LENGTH:
            longer = [k for k in same_first_word if k.startswith(key + " ")]
            # Only when exactly one register name fits: "Meta" also starts "Meta Hospitality",
            # so a short, common name with several candidates is too risky to guess.
            if len(longer) == 1:
                return SponsorMatch(SponsorStatus.LIKELY, self._by_key[longer[0]], 90.0)

        if len(key) >= FUZZY_MIN_LENGTH and same_first_word:
            hit = process.extractOne(
                key, same_first_word, scorer=fuzz.ratio, score_cutoff=FUZZY_THRESHOLD
            )
            if hit is not None:
                return SponsorMatch(SponsorStatus.LIKELY, self._by_key[hit[0]], float(hit[1]))
        return SponsorMatch(SponsorStatus.NOT_FOUND)


# ---------- Seniority ----------


class Seniority(StrEnum):
    JUNIOR = "junior"
    NOT_JUNIOR = "not_junior"
    UNCLEAR = "unclear"


_SENIOR_TITLE = re.compile(
    r"\b(senior|snr|sr|lead|principal|staff|head|director|manager|architect|vp|chief|"
    r"mid[- ]?level|experienced)\b"
)
_JUNIOR_TITLE = re.compile(
    r"\b(junior|jnr|jr|graduate|grad|entry[- ]level|trainee|apprentice|apprenticeship|"
    r"intern|internship|placement|associate)\b"
)
# "3+ years", "3-5 years", "3\u20135 years" (en dash), "at least 2 years"
# Japanese and Chinese titles: \b does not work between CJK characters, so no word bounds.
_SENIOR_TITLE_CJK = re.compile(r"シニア|リード|マネージャー|管理職|資深|主管|經理|经理|高級|高级")
_JUNIOR_TITLE_CJK = re.compile(
    r"ジュニア|新卒|第二新卒|未経験|インターン|実習|研修生|見習|實習|实习|新鮮人|應屆|应届|初階|初级|助理"
)
_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:-|to|\u2013)?\s*(?:\d{1,2})?\s*\+?\s*years?", re.IGNORECASE
)
_EXPERIENCE_NEARBY = re.compile(r"experience|exp\b|commercial|industry", re.IGNORECASE)
JUNIOR_MAX_YEARS = 1  # asking for more than this is not a junior role


def classify_seniority(title: str, description: str) -> tuple[Seniority, str]:
    """Return a seniority tag and a short human-readable reason."""
    title_l = title.casefold()
    senior = _SENIOR_TITLE.search(title_l) or _SENIOR_TITLE_CJK.search(title)
    if senior:
        return Seniority.NOT_JUNIOR, f'title says "{senior.group(0)}"'

    for m in _YEARS.finditer(description):
        years = int(m.group(1))
        window = description[m.end() : m.end() + 60]
        if years > JUNIOR_MAX_YEARS and years < 30 and _EXPERIENCE_NEARBY.search(window):
            return Seniority.NOT_JUNIOR, f'asks for "{m.group(0).strip()}" of experience'

    junior = _JUNIOR_TITLE.search(title_l) or _JUNIOR_TITLE_CJK.search(title)
    if junior:
        return Seniority.JUNIOR, f'title says "{junior.group(0)}"'
    return Seniority.UNCLEAR, "no seniority signal in the title or description"


# ---------- Apply to the database ----------


def load_matcher(session: Session) -> SponsorMatcher:
    rows = session.execute(select(SponsorRow.name_key, SponsorRow.name)).all()
    return SponsorMatcher((key, name) for key, name in rows)


def tag_jobs(session: Session) -> int:
    """Re-tag every saved job. Returns how many were tagged."""
    matcher = load_matcher(session)
    jobs = session.scalars(select(JobPostingRow)).all()
    for job in jobs:
        if job.country != "gb":
            sponsor = SponsorMatch(SponsorStatus.NOT_UK)
        elif is_training_ad(job.company, job.title, job.description):
            sponsor = SponsorMatch(SponsorStatus.TRAINING)
        else:
            sponsor = matcher.match(job.company)
        job.sponsor_status = sponsor.status.value
        job.sponsor_match = sponsor.matched_name
        job.sponsor_score = sponsor.score
        labelled = seniority_from_source(job.source, job.raw or {})
        if labelled is None:
            seniority, reason = classify_seniority(job.title, job.description)
            labelled = (seniority.value, reason)
        job.seniority, job.seniority_reason = labelled
        market = tag_market(
            job.country,
            job.source,
            job.title,
            job.description,
            job.salary_min,
            job.salary_max,
            job.raw or {},
        )
        job.market_flags, job.market_notes = market.flags, market.notes
        job.salary_year = market.salary_year
    session.flush()
    return len(jobs)

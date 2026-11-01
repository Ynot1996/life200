"""Fact guard: proves a tailored CV says nothing the master profile doesn't.

The LLM is allowed to select, reorder and reword achievements. It is NOT allowed to
invent a number or claim a skill. This module checks both, deterministically, so the
check itself can never hallucinate.

It is intentionally conservative: a false alarm costs you a two-second review; a
missed fabrication can cost you an interview.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from life200.domain.profile import Achievement, MasterProfile

# Matches 6,810 / 42.9 / 1.8 / 2026 / 130000. Thousands separators are normalised away.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True, slots=True)
class Violation:
    kind: Literal["number", "skill"]
    value: str
    message: str


def extract_numbers(text: str) -> set[str]:
    """Return every number in `text`, normalised ("6,810" -> "6810")."""
    return {m.group().rstrip(",").replace(",", "") for m in _NUMBER.finditer(text)}


def check_rewrite(rewritten: str, sources: Sequence[Achievement]) -> list[Violation]:
    """Flag any number in `rewritten` that does not appear in its source achievements."""
    allowed = set().union(*(extract_numbers(a.text) for a in sources)) if sources else set()
    return [
        Violation("number", n, f"number {n!r} does not appear in any source achievement")
        for n in sorted(extract_numbers(rewritten) - allowed)
    ]


def check_skills(claimed: Iterable[str], profile: MasterProfile) -> list[Violation]:
    """Flag any claimed skill that is not declared in the master profile."""
    known = profile.known_skill_names()
    return [
        Violation("skill", s, f"skill {s!r} is not in the master profile")
        for s in claimed
        if s.casefold() not in known
    ]

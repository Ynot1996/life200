"""The master profile: the single source of truth for everything Tony has done.

Every tailored CV is a *selection and rewording* of what is stored here — never an
addition. That rule is enforced in `life200.services.fact_guard`.

Design notes
------------
* The atomic unit is an `Achievement` (one CV bullet's worth of fact). Achievements
  belong to an experience, project or education entry, and each one records which
  uploaded CV(s) it came from (`sources`) so every claim stays traceable.
* Models are frozen (immutable). To change one, build a new copy with
  `model.model_copy(update={...})`. Immutability makes bugs from shared state impossible.
* `extra="forbid"` rejects unknown fields, so a typo or an LLM inventing a key fails loudly.
"""

from collections.abc import Iterator
from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    """Base class with the strict settings shared by every domain model."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SkillCategory(StrEnum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    TOOL = "tool"
    CLOUD = "cloud"
    DOMAIN = "domain"
    METHOD = "method"


class Skill(DomainModel):
    name: str = Field(min_length=1)
    category: SkillCategory
    aliases: tuple[str, ...] = ()  # e.g. "Postgres" for "PostgreSQL"

    def all_names(self) -> set[str]:
        return {n.casefold() for n in (self.name, *self.aliases)}


class SourceRef(DomainModel):
    """Where a fact came from: an uploaded CV file, optionally with the original line."""

    document: str
    excerpt: str | None = None


class Period(DomainModel):
    start: date
    end: date | None = None  # None means ongoing

    @model_validator(mode="after")
    def _end_after_start(self) -> "Period":
        if self.end is not None and self.end < self.start:
            raise ValueError("period end must not be before start")
        return self


class Achievement(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=10)
    skills: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()  # free-form, e.g. "evaluation", "leadership"
    sources: tuple[SourceRef, ...] = ()


class Experience(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    organisation: str
    title: str
    location: str | None = None
    period: Period
    achievements: tuple[Achievement, ...] = ()


class Project(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    summary: str
    url: str | None = None
    period: Period | None = None
    achievements: tuple[Achievement, ...] = ()


class Education(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    institution: str
    qualification: str
    period: Period
    grade: str | None = None
    achievements: tuple[Achievement, ...] = ()


class MasterProfile(DomainModel):
    full_name: str
    headline: str | None = None
    location: str | None = None
    email: str | None = None
    skills: tuple[Skill, ...] = ()
    experiences: tuple[Experience, ...] = ()
    projects: tuple[Project, ...] = ()
    education: tuple[Education, ...] = ()

    def known_skill_names(self) -> set[str]:
        """All skill names and aliases, case-folded, for fast membership checks."""
        names: set[str] = set()
        for skill in self.skills:
            names |= skill.all_names()
        return names

    def iter_achievements(self) -> Iterator[Achievement]:
        for section in (self.experiences, self.projects, self.education):
            for entry in section:
                yield from entry.achievements

    @model_validator(mode="after")
    def _achievement_skills_are_declared(self) -> "MasterProfile":
        known = self.known_skill_names()
        undeclared = sorted(
            {s for a in self.iter_achievements() for s in a.skills if s.casefold() not in known}
        )
        if undeclared:
            raise ValueError(f"achievements reference undeclared skills: {undeclared}")
        return self

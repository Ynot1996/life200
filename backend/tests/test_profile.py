from datetime import date

import pytest
from pydantic import ValidationError

from life200.domain.profile import Achievement, MasterProfile, Period, Project


def test_period_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError, match="end must not be before start"):
        Period(start=date(2026, 5, 1), end=date(2026, 1, 1))


def test_ongoing_period_is_allowed() -> None:
    assert Period(start=date(2026, 1, 1)).end is None


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MasterProfile(full_name="Tony Kang", invented_field="x")  # type: ignore[call-arg]


def test_models_are_immutable(profile: MasterProfile) -> None:
    with pytest.raises(ValidationError):
        profile.full_name = "Someone Else"  # type: ignore[misc]


def test_achievement_skills_must_be_declared(profile: MasterProfile) -> None:
    bad = Project(
        name="Side project",
        summary="Uses a skill that was never declared",
        achievements=(
            Achievement(text="Deployed the service on Kubernetes", skills=("Kubernetes",)),
        ),
    )
    with pytest.raises(ValidationError, match="undeclared skills"):
        MasterProfile(full_name="Tony Kang", skills=profile.skills, projects=(bad,))


def test_skill_aliases_are_case_insensitive(profile: MasterProfile) -> None:
    assert {"python", "postgres", "postgresql"} <= profile.known_skill_names()


def test_iter_achievements_walks_every_section(
    profile: MasterProfile, dissertation_achievement: Achievement
) -> None:
    assert list(profile.iter_achievements()) == [dissertation_achievement]

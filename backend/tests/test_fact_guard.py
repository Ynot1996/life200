import pytest

from life200.domain.profile import Achievement, MasterProfile
from life200.services.fact_guard import check_rewrite, check_skills, extract_numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6,810 task-runs", {"6810"}),
        ("42.9% of tasks", {"42.9"}),
        ("1.8-4.2x cheaper", {"1.8", "4.2"}),
        ("no numbers here", set()),
    ],
)
def test_extract_numbers(text: str, expected: set[str]) -> None:
    assert extract_numbers(text) == expected


def test_faithful_rewrite_passes(dissertation_achievement: Achievement) -> None:
    rewritten = "Designed a 6810-run controlled experiment; resampling proved 1.8-4.2x cheaper."
    assert check_rewrite(rewritten, [dissertation_achievement]) == []


def test_invented_number_is_flagged(dissertation_achievement: Achievement) -> None:
    rewritten = "Ran 10,000 task-runs, cutting cost by 1.8x."
    violations = check_rewrite(rewritten, [dissertation_achievement])
    assert [v.value for v in violations] == ["10000"]


def test_rewrite_with_no_sources_flags_every_number() -> None:
    assert len(check_rewrite("Improved recall by 30%", [])) == 1


def test_undeclared_skill_is_flagged(profile: MasterProfile) -> None:
    violations = check_skills(["python", "Postgres", "Kubernetes"], profile)
    assert [v.value for v in violations] == ["Kubernetes"]

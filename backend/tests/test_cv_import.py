import json
from typing import Any

import pytest

from life200.domain.life import LifeEntry, LifeProfile
from life200.services.ai_costs import Usage
from life200.services.cv_import import import_cv, merge
from life200.services.tailor import TailorError

CV = (
    "Alex Doe\nalex@example.com\n"
    "Data Analyst Intern, Acme Ltd, 2024-06 to 2024-09\n- Built dashboards"
)
REPLY = {
    "full_name": "Alex Doe",
    "email": "alex@example.com",
    "entries": [
        {
            "kind": "job",
            "title": "Data Analyst Intern",
            "org": "Acme Ltd",
            "start": "2024-06",
            "end": "2024-09",
            "text": "Built dashboards",
        },
        {"kind": "skill", "title": "Programming", "text": "Python, SQL"},
        {"kind": "story", "title": "made up", "text": "should be dropped"},
    ],
}


def writer(reply: str) -> Any:
    def write(system: str, user: str) -> tuple[str, Usage]:
        assert "never invent" in system
        assert "Alex Doe" in user
        return reply, Usage("google", "gemini-3.8-flash", 900, 700)

    return write


def test_import_reads_json_even_inside_fences() -> None:
    result = import_cv(writer("Here you go:\n```json\n" + json.dumps(REPLY) + "\n```"), CV)
    assert result.profile.full_name == "Alex Doe"
    assert [e.kind for e in result.profile.entries] == ["job", "skill"]  # stories are not imported
    assert result.usage is not None


def test_import_errors() -> None:
    with pytest.raises(TailorError, match="scanned"):
        import_cv(writer("{}"), "too short")
    with pytest.raises(TailorError, match="not a readable profile"):
        import_cv(writer("sorry, I cannot"), CV)


def test_merge_keeps_what_the_user_already_has() -> None:
    current = LifeProfile(
        full_name="Alex D.",
        entries=[LifeEntry(kind="job", title="Data Analyst Intern", org="Acme Ltd", text="mine")],
    )
    merged = merge(current, import_cv(writer(json.dumps(REPLY)), CV).profile)
    assert merged.full_name == "Alex D."  # not overwritten
    assert merged.email == "alex@example.com"  # empty, so filled
    jobs = [e for e in merged.entries if e.kind == "job"]
    assert len(jobs) == 1
    assert jobs[0].text == "mine"  # duplicate not added
    assert any(e.kind == "skill" for e in merged.entries)


def test_raw_cv_text_is_hidden_once_split_into_sections() -> None:
    raw = LifeEntry(kind="cv", title="cv.pdf", text="RAW CV TEXT")
    only_raw = LifeProfile(entries=[raw])
    assert "RAW CV TEXT" in only_raw.as_text()
    split = LifeProfile(entries=[raw, LifeEntry(kind="job", title="Intern", text="did things")])
    assert "RAW CV TEXT" not in split.as_text()
    assert "did things" in split.as_text()

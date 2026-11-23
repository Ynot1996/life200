import pytest
from sqlalchemy.orm import Session

from life200.services import auth
from life200.services.ai_costs import Usage
from life200.services.interview import (
    draft_answer,
    list_answers,
    save_answer,
    save_interview,
    suggest_questions,
)
from life200.services.tailor import TailorError

PROFILE = "STORY | Fixed the late reports\nReporting took 5 hours; I automated it to 1 hour."


def test_draft_answer_flags_numbers_not_in_the_profile() -> None:
    seen: list[str] = []

    def write(system: str, user: str) -> tuple[str, Usage | None]:
        seen.append(user)
        return "I cut reporting from 5 hours to 1 hour, saving 80% for 12 people.", None

    draft = draft_answer(write, PROFILE, "Tell me about a challenge.")
    assert "<profile>" in seen[0]
    assert "Tell me about a challenge." in seen[0]
    assert any('"12"' in w for w in draft.warnings)
    assert not any('"5"' in w for w in draft.warnings)


def test_empty_profile_is_refused() -> None:
    with pytest.raises(TailorError):
        draft_answer(lambda s, u: ("x", None), " ", "Why us?")


def test_questions_and_answers_are_per_user_and_interview(db_session: Session) -> None:
    user = auth.create_user(db_session, "iv@example.com", "long enough pw")
    other = auth.create_user(db_session, "iv2@example.com", "long enough pw")
    iv = save_interview(
        db_session, user.id, None, company="Acme", role="Data intern", job_description="x" * 40
    )
    save_answer(db_session, user.id, None, "Why should we hire you?", "General answer")
    save_answer(db_session, user.id, iv.id, "Why Acme?", "")
    save_answer(db_session, user.id, iv.id, "Why Acme?", "Because...")  # updates, no duplicate
    assert [a.answer for a in list_answers(db_session, user.id, iv.id)] == ["Because..."]
    assert [a.question for a in list_answers(db_session, user.id, None)] == [
        "Why should we hire you?"
    ]
    assert list_answers(db_session, other.id, None) == []

    reply = "1. What SQL have you used?\n- Tell me about a dashboard you built.\n\n"
    found, _ = suggest_questions(lambda s, u: (reply, None), iv)
    assert found == ["What SQL have you used?", "Tell me about a dashboard you built."]

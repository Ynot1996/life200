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


def test_several_drafts_in_one_call() -> None:
    from life200.services.interview import draft_answers

    reply = "First answer about 5 hours.\n===\nSecond answer, 1 hour.\n===\n"
    drafts = draft_answers(lambda s, u: (reply, None), PROFILE, "Q?", count=2)
    assert [d.answer for d in drafts] == ["First answer about 5 hours.", "Second answer, 1 hour."]


def test_drafts_never_overwrite_the_chosen_answer(db_session: Session) -> None:
    user = auth.create_user(db_session, "iv3@example.com", "long enough pw")
    save_answer(db_session, user.id, None, "Tell me about yourself.", "Mine")
    row = save_answer(db_session, user.id, None, "Tell me about yourself.", drafts=[{"text": "AI"}])
    assert row.answer == "Mine"
    assert row.category == "About you"  # default category for a default question


def test_rename_category_moves_default_and_saved_questions(db_session: Session) -> None:
    from life200.services.interview import DEFAULT_QUESTIONS, rename_category, search

    user = auth.create_user(db_session, "iv4@example.com", "long enough pw")
    rename_category(db_session, user.id, "Motivation", "Why here")
    cats = {a.question: a.category for a in list_answers(db_session, user.id, None)}
    assert set(cats) == set(DEFAULT_QUESTIONS["Motivation"])
    assert set(cats.values()) == {"Why here"}
    assert search(["Tell me about a time you worked in a team."], "TEAM time") != []
    assert search(["Why us?"], "team") == []


def test_rounds_practice_and_real_questions(db_session: Session) -> None:
    from datetime import date

    from life200.services.interview import (
        REAL,
        add_practice,
        list_answers,
        list_rounds,
        save_answer,
        save_round,
    )

    user = auth.create_user(db_session, "rounds@example.com", "long enough pw")
    iv = save_interview(db_session, user.id, None, company="Acme", role="Junior dev")
    final = save_round(db_session, user.id, iv.id, name="Final", on=date(2026, 12, 9))
    first = save_round(db_session, user.id, iv.id, name="HR", on=date(2026, 12, 2))
    undated = save_round(db_session, user.id, iv.id, name="Later")
    assert [r.id for r in list_rounds(db_session, user.id, iv.id)] == [
        first.id,
        final.id,
        undated.id,
    ]

    save_answer(db_session, user.id, None, "Tell me about yourself.", "My general answer")
    assert add_practice(db_session, user.id, iv.id, first.id, ["Tell me about yourself."]) == 1
    assert add_practice(db_session, user.id, iv.id, first.id, ["Tell me about yourself."]) == 0
    save_answer(
        db_session,
        user.id,
        iv.id,
        "Tell me about yourself.",
        "said it",
        kind=REAL,
        round_id=first.id,
    )

    rows = list_answers(db_session, user.id, iv.id)
    assert sorted((a.kind, a.answer) for a in rows) == [
        ("practice", "My general answer"),
        ("real", "said it"),
    ]
    assert all(a.round_id == first.id for a in rows)

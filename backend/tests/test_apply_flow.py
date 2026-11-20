"""Login, life profile, matching, tailoring and the application tracker."""

from typing import Any

import httpx
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from life200.db.models import JobPostingRow
from life200.domain.life import LifeEntry, LifeProfile
from life200.services import auth
from life200.services.applications import list_applications, save_draft, set_status
from life200.services.documents import markdown_to_docx, read_cv
from life200.services.life_store import load_profile, save_profile
from life200.services.matching import rank_jobs
from life200.services.tagging import Seniority, classify_seniority
from life200.services.tailor import TailorError, check_facts, tailor
from life200.sources.jooble import JoobleClient, JoobleError

# ---------- auth ----------


def test_password_hash_round_trip() -> None:
    stored = auth.hash_password("correct horse battery")
    assert "correct" not in stored
    assert auth.verify_password("correct horse battery", stored)
    assert not auth.verify_password("wrong password!", stored)
    assert not auth.verify_password("x", "garbage")


def test_create_and_authenticate(db_session: Session) -> None:
    auth.create_user(db_session, " Me@Example.com ", "long enough pw", is_admin=True)
    user = auth.authenticate(db_session, "me@example.com", "long enough pw")
    assert user is not None
    assert user.is_admin
    assert auth.authenticate(db_session, "me@example.com", "nope nope nope") is None
    with pytest.raises(ValueError, match="at least"):
        auth.create_user(db_session, "a@b.c", "short")


# ---------- life profile ----------


def _profile() -> LifeProfile:
    return LifeProfile(
        full_name="Test Person",
        email="test@example.com",
        markets=["gb", "jp"],
        entries=[
            LifeEntry(
                kind="project",
                title="Job search tool",
                text="Built a Python data pipeline with pandas and PostgreSQL for 1,610 jobs.",
            )
        ],
    )


def test_profile_round_trip(db_session: Session) -> None:
    user = auth.create_user(db_session, "p@example.com", "long enough pw")
    assert load_profile(db_session, user.id) == LifeProfile()
    save_profile(db_session, user.id, _profile())
    save_profile(db_session, user.id, _profile())  # second save updates
    assert load_profile(db_session, user.id).markets == ["gb", "jp"]
    assert "PROJECT | Job search tool" in _profile().as_text()


# ---------- matching ----------


def test_rank_jobs_puts_the_relevant_job_first() -> None:
    jobs = pd.DataFrame(
        {
            "Title": ["Junior Python Data Engineer", "Junior Chef"],
            "Description": ["pandas PostgreSQL pipelines", "kitchen cooking food"],
        }
    )
    ranked = rank_jobs(_profile().as_text(), jobs)
    assert ranked.scores[0] > ranked.scores[1]
    assert "python" in ranked.reasons[0]
    assert rank_jobs("", jobs).scores.sum() == 0


# ---------- seniority in Japanese and Chinese ----------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("新卒エンジニア", Seniority.JUNIOR),
        ("軟體工程師 實習", Seniority.JUNIOR),
        ("シニアエンジニア", Seniority.NOT_JUNIOR),
        ("Software Intern", Seniority.JUNIOR),
    ],
)
def test_cjk_seniority(title: str, expected: Seniority) -> None:
    assert classify_seniority(title, "")[0] == expected


# ---------- tailoring ----------


def _fake_writer(text: str) -> Any:
    seen: dict[str, str] = {}

    def write(system: str, user: str) -> str:
        seen["system"], seen["user"] = system, user
        return text

    return write, seen


JOB = {"Title": "Junior Data Engineer", "Company": "Acme", "Description": "Python, 2 days office"}


def test_tailor_returns_both_documents_and_flags_invented_numbers() -> None:
    client, seen = _fake_writer(
        "<cv># Test Person\n- Built a pipeline for 1,610 jobs, cutting cost 40%</cv>"
        "<cover_letter>Dear Acme, see https://made.up</cover_letter>"
    )
    result = tailor(client, _profile().as_text(), JOB)
    assert result.cv.startswith("# Test Person")
    assert "Dear Acme" in result.cover_letter
    assert any("40%" in w for w in result.warnings)
    assert any("made.up" in w for w in result.warnings)
    assert not any("1610" in w for w in result.warnings)  # in the profile: fine
    assert "Test Person" in seen["user"]
    assert "ONLY facts" in seen["system"]


def test_tailor_errors() -> None:
    def broken(system: str, user: str) -> str:
        raise ConnectionError("down")

    with pytest.raises(TailorError, match="ConnectionError"):
        tailor(broken, "x", JOB)
    client, _ = _fake_writer("<cv>only a cv</cv>")
    with pytest.raises(TailorError, match="missing"):
        tailor(client, "x", JOB)


def test_writer_prefers_claude_then_gemini() -> None:
    from life200.core.config import Settings
    from life200.services.tailor import writer_from_settings

    assert writer_from_settings(Settings(_env_file=None)) is None
    gemini = writer_from_settings(Settings(_env_file=None, gemini_api_key="g"))
    assert gemini is not None
    assert gemini[1] == "gemini-3.8-flash"
    both = Settings(_env_file=None, gemini_api_key="g", anthropic_api_key="a")
    assert writer_from_settings(both)[1].startswith("claude")  # type: ignore[index]


def test_check_facts_accepts_numbers_from_the_job_ad() -> None:
    assert check_facts("Happy to be in the office 2 days", "office 2 days") == []


# ---------- documents ----------


def test_markdown_to_docx_and_back() -> None:
    data = markdown_to_docx("# Name\n\n## Skills\n- **Python**, SQL\nPlain line\n")
    text = read_cv("cv.docx", data)
    assert "Name" in text
    assert "Python, SQL" in text
    assert read_cv("cv.txt", b"hello") == "hello"


# ---------- applications ----------


def _job(db_session: Session) -> JobPostingRow:
    job = JobPostingRow(source="t", source_id="1", title="Junior Dev", url="https://x", raw={})
    db_session.add(job)
    db_session.flush()
    return job


def test_application_tracker(db_session: Session) -> None:
    user = auth.create_user(db_session, "t@example.com", "long enough pw")
    job = _job(db_session)
    save_draft(db_session, user.id, job.id, "cv", "letter", ["w"])
    app = set_status(db_session, user.id, job.id, "applied")
    assert app.applied_at is not None
    assert app.cv == "cv"
    df = list_applications(db_session, user.id)
    assert df.loc[0, "Status"] == "applied"
    with pytest.raises(ValueError, match="unknown status"):
        set_status(db_session, user.id, job.id, "ghosted")


# ---------- Jooble ----------


def test_jooble_search_parses_and_stops_on_empty_page() -> None:
    pages = iter(
        [
            {
                "jobs": [
                    {
                        "id": 7,
                        "title": "<b>新卒</b> エンジニア",
                        "link": "https://jp.jooble.org/x",
                        "company": "Acme",
                        "snippet": "Python",
                        "updated": "2026-11-18T09:00:00",
                    }
                ]
            },
            {"jobs": []},
        ]
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=next(pages))

    client = JoobleClient("tw", "k", http=httpx.Client(transport=httpx.MockTransport(handler)))
    jobs = list(client.search("エンジニア", pages=5))
    assert len(jobs) == 1
    assert len(seen) == 2
    assert jobs[0].country == "tw"
    assert jobs[0].title == "新卒 エンジニア"
    assert seen[0].url.host == "tw.jooble.org"


def test_jooble_bad_key_does_not_leak() -> None:
    client = JoobleClient(
        "tw",
        "secret-key",
        http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))),
    )
    with pytest.raises(JoobleError) as exc_info:
        list(client.search("x"))
    assert "secret-key" not in str(exc_info.value)
    with pytest.raises(ValueError, match="no Jooble host"):
        JoobleClient("us", "k")


def test_blank_keys_count_as_missing() -> None:
    from life200.core.config import Settings

    assert Settings(_env_file=None, anthropic_api_key="  ").anthropic_api_key is None


def test_google_sign_in_creates_then_reuses_the_account(db_session: Session) -> None:
    first = auth.sign_in_with_google(db_session, " New@Gmail.com ", "New Person")
    again = auth.sign_in_with_google(db_session, "new@gmail.com", None)
    assert first.id == again.id
    assert again.auth_provider == "google"
    assert again.plan == "free"
    assert again.name == "New Person"
    assert again.last_login_at is not None
    # A Google account has no password, so password sign-in must fail.
    assert auth.authenticate(db_session, "new@gmail.com", "anything at all") is None

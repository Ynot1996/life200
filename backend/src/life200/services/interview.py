"""Interview preparation: common questions, questions for one company, and answers drafted
from the user's own profile and stories.

Like the CV writer, the AI may only use facts from the profile (and the job ad). Numbers or
names it adds that are in neither are flagged for the user to check.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from life200.db.models import InterviewAnswerRow, InterviewRow
from life200.services.ai_costs import Usage
from life200.services.tailor import TailorError, Writer, check_facts

GENERAL_QUESTIONS = (
    "Tell me about yourself.",
    "Why do you want this role?",
    "Why do you want to work at this company?",
    "What are your greatest strengths?",
    "What is a weakness you are working on?",
    "Tell me about a time you faced a difficult challenge.",
    "Tell me about a time you worked in a team.",
    "Tell me about a time you disagreed with someone. How did you handle it?",
    "Tell me about a time you failed, and what you learned.",
    "Tell me about a project you are proud of.",
    "Tell me about a time you showed leadership.",
    "Where do you see yourself in five years?",
    "Why should we hire you?",
    "Do you have any questions for us?",
)

ANSWER_SYSTEM = """You help one candidate prepare a spoken interview answer.
Rules:
- Use ONLY facts from the candidate's profile (and the job, when given). Never invent jobs,
  numbers, names, dates or results. If the profile has no good example, say so in one line
  and suggest which story the candidate should add to their profile.
- Behavioural questions ("tell me about a time..."): pick the single best story and use STAR
  (Situation, Task, Action, Result), with the result's numbers if the profile has them.
- When a job is given, link the answer to what that job asks for.
- First person, natural spoken English (or the job ad's language), 150-250 words, about
  1-2 minutes aloud. No headings. End with a short line starting "Tip:" on delivery or a
  follow-up the interviewer may ask."""

QUESTIONS_SYSTEM = """You help a candidate prepare for an interview at one company.
From the job description, write the 8 questions this interviewer is most likely to ask:
technical or role-specific ones first, then behavioural ones about what the job needs.
Return ONLY the questions, one per line, no numbering."""


@dataclass(frozen=True, slots=True)
class Draft:
    answer: str
    warnings: list[str]
    usage: Usage | None


def _job_block(interview: InterviewRow | None) -> str:
    if interview is None:
        return ""
    return (
        f"\n\n<job>\nCompany: {interview.company}\nRole: {interview.role}\n"
        f"{interview.job_description}\n</job>"
    )


def draft_answer(
    write: Writer, profile_text: str, question: str, interview: InterviewRow | None = None
) -> Draft:
    if not profile_text.strip():
        raise TailorError("your profile is empty; add your experience and stories first")
    job = _job_block(interview)
    user = f"<profile>\n{profile_text}\n</profile>{job}\n\n<question>{question}</question>"
    try:
        reply, usage = write(ANSWER_SYSTEM, user)
    except TailorError:
        raise
    except Exception as exc:
        raise TailorError(f"the AI service failed: {type(exc).__name__}") from exc
    answer = reply.strip()
    return Draft(answer, check_facts(answer, profile_text + job + question), usage)


def suggest_questions(write: Writer, interview: InterviewRow) -> tuple[list[str], Usage | None]:
    if len(interview.job_description.strip()) < 30:
        raise TailorError("paste the job description first, so the questions fit this job")
    try:
        reply, usage = write(QUESTIONS_SYSTEM, _job_block(interview).strip())
    except Exception as exc:
        raise TailorError(f"the AI service failed: {type(exc).__name__}") from exc
    lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", x).strip() for x in reply.splitlines()]
    return [x for x in lines if len(x) > 8][:10], usage


# ---------- storage ----------


def list_interviews(session: Session, user_id: int) -> list[InterviewRow]:
    return list(
        session.scalars(
            select(InterviewRow)
            .where(InterviewRow.user_id == user_id)
            .order_by(InterviewRow.created_at.desc())
        )
    )


def get_interview(session: Session, user_id: int, interview_id: int) -> InterviewRow | None:
    row = session.get(InterviewRow, interview_id)
    return row if row is not None and row.user_id == user_id else None


def save_interview(
    session: Session, user_id: int, interview_id: int | None, **fields: str
) -> InterviewRow:
    row = get_interview(session, user_id, interview_id) if interview_id else None
    if row is None:
        row = InterviewRow(user_id=user_id)
        session.add(row)
    for name in ("company", "role", "job_description", "when", "notes"):
        if name in fields:
            setattr(row, name, fields[name])
    session.flush()
    return row


def delete_interview(session: Session, user_id: int, interview_id: int) -> None:
    row = get_interview(session, user_id, interview_id)
    if row is not None:
        session.delete(row)


def list_answers(
    session: Session, user_id: int, interview_id: int | None
) -> list[InterviewAnswerRow]:
    where = (
        InterviewAnswerRow.interview_id.is_(None)
        if interview_id is None
        else InterviewAnswerRow.interview_id == interview_id
    )
    return list(
        session.scalars(
            select(InterviewAnswerRow)
            .where(InterviewAnswerRow.user_id == user_id, where)
            .order_by(InterviewAnswerRow.id)
        )
    )


def save_answer(
    session: Session,
    user_id: int,
    interview_id: int | None,
    question: str,
    answer: str,
    warnings: list[str] | None = None,
) -> InterviewAnswerRow:
    """Add the question, or update its answer if it is already there (same wording)."""
    question = question.strip()
    row = next(
        (a for a in list_answers(session, user_id, interview_id) if a.question == question), None
    )
    if row is None:
        row = InterviewAnswerRow(user_id=user_id, interview_id=interview_id, question=question)
        session.add(row)
    row.answer = answer
    if warnings is not None:
        row.warnings = warnings
    session.flush()
    return row


def delete_answer(session: Session, user_id: int, answer_id: int) -> None:
    row = session.get(InterviewAnswerRow, answer_id)
    if row is not None and row.user_id == user_id:
        session.delete(row)

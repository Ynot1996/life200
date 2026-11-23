"""Interview prep: common questions, and questions for each company's interview."""

import streamlit as st

from life200.core.config import get_settings
from life200.db.models import InterviewRow, JobPostingRow
from life200.services.ai_costs import record
from life200.services.applications import list_applications
from life200.services.interview import (
    GENERAL_QUESTIONS,
    delete_answer,
    delete_interview,
    draft_answer,
    get_interview,
    list_answers,
    list_interviews,
    save_answer,
    save_interview,
    suggest_questions,
)
from life200.services.life_store import load_profile
from life200.services.tailor import TailorError, writer_from_settings
from life200.ui.common import session, user_id

st.title("Interview prep")
st.caption(
    "Answers are drafted only from your profile: your experience, projects and **stories**. "
    "The more stories you add on My profile, the better they get. Edit every answer into "
    "your own words, then practise it aloud."
)

with session() as s:
    profile = load_profile(s, user_id())
writer = writer_from_settings(get_settings())
if writer is None:
    st.info("Set LIFE200_GEMINI_API_KEY in .env to draft answers with AI.")
if not any(e.kind == "story" for e in profile.entries):
    st.warning(
        'You have no stories yet. Behavioural questions ("tell me about a time...") need '
        "them: add a few on **My profile → Stories**."
    )


def _question_card(
    question: str,
    answer: str,
    warnings: list[str],
    key: str,
    interview: InterviewRow | None,
    answer_id: int | None,
) -> None:
    """One question: its saved answer, an AI draft button, save and delete."""
    interview_id = interview.id if interview else None
    done = "✅ " if answer.strip() else ""
    with st.expander(f"{done}{question}"):
        if warnings:
            st.warning("Check these, they are not in your profile:\n\n- " + "\n- ".join(warnings))
        text = st.text_area("Your answer", answer, height=220, key=f"ans_{key}")
        c1, c2, c3 = st.columns(3)
        if c1.button("Save", key=f"save_{key}", type="primary"):
            with session() as s, s.begin():
                save_answer(s, user_id(), interview_id, question, text)
            st.rerun()
        if c2.button(
            "✍️ Draft with AI" if not answer else "✍️ Redraft",
            key=f"draft_{key}",
            disabled=writer is None,
        ):
            assert writer is not None
            write, model = writer
            with st.spinner(f"Drafting from your profile with {model}…"):
                try:
                    draft = draft_answer(write, profile.as_text(), question, interview)
                except TailorError as exc:
                    st.error(f"{exc}. Your saved answer was not changed.")
                    return
            with session() as s, s.begin():
                save_answer(s, user_id(), interview_id, question, draft.answer, draft.warnings)
                if draft.usage is not None:
                    record(s, user_id(), "interview", draft.usage)
            st.session_state.pop(f"ans_{key}", None)
            st.rerun()
        if answer_id is not None and c3.button("Delete", key=f"del_{key}"):
            with session() as s, s.begin():
                delete_answer(s, user_id(), answer_id)
            st.rerun()


def _questions(interview: InterviewRow | None, defaults: tuple[str, ...]) -> None:
    """The default questions (not yet saved) followed by the user's saved ones."""
    with session() as s:
        saved = list_answers(s, user_id(), interview.id if interview else None)
        rows = [(a.id, a.question, a.answer, list(a.warnings)) for a in saved]
    prefix = f"i{interview.id}" if interview else "g"
    by_question = {q: r for r in rows for q in [r[1]]}
    for i, q in enumerate(defaults):
        aid, _, ans, warn = by_question.get(q, (None, q, "", []))
        _question_card(q, ans, warn, f"{prefix}_d{i}", interview, aid)
    for aid, q, ans, warn in rows:
        if q not in defaults:
            _question_card(q, ans, warn, f"{prefix}_{aid}", interview, aid)
    with st.form(f"add_q_{prefix}", clear_on_submit=True, border=False):
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        new_q = c1.text_input("Add your own question")
        if c2.form_submit_button("Add") and new_q.strip():
            with session() as s, s.begin():
                save_answer(s, user_id(), interview.id if interview else None, new_q, "")
            st.rerun()


general, company = st.tabs(["Common questions", "My interviews"])

with general:
    st.caption("Questions almost every interview asks. Prepare these once, reuse them everywhere.")
    _questions(None, GENERAL_QUESTIONS)

with company:
    with session() as s:
        interviews = [(i.id, i.company, i.role, i.when) for i in list_interviews(s, user_id())]
    options = [None, *[i[0] for i in interviews]]
    names = {i[0]: " · ".join(x for x in i[1:] if x) or "(untitled)" for i in interviews}
    chosen = st.selectbox(
        "Interview",
        options,
        index=1 if interviews else 0,
        format_func=lambda i: "+ New interview" if i is None else names[i],
    )

    if chosen is None:
        with session() as s:
            apps = list_applications(s, user_id())
        pick = st.selectbox(
            "Start from one of my applications (optional)",
            [None, *apps["Job id"].tolist()],
            format_func=lambda j: (
                "Type it in myself"
                if j is None
                else " — ".join(
                    str(x) for x in apps.loc[apps["Job id"] == j, ["Title", "Company"]].iloc[0]
                )
            ),
        )
        if st.button("Create interview", type="primary"):
            fields = {"company": "", "role": "", "job_description": ""}
            with session() as s, s.begin():
                if pick is not None and (job := s.get(JobPostingRow, int(pick))) is not None:
                    fields = {
                        "company": job.company or "",
                        "role": job.title,
                        "job_description": job.description,
                    }
                save_interview(s, user_id(), None, **fields)
            st.rerun()
        st.stop()

    with session() as s:
        row = get_interview(s, user_id(), chosen)
        assert row is not None
        s.expunge(row)

    with st.expander("Interview details", expanded=not row.company), st.form("details"):
        c1, c2, c3 = st.columns([2, 2, 1])
        company_name = c1.text_input("Company", row.company)
        role = c2.text_input("Role", row.role)
        when = c3.text_input("When", row.when, placeholder="Tue 2 Dec 10:00")
        jd = st.text_area("Job description", row.job_description, height=200)
        notes = st.text_area(
            "Notes", row.notes, height=100, placeholder="Interviewers, format, what you researched"
        )
        if st.form_submit_button("Save details", type="primary"):
            with session() as s, s.begin():
                save_interview(
                    s,
                    user_id(),
                    row.id,
                    company=company_name,
                    role=role,
                    when=when,
                    job_description=jd,
                    notes=notes,
                )
            st.rerun()

    if st.button(
        "💡 Suggest likely questions for this job", disabled=writer is None or not row.company
    ):
        assert writer is not None
        write, model = writer
        with st.spinner(f"Reading the job description with {model}…"):
            try:
                found, usage = suggest_questions(write, row)
            except TailorError as exc:
                st.error(str(exc))
                found, usage = [], None
        if found:
            with session() as s, s.begin():
                existing = {a.question for a in list_answers(s, user_id(), row.id)}
                for q in found:
                    if q not in existing:
                        save_answer(s, user_id(), row.id, q, "")
                if usage is not None:
                    record(s, user_id(), "interview", usage)
            st.rerun()

    st.caption(
        "Questions for this company. Answers here also use the job description, so they "
        "fit this role."
    )
    _questions(row, ())

    if st.button("Delete this interview", icon=":material/delete:"):
        with session() as s, s.begin():
            delete_interview(s, user_id(), row.id)
        st.rerun()

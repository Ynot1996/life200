"""Interview prep: common questions by category, and questions for each company's interview."""

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from life200.core.config import get_settings
from life200.db.models import InterviewRow, JobPostingRow
from life200.services.ai_costs import record
from life200.services.applications import list_applications
from life200.services.interview import (
    DEFAULT_CATEGORY,
    DEFAULT_QUESTIONS,
    OTHER,
    delete_answer,
    delete_interview,
    draft_answers,
    get_interview,
    list_answers,
    list_interviews,
    rename_category,
    save_answer,
    save_interview,
    search,
    suggest_questions,
)
from life200.services.life_store import load_profile
from life200.services.tailor import TailorError, model_choices, writer_from_settings
from life200.ui.common import session, user_id

AUTO = "Automatic (fastest free model)"
NEW = "+ New category"

st.title("Interview prep")
st.caption(
    "Answers are drafted only from your profile: your experience, projects and **stories**. "
    "The more stories you add on My profile, the better they get. Edit every answer into "
    "your own words, then practise it aloud."
)

settings = get_settings()
with session() as s:
    profile = load_profile(s, user_id())
models = model_choices(settings)
if not models:
    st.info("Set LIFE200_GEMINI_API_KEY in .env to draft answers with AI.")
if not any(e.kind == "story" for e in profile.entries):
    st.warning(
        'You have no stories yet. Behavioural questions ("tell me about a time...") need '
        "them: add a few on **My profile → Stories**."
    )

c1, c2, c3 = st.columns([2, 1, 2])
picked_model = c1.selectbox("AI model for drafts", [AUTO, *models], disabled=not models)
how_many = c2.number_input("Drafts per click", 1, 3, 2, help="Several drafts take a bit longer.")
query = c3.text_input("Search questions", placeholder="e.g. team, failure, why")


@dataclass
class Item:
    question: str
    category: str
    answer: str = ""
    warnings: list[str] = field(default_factory=list)
    drafts: list[dict[str, Any]] = field(default_factory=list)
    answer_id: int | None = None


def _items(interview: InterviewRow | None, with_defaults: bool) -> list[Item]:
    with session() as s:
        saved = [
            Item(a.question, a.category or OTHER, a.answer, list(a.warnings), list(a.drafts), a.id)
            for a in list_answers(s, user_id(), interview.id if interview else None)
        ]
    have = {i.question for i in saved}
    defaults = [Item(q, c) for q, c in DEFAULT_CATEGORY.items() if q not in have]
    return (defaults if with_defaults else []) + saved


def _draft(item: Item, interview: InterviewRow | None) -> None:
    model = None if picked_model == AUTO else picked_model
    found = writer_from_settings(settings, model, quick=True)
    assert found is not None
    write, label = found
    with st.spinner(f"Writing {how_many} draft(s) with {label}…"):
        try:
            drafts = draft_answers(write, profile.as_text(), item.question, interview, how_many)
        except TailorError as exc:
            st.error(f"{exc}. Your saved answer was not changed.")
            return
    with session() as s, s.begin():
        save_answer(
            s,
            user_id(),
            interview.id if interview else None,
            item.question,
            category=item.category,
            drafts=[d.as_json() for d in drafts],
        )
        if drafts and drafts[0].usage is not None:
            record(s, user_id(), "interview", drafts[0].usage)
    st.rerun()


def _card(item: Item, key: str, interview: InterviewRow | None, categories: list[str]) -> None:
    interview_id = interview.id if interview else None
    done = "✅ " if item.answer.strip() else ""
    with st.expander(f"{done}{item.question}"):
        if item.drafts:
            st.markdown(f"**AI drafts** ({len(item.drafts)}). Pick one, then edit it below.")
            tabs = st.tabs([f"Draft {i + 1}" for i in range(len(item.drafts))])
            for i, (tab, d) in enumerate(zip(tabs, item.drafts, strict=True)):
                with tab:
                    if d.get("warnings"):
                        st.warning("Not in your profile:\n\n- " + "\n- ".join(d["warnings"]))
                    st.write(d.get("text", ""))
                    st.caption(f"Written by {d.get('model') or 'AI'}")
                    if st.button("Use this draft", key=f"use_{key}_{i}"):
                        with session() as s, s.begin():
                            save_answer(
                                s,
                                user_id(),
                                interview_id,
                                item.question,
                                d.get("text", ""),
                                list(d.get("warnings", [])),
                                category=item.category,
                            )
                        st.session_state.pop(f"ans_{key}", None)
                        st.rerun()
        if item.warnings:
            st.warning(
                "Check these, they are not in your profile:\n\n- " + "\n- ".join(item.warnings)
            )
        text = st.text_area("My answer", item.answer, height=200, key=f"ans_{key}")
        c1, c2, c3, c4 = st.columns([1, 1.3, 2, 1], vertical_alignment="bottom")
        if c1.button("Save", key=f"save_{key}", type="primary"):
            with session() as s, s.begin():
                save_answer(s, user_id(), interview_id, item.question, text, category=item.category)
            st.rerun()
        label = "✍️ Draft with AI" if not item.drafts else "✍️ New drafts"
        if c2.button(label, key=f"draft_{key}", disabled=not models):
            _draft(item, interview)
        move = c3.selectbox(
            "Category",
            categories,
            index=categories.index(item.category) if item.category in categories else 0,
            key=f"cat_{key}",
        )
        if move != item.category:
            with session() as s, s.begin():
                save_answer(s, user_id(), interview_id, item.question, category=move)
            st.rerun()
        if item.answer_id is not None and c4.button("Delete", key=f"del_{key}"):
            with session() as s, s.begin():
                delete_answer(s, user_id(), item.answer_id)
            st.rerun()


def _questions(interview: InterviewRow | None, with_defaults: bool) -> None:
    items = _items(interview, with_defaults)
    defaults = list(DEFAULT_QUESTIONS) if with_defaults else []
    found = sorted({i.category for i in items} - set(defaults) - {OTHER})
    categories = [*defaults, *found, OTHER]
    prefix = f"i{interview.id}" if interview else "g"

    shown = set(search([i.question for i in items], query)) if query else None
    any_shown = False
    for cat in categories:
        in_cat = [i for i in items if i.category == cat and (shown is None or i.question in shown)]
        if not in_cat:
            continue
        any_shown = True
        answered = sum(bool(i.answer.strip()) for i in in_cat)
        st.subheader(f"{cat}  ·  {answered}/{len(in_cat)} ready")
        for n, item in enumerate(in_cat):
            _card(item, f"{prefix}_{item.answer_id or 'd'}_{cat}_{n}", interview, categories)
    if not any_shown:
        st.caption("No questions match." if query else "No questions yet.")

    with (
        st.expander("Add a question or category", icon=":material/add:"),
        st.form(f"add_q_{prefix}", clear_on_submit=True, border=False),
    ):
        new_q = st.text_input("Question")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", [*categories, NEW])
        new_cat = c2.text_input("New category name", help=f'Used when "{NEW}" is chosen')
        if st.form_submit_button("Add") and new_q.strip():
            chosen = new_cat.strip() if cat == NEW else cat
            with session() as s, s.begin():
                save_answer(
                    s,
                    user_id(),
                    interview.id if interview else None,
                    new_q,
                    category=chosen or OTHER,
                )
            st.rerun()
    with (
        st.expander("Rename a category", icon=":material/edit:"),
        st.form(f"rename_{prefix}", border=False),
    ):
        c1, c2 = st.columns(2)
        old = c1.selectbox("Category", [c for c in categories if c != OTHER] or [OTHER])
        new = c2.text_input("New name")
        if st.form_submit_button("Rename") and new.strip():
            with session() as s, s.begin():
                rename_category(s, user_id(), old, new)
            st.rerun()


general, company = st.tabs(["Common questions", "My interviews"])

with general:
    st.caption("Questions almost every interview asks. Prepare these once, reuse them everywhere.")
    _questions(None, with_defaults=True)

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
        "💡 Suggest likely questions for this job", disabled=not models or not row.company
    ):
        found_writer = writer_from_settings(
            settings, None if picked_model == AUTO else picked_model, quick=True
        )
        assert found_writer is not None
        write, label = found_writer
        with st.spinner(f"Reading the job description with {label}…"):
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
                        save_answer(s, user_id(), row.id, q, category="Likely for this job")
                if usage is not None:
                    record(s, user_id(), "interview", usage)
            st.rerun()

    st.caption(
        "Questions for this company. Answers here also use the job description, so they "
        "fit this role."
    )
    _questions(row, with_defaults=False)

    if st.button("Delete this interview", icon=":material/delete:"):
        with session() as s, s.begin():
            delete_interview(s, user_id(), row.id)
        st.rerun()

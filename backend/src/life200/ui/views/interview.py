"""Interview prep: common questions by category, and questions for each company's interview."""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

import streamlit as st

from life200.core.config import get_settings
from life200.db.models import InterviewRoundRow, InterviewRow, JobPostingRow
from life200.services.ai_costs import record
from life200.services.applications import list_applications
from life200.services.interview import (
    DEFAULT_CATEGORY,
    DEFAULT_QUESTIONS,
    GENERAL_QUESTIONS,
    OTHER,
    PRACTICE,
    REAL,
    ROUND_NAMES,
    ROUND_STATUS,
    add_practice,
    delete_answer,
    delete_interview,
    delete_round,
    draft_answers,
    get_interview,
    list_answers,
    list_interviews,
    list_rounds,
    rename_category,
    save_answer,
    save_interview,
    save_round,
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
    round_id: int | None = None
    kind: str = PRACTICE

    def where(self) -> dict[str, Any]:
        return {"round_id": self.round_id, "kind": self.kind}


def _items(
    interview: InterviewRow | None, with_defaults: bool, round_id: int | None, kind: str
) -> list[Item]:
    with session() as s:
        saved = [
            Item(
                a.question,
                a.category or OTHER,
                a.answer,
                list(a.warnings),
                list(a.drafts),
                a.id,
                a.round_id,
                a.kind or PRACTICE,
            )
            for a in list_answers(s, user_id(), interview.id if interview else None)
            if a.round_id == round_id and (a.kind or PRACTICE) == kind
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
            **item.where(),
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
                                **item.where(),
                            )
                        st.session_state.pop(f"ans_{key}", None)
                        st.rerun()
        if item.warnings:
            st.warning(
                "Check these, they are not in your profile:\n\n- " + "\n- ".join(item.warnings)
            )
        label = "What I answered, and how it went" if item.kind == REAL else "My answer"
        text = st.text_area(label, item.answer, height=200, key=f"ans_{key}")
        c1, c2, c3, c4 = st.columns([1, 1.3, 2, 1], vertical_alignment="bottom")
        if c1.button("Save", key=f"save_{key}", type="primary"):
            with session() as s, s.begin():
                save_answer(
                    s,
                    user_id(),
                    interview_id,
                    item.question,
                    text,
                    category=item.category,
                    **item.where(),
                )
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
                save_answer(
                    s, user_id(), interview_id, item.question, category=move, **item.where()
                )
            st.rerun()
        if item.answer_id is not None and c4.button("Delete", key=f"del_{key}"):
            with session() as s, s.begin():
                delete_answer(s, user_id(), item.answer_id)
            st.rerun()


def _questions(
    interview: InterviewRow | None,
    with_defaults: bool,
    round_id: int | None = None,
    kind: str = PRACTICE,
) -> None:
    items = _items(interview, with_defaults, round_id, kind)
    defaults = list(DEFAULT_QUESTIONS) if with_defaults or kind == PRACTICE else []
    found = sorted({i.category for i in items} - set(defaults) - {OTHER})
    categories = [*defaults, *found, OTHER]
    prefix = f"i{interview.id}r{round_id}{kind}" if interview else "g"

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

    title = "Add a question they asked" if kind == REAL else "Add a question or category"
    with (
        st.expander(title, icon=":material/add:"),
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
                    round_id=round_id,
                    kind=kind,
                )
            st.rerun()
    if not with_defaults:
        return
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
        interviews = [(i.id, i.company, i.role) for i in list_interviews(s, user_id())]
    names = {i[0]: " · ".join(x for x in i[1:] if x) or "(untitled)" for i in interviews}
    if "new_interview" in st.session_state:
        st.session_state["pick_interview"] = st.session_state.pop("new_interview")
    chosen = st.selectbox(
        "Interview",
        [None, *names],
        index=1 if interviews else 0,
        format_func=lambda i: "+ New interview" if i is None else names[i],
        key="pick_interview",
    )

    if chosen is None:
        with session() as s:
            apps = list_applications(s, user_id())
        pick = st.selectbox(
            "Fill in from one of my applications (optional)",
            [None, *apps["Job id"].tolist()],
            format_func=lambda j: (
                "Type it in myself"
                if j is None
                else " — ".join(
                    str(x) for x in apps.loc[apps["Job id"] == j, ["Title", "Company"]].iloc[0]
                )
            ),
        )
        job = None
        if pick is not None:
            with session() as s:
                job = s.get(JobPostingRow, int(pick))
                if job is not None:
                    s.expunge(job)
        with st.form(f"new_interview_{pick}"):
            c1, c2 = st.columns(2)
            company_name = c1.text_input("Company *", job.company or "" if job else "")
            role = c2.text_input("Role *", job.title if job else "")
            jd = st.text_area(
                "Job description (optional, makes answers fit the role)",
                job.description if job else "",
                height=150,
            )
            if st.form_submit_button("Create interview", type="primary"):
                if not company_name.strip() or not role.strip():
                    st.error("Add the company and the role.")
                else:
                    with session() as s, s.begin():
                        new = save_interview(
                            s,
                            user_id(),
                            None,
                            company=company_name.strip(),
                            role=role.strip(),
                            job_description=jd,
                        )
                        save_round(s, user_id(), new.id, name=ROUND_NAMES[0])
                        st.session_state["new_interview"] = new.id
                    st.rerun()
        st.stop()

    with session() as s:
        row = get_interview(s, user_id(), chosen)
        assert row is not None
        s.expunge(row)
        rounds = list_rounds(s, user_id(), row.id)
        for r in rounds:
            s.expunge(r)

    with st.expander("Interview details"), st.form("details"):
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Company", row.company)
        role = c2.text_input("Role", row.role)
        jd = st.text_area("Job description", row.job_description, height=200)
        notes = st.text_area(
            "Notes", row.notes, height=100, placeholder="Interviewers, format, what you researched"
        )
        c1, c2 = st.columns([1, 4])
        if c1.form_submit_button("Save details", type="primary"):
            with session() as s, s.begin():
                save_interview(
                    s,
                    user_id(),
                    row.id,
                    company=company_name,
                    role=role,
                    job_description=jd,
                    notes=notes,
                )
            st.rerun()
        if c2.form_submit_button("Delete this interview", icon=":material/delete:"):
            with session() as s, s.begin():
                delete_interview(s, user_id(), row.id)
            st.rerun()

    def _when(r: InterviewRoundRow) -> str:
        if r.on is None:
            return ""
        return r.on.strftime("%a %d %b") + (r.at.strftime(" %H:%M") if r.at else "")

    labels = [
        f"{ROUND_STATUS.get(r.status, '')[:2]} {n + 1}. {r.name or 'Round'}"
        + (f" · {_when(r)}" if _when(r) else "")
        for n, r in enumerate(rounds)
    ]
    tabs = st.tabs([*labels, "+ Add a round"])

    with tabs[-1], st.form("add_round", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        kind_of = c1.selectbox("Round", [*ROUND_NAMES, "Other (type below)"])
        other_name = c1.text_input("Name", placeholder="e.g. Case study with the team")
        day = c2.date_input("Date (optional)", value=None)
        at = c3.time_input("Time (optional)", value=None, step=900)
        if st.form_submit_button("Add round", type="primary"):
            name = other_name.strip() or (kind_of if kind_of in ROUND_NAMES else "Round")
            with session() as s, s.begin():
                save_round(s, user_id(), row.id, name=name, on=day, at=at)
            st.rerun()

    for tab, r in zip(tabs, rounds, strict=False):
        with tab:
            with st.expander("Round details", expanded=False), st.form(f"round_{r.id}"):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1.4])
                name = c1.text_input("Name", r.name)
                day_v: date | None = c2.date_input("Date", value=r.on)
                at_v: time | None = c3.time_input("Time", value=r.at, step=900)
                status = c4.selectbox(
                    "Status",
                    list(ROUND_STATUS),
                    index=list(ROUND_STATUS).index(r.status) if r.status in ROUND_STATUS else 0,
                    format_func=ROUND_STATUS.__getitem__,
                )
                how = st.text_area(
                    "How it went", r.notes, height=80, placeholder="Who you met, what to improve"
                )
                b1, b2 = st.columns([1, 4])
                if b1.form_submit_button("Save", type="primary"):
                    with session() as s, s.begin():
                        save_round(
                            s,
                            user_id(),
                            row.id,
                            r.id,
                            name=name,
                            on=day_v,
                            at=at_v,
                            status=status,
                            notes=how,
                        )
                    st.rerun()
                if b2.form_submit_button("Delete round", icon=":material/delete:"):
                    with session() as s, s.begin():
                        delete_round(s, user_id(), r.id)
                    st.rerun()

            mock, real = st.tabs(["🎯 Practice (mock)", "📝 Real questions asked"])
            with mock:
                st.caption(
                    "Pick the questions to practise for this round. Answers here also use the "
                    "job description, so they fit this role."
                )
                c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
                picks = c1.multiselect(
                    "Add from common questions",
                    list(GENERAL_QUESTIONS),
                    key=f"picks_{r.id}",
                    placeholder="Choose questions (your saved answers come along)",
                )
                if c2.button("Add", key=f"addp_{r.id}", disabled=not picks):
                    with session() as s, s.begin():
                        add_practice(s, user_id(), row.id, r.id, picks)
                    st.session_state.pop(f"picks_{r.id}", None)
                    st.rerun()
                if st.button(
                    "💡 Suggest likely questions for this job",
                    key=f"suggest_{r.id}",
                    disabled=not models,
                ):
                    found_writer = writer_from_settings(
                        settings, None if picked_model == AUTO else picked_model, quick=True
                    )
                    assert found_writer is not None
                    write, wlabel = found_writer
                    with st.spinner(f"Reading the job description with {wlabel}…"):
                        try:
                            found, usage = suggest_questions(write, row)
                        except TailorError as exc:
                            st.error(str(exc))
                            found, usage = [], None
                    if found:
                        with session() as s, s.begin():
                            for q in found:
                                save_answer(
                                    s,
                                    user_id(),
                                    row.id,
                                    q,
                                    category="Likely for this job",
                                    round_id=r.id,
                                )
                            if usage is not None:
                                record(s, user_id(), "interview", usage)
                        st.rerun()
                _questions(row, with_defaults=False, round_id=r.id, kind=PRACTICE)
            with real:
                st.caption(
                    "After the round, write down what they really asked and how you answered. "
                    "Next time, draft a better answer here."
                )
                _questions(row, with_defaults=False, round_id=r.id, kind=REAL)

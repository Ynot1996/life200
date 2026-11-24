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
    LENGTHS,
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
LIKELY = "Likely for this job"

st.title("Interview prep")

settings = get_settings()
with session() as s:
    profile = load_profile(s, user_id())
models = model_choices(settings)

if "_flash" in st.session_state:
    st.toast(st.session_state.pop("_flash"), icon=":material/check:")

with st.expander("How this works", icon=":material/help:", expanded=False):
    st.markdown(
        "1. **Common questions**: prepare answers once for questions almost every interview "
        "asks.\n"
        "2. **My interviews**: add each interview (company, role), then its rounds.\n"
        "3. In a round, **Practice** the questions you pick or the AI suggests. Your saved "
        "answers come along.\n"
        "4. Open a question to write your answer, or **Write with AI** (choose length, give "
        "instructions). Each AI answer is kept as a **version**: pick the best and press "
        "**Use as my answer**.\n"
        "5. After the round, note the **Real questions asked** to track and improve.\n\n"
        "AI uses only your profile (experience, projects, **stories**), never made-up facts."
    )

c1, c2 = st.columns([5, 1], vertical_alignment="center")
query = c1.text_input(
    "Search questions",
    placeholder="Search questions, e.g. team, failure, why",
    label_visibility="collapsed",
    icon=":material/search:",
)
with c2.popover("AI model", icon=":material/tune:", use_container_width=True):
    picked_model = st.selectbox(
        "Model for drafts", [AUTO, *models], disabled=not models, key="ai_model"
    )
if not models:
    st.info("Set LIFE200_GEMINI_API_KEY in .env to draft answers with AI.")
if not any(e.kind == "story" for e in profile.entries):
    st.warning(
        'You have no stories yet. Behavioural questions ("tell me about a time...") need '
        "them: add a few on **My profile → Stories**."
    )


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


def _save(item: Item, interview: InterviewRow | None, **changes: Any) -> None:
    with session() as s, s.begin():
        save_answer(
            s,
            user_id(),
            interview.id if interview else None,
            item.question,
            changes.pop("answer", None),
            changes.pop("warnings", None),
            category=changes.pop("category", item.category),
            drafts=changes.pop("drafts", None),
            **item.where(),
        )


def _toggle(key: str) -> bool:
    """A header that opens and closes, remembered across reruns."""
    return bool(st.session_state.get(key, False))


def _flash(message: str) -> None:
    """Show a short confirmation after the page reloads."""
    st.session_state["_flash"] = message


def _height(text: str) -> int:
    """Tall enough to read the whole answer without scrolling inside the box."""
    lines = sum(max(1, len(line) // 150 + 1) for line in (text or " ").splitlines())
    return max(140, min(900, 26 * lines + 40))


def _generate(item: Item, interview: InterviewRow | None, key: str, base: str) -> None:
    """New AI versions are added to the ones already there; nothing is replaced."""
    count = int(st.session_state.get(f"g_n_{key}", 1))
    length = str(st.session_state.get(f"g_len_{key}", "Medium"))
    wishes = str(st.session_state.get(f"g_ask_{key}", ""))
    model = None if picked_model == AUTO else picked_model
    found = writer_from_settings(settings, model, quick=True)
    assert found is not None
    write, label = found
    with st.spinner(f"Writing {count} version(s) with {label}…"):
        try:
            drafts = draft_answers(
                write,
                profile.as_text(),
                item.question,
                interview,
                count,
                length=length,
                instructions=wishes,
                base=base,
            )
        except TailorError as exc:
            st.error(f"{exc}. Nothing was changed.")
            return
    with session() as s, s.begin():
        save_answer(
            s,
            user_id(),
            interview.id if interview else None,
            item.question,
            category=item.category,
            drafts=item.drafts + [d.as_json() for d in drafts],
            **item.where(),
        )
        if drafts and drafts[0].usage is not None:
            record(s, user_id(), "interview", drafts[0].usage)
    st.session_state[f"view_{key}"] = len(item.drafts) + 1  # open the first new version
    _flash(f"Added {len(drafts)} new version(s).")
    st.rerun()


def _warn(warnings: list[str], key: str) -> None:
    hide = f"hide_warn_{key}"
    if not warnings or st.session_state.get(hide):
        return
    c1, c2 = st.columns([12, 1], vertical_alignment="center")
    c1.warning(
        "Not in your profile, please check: " + "; ".join(warnings), icon=":material/fact_check:"
    )
    if c2.button("", key=f"x_{hide}", icon=":material/close:", help="Hide this note"):
        st.session_state[hide] = True
        st.rerun()


def _confirm_delete(label: str, key: str, what: str) -> bool:
    """A delete button that asks first. True once the user confirms."""
    with st.popover(label, icon=":material/delete:"):
        st.markdown(f"Delete {what}? This cannot be undone.")
        return st.button("Yes, delete", key=key, type="primary")


def _card(item: Item, key: str, interview: InterviewRow | None, categories: list[str]) -> None:
    open_key = f"open_{key}"
    is_open = _toggle(open_key)
    ready = bool(item.answer.strip())
    n = len(item.drafts)
    with st.container(border=True):
        # Header: the question on the left, its category on the right.
        h1, h2 = st.columns([5, 1.4], vertical_alignment="center")
        icon = ":material/check_circle:" if ready else ":material/radio_button_unchecked:"
        extra = f"  ·  :gray[{n} version{'s' if n != 1 else ''}]" if n else ""
        if h1.button(f"**{item.question}**{extra}", key=f"t_{key}", type="tertiary", icon=icon):
            st.session_state[open_key] = not is_open
            st.rerun()
        move = h2.selectbox(
            "Category",
            categories,
            index=categories.index(item.category) if item.category in categories else 0,
            key=f"cat_{key}",
            label_visibility="collapsed",
        )
        if move != item.category:
            _save(item, interview, category=move)
            _flash(f"Moved to {move}.")
            st.rerun()
        if not is_open:
            return

        # Which answer to look at: mine, or one of the versions.
        mine = "What I answered" if item.kind == REAL else "My answer"
        names = [f"⭐ {mine}", *[f"Version {i + 1}" for i in range(n)]]
        view_key = f"view_{key}"
        current = min(int(st.session_state.get(view_key, 0)), n)
        v1, v2 = st.columns([1.3, 6], vertical_alignment="center")
        if v1.button("Blank version", key=f"blank_{key}", icon=":material/add:"):
            _save(item, interview, drafts=[*item.drafts, {"text": "", "warnings": [], "model": ""}])
            st.session_state[view_key] = n + 1
            st.rerun()
        picked = v2.segmented_control(
            "Answers",
            range(n + 1),
            default=current,
            format_func=lambda i: names[i],
            key=f"seg_{key}_{n}",
            label_visibility="collapsed",
        )
        current = current if picked is None else int(picked)
        st.session_state[view_key] = current

        if current == 0:
            _warn(item.warnings, key)
            text = st.text_area(
                mine,
                item.answer,
                height=_height(item.answer),
                key=f"ans_{key}",
                label_visibility="collapsed",
                placeholder="Write your answer, or generate one with AI below.",
            )
        else:
            d = item.drafts[current - 1]
            _warn(list(d.get("warnings", [])), f"{key}_{current}")
            text = st.text_area(
                "Version",
                d.get("text", ""),
                height=_height(d.get("text", "")),
                key=f"ver_{key}_{current}",
                label_visibility="collapsed",
            )
            st.caption(f"Written by {d.get('model') or 'you'}")

        # Actions: save and use on the left, AI in the middle, delete on the right.
        a1, a2, a3, _, a5 = st.columns([0.8, 1.5, 1.4, 1.6, 1.3])
        if a1.button("Save", key=f"save_{key}_{current}", type="primary", icon=":material/save:"):
            if current == 0:
                _save(item, interview, answer=text)
            else:
                drafts = [dict(x) for x in item.drafts]
                drafts[current - 1]["text"] = text
                _save(item, interview, drafts=drafts)
            _flash("Saved.")
            st.rerun()
        if current > 0 and a2.button(
            "Use as my answer", key=f"use_{key}_{current}", icon=":material/star:"
        ):
            d = item.drafts[current - 1]
            _save(item, interview, answer=text, warnings=list(d.get("warnings", [])))
            st.session_state.pop(f"ans_{key}", None)
            st.session_state[view_key] = 0
            _flash("Now your answer.")
            st.rerun()
        with a3.popover("Write with AI", icon=":material/auto_awesome:", disabled=not models):
            st.radio("Length", list(LENGTHS), index=1, horizontal=True, key=f"g_len_{key}")
            st.text_area(
                "Your instructions (optional)",
                key=f"g_ask_{key}",
                height=90,
                placeholder="e.g. sound more confident · mention my SQL work · simpler words",
            )
            rewrite = bool(text.strip()) and st.toggle(
                "Improve the answer I'm looking at",
                key=f"g_base_{key}",
                help="Off: write fresh from your profile.",
            )
            st.number_input("How many versions", 1, 3, 1, key=f"g_n_{key}")
            if st.button("Generate", key=f"gen_{key}", type="primary"):
                _generate(item, interview, key, text if rewrite else "")
        with a5:
            if current > 0:
                if _confirm_delete("Delete version", f"vd_{key}_{current}", "this version"):
                    _save(
                        item, interview, drafts=item.drafts[: current - 1] + item.drafts[current:]
                    )
                    for j in range(current, n + 1):
                        st.session_state.pop(f"ver_{key}_{j}", None)
                    st.session_state[view_key] = 0
                    _flash("Version deleted.")
                    st.rerun()
            elif item.answer_id is not None and _confirm_delete(
                "Delete question", f"del_{key}", "this question and all its versions"
            ):
                with session() as s, s.begin():
                    delete_answer(s, user_id(), item.answer_id)
                st.session_state.pop(open_key, None)
                _flash("Question deleted.")
                st.rerun()


def _toolbar(
    interview: InterviewRow | None,
    prefix: str,
    categories: list[str],
    round_id: int | None,
    kind: str,
    rename: bool,
) -> None:
    c1, c2, _, c4, c5 = st.columns([1.3, 1.5, 3, 1, 1], vertical_alignment="center")
    title = "Add a real question" if kind == REAL else "Add a question"
    with c1.popover(title, icon=":material/add:", type="primary"):
        new_q = st.text_input("Question", key=f"nq_{prefix}")
        cat = st.selectbox("Category", [*categories, NEW], key=f"nc_{prefix}")
        new_cat = st.text_input("Category name", key=f"ncn_{prefix}") if cat == NEW else ""
        if st.button("Add", key=f"add_{prefix}", type="primary", disabled=not new_q.strip()):
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
            for k in (f"nq_{prefix}", f"ncn_{prefix}"):
                st.session_state.pop(k, None)
            st.session_state[f"cat_open_{prefix}_{chosen or OTHER}"] = True
            _flash("Question added.")
            st.rerun()
    if rename:
        with c2.popover("Rename category", icon=":material/edit:"):
            old = st.selectbox(
                "Category", [c for c in categories if c != OTHER] or [OTHER], key=f"ro_{prefix}"
            )
            new = st.text_input("New name", key=f"rn_{prefix}")
            if st.button("Rename", key=f"rb_{prefix}", disabled=not new.strip()):
                with session() as s, s.begin():
                    rename_category(s, user_id(), old, new)
                _flash("Category renamed.")
                st.rerun()
    if c4.button("Open all", key=f"oa_{prefix}", type="tertiary", icon=":material/unfold_more:"):
        for c in categories:
            st.session_state[f"cat_open_{prefix}_{c}"] = True
        st.rerun()
    if c5.button("Close all", key=f"ca_{prefix}", type="tertiary", icon=":material/unfold_less:"):
        for c in categories:
            st.session_state[f"cat_open_{prefix}_{c}"] = False
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
    _toolbar(interview, prefix, categories, round_id, kind, rename=with_defaults)

    shown = set(search([i.question for i in items], query)) if query else None
    any_shown = False
    for cat in categories:
        in_cat = [i for i in items if i.category == cat and (shown is None or i.question in shown)]
        if not in_cat:
            continue
        any_shown = True
        answered = sum(bool(i.answer.strip()) for i in in_cat)
        cat_key = f"cat_open_{prefix}_{cat}"
        is_open = bool(query) or _toggle(cat_key)
        arrow = ":material/expand_more:" if is_open else ":material/chevron_right:"
        colour = "green" if answered == len(in_cat) else "gray"
        if st.button(
            f"#### {cat} &nbsp; :{colour}-badge[{answered}/{len(in_cat)} ready]",
            key=f"h_{cat_key}",
            type="tertiary",
            icon=arrow,
        ):
            st.session_state[cat_key] = not is_open
            st.rerun()
        if is_open:
            for item in in_cat:
                ident = item.answer_id or f"d{GENERAL_QUESTIONS.index(item.question)}"
                _card(item, f"{prefix}_{ident}", interview, categories)
    if not any_shown:
        st.caption("No questions match." if query else "No questions yet. Add one above.")


def _suggest(row: InterviewRow, round_id: int) -> None:
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
            return
    with session() as s, s.begin():
        for q in found:
            save_answer(s, user_id(), row.id, q, category=LIKELY, round_id=round_id)
        if usage is not None:
            record(s, user_id(), "interview", usage)
    st.session_state[f"cat_open_i{row.id}r{round_id}{PRACTICE}_{LIKELY}"] = True
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
            with st.expander("Job description (optional, makes answers fit the role)"):
                jd = st.text_area(
                    "Job description",
                    job.description if job else "",
                    height=450,
                    label_visibility="collapsed",
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

    d1, d2 = st.columns(2)
    with d2.expander("Job description", icon=":material/description:"), st.form("jd"):
        jd = st.text_area(
            "Job description", row.job_description, height=500, label_visibility="collapsed"
        )
        if st.form_submit_button("Save job description", type="primary"):
            with session() as s, s.begin():
                save_interview(s, user_id(), row.id, job_description=jd)
            st.rerun()
    with d1.expander("Interview details", icon=":material/edit:"), st.form("details"):
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Company", row.company)
        role = c2.text_input("Role", row.role)
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
                    notes=notes,
                )
            st.rerun()
        sure_key = f"sure_interview_{row.id}"
        if not st.session_state.get(sure_key):
            if c2.form_submit_button("Delete this interview", icon=":material/delete:"):
                st.session_state[sure_key] = True
                st.rerun()
        elif c2.form_submit_button(
            "Yes, delete the interview, its rounds and questions", type="primary"
        ):
            st.session_state.pop(sure_key)
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
                sure_round = f"sure_round_{r.id}"
                if not st.session_state.get(sure_round):
                    if b2.form_submit_button("Delete round", icon=":material/delete:"):
                        st.session_state[sure_round] = True
                        st.rerun()
                elif b2.form_submit_button("Yes, delete round and its questions", type="primary"):
                    st.session_state.pop(sure_round)
                    with session() as s, s.begin():
                        delete_round(s, user_id(), r.id)
                    st.rerun()

            mock, real = st.tabs(
                [":material/fitness_center: Practice", ":material/assignment: Real questions asked"]
            )
            with mock, st.container(border=True):
                st.markdown("**Build your practice list**")
                st.caption(
                    "Pick common questions (your saved answers come along) or let AI read the job."
                )
                c1, c2, c3 = st.columns([4, 0.7, 2.2], vertical_alignment="bottom")
                picks = c1.multiselect(
                    "Add from common questions",
                    list(GENERAL_QUESTIONS),
                    key=f"picks_{r.id}",
                    placeholder="Choose common questions",
                    label_visibility="collapsed",
                )
                if c2.button(
                    "Add", key=f"addp_{r.id}", disabled=not picks, use_container_width=True
                ):
                    with session() as s, s.begin():
                        added = add_practice(s, user_id(), row.id, r.id, picks)
                    st.session_state.pop(f"picks_{r.id}", None)
                    _flash(f"Added {added} question(s).")
                    st.rerun()
                with session() as s:
                    likely = sum(
                        a.round_id == r.id and a.category == LIKELY
                        for a in list_answers(s, user_id(), row.id)
                    )
                confirm = f"confirm_suggest_{r.id}"
                if c3.button(
                    "Suggest from job description",
                    key=f"suggest_{r.id}",
                    disabled=not models,
                    icon=":material/lightbulb:",
                    use_container_width=True,
                ):
                    if likely:
                        st.session_state[confirm] = True
                    else:
                        _suggest(row, r.id)
                if st.session_state.get(confirm):
                    st.warning(
                        f"You already have {likely} suggested questions for this round. "
                        "Suggest more? Ones you already have are not added twice."
                    )
                    y, n, _ = st.columns([1, 1, 4])
                    if y.button("Yes, suggest more", key=f"yes_{r.id}", type="primary"):
                        st.session_state.pop(confirm)
                        _suggest(row, r.id)
                    if n.button("Cancel", key=f"no_{r.id}"):
                        st.session_state.pop(confirm)
                        st.rerun()
            with mock:
                _questions(row, with_defaults=False, round_id=r.id, kind=PRACTICE)
            with real:
                st.caption(
                    "After the round, write down what they really asked and how you answered. "
                    "Next time, draft a better answer here."
                )
                _questions(row, with_defaults=False, round_id=r.id, kind=REAL)

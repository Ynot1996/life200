"""Read a document, then show the user exactly what would change before anything is saved."""

import streamlit as st

from life200.core.config import get_settings
from life200.domain.life import SECTIONS, LifeEntry, LifeProfile
from life200.services.ai_costs import record
from life200.services.cv_import import import_cv, transcribe
from life200.services.documents import UnsupportedDocumentError, read_document
from life200.services.life_store import save_profile
from life200.services.profile_review import ImportPlan, apply_plan, plan_import
from life200.services.tailor import TailorError, writer_from_settings
from life200.ui.common import session, user_id

PLAN = "import_plan"
SOURCE = "import_source"
CHOICES = {
    "combine": "Combine: keep mine, add the CV's new lines",
    "keep": "Keep mine",
    "theirs": "Use the CV's version",
}


def start_import(name: str, data: bytes, current: LifeProfile) -> None:
    """Read the document with the AI and keep the result as a draft for review."""
    settings = get_settings()
    writer = writer_from_settings(settings)
    if writer is None:
        st.error("Reading documents needs an AI key (LIFE200_GEMINI_API_KEY) in .env.")
        return
    write, model = writer
    try:
        doc = read_document(name, data)
    except UnsupportedDocumentError as exc:
        st.error(str(exc).capitalize() + ".")
        return
    with st.status(f"Reading {name}…", expanded=True) as status:
        try:
            text = doc.text
            if doc.needs_ai_reading:
                st.write("This looks like an image or a scan, so the AI is reading the page…")
                text, usage = transcribe(settings, data, doc.mime)
                _record(usage, "cv_transcribe")
            st.write(f"Finding your details and history with {model} (about 30 seconds)…")
            result = import_cv(write, text)
            _record(result.usage, "cv_import")
            st.write("Checking every line against the document…")
            plan = plan_import(current, result.profile, text, name)
        except TailorError as exc:
            status.update(label="Could not read the document", state="error")
            st.error(f"{str(exc).capitalize()}. Nothing was changed. Please try again in a minute.")
            return
        status.update(label="Ready for your review", state="complete")
    st.session_state[PLAN] = plan
    st.session_state[SOURCE] = (name, text)
    st.rerun()


def _record(usage: object, feature: str) -> None:
    if usage is not None:
        with session() as s, s.begin():
            record(s, user_id(), feature, usage)  # type: ignore[arg-type]


def _entry_head(e: LifeEntry) -> str:
    when = " to ".join(x for x in (e.start, e.end) if x)
    return " · ".join(x for x in (e.title or "(untitled)", e.org, when) if x)


def _section(kind: str) -> str:
    return SECTIONS.get(kind, ("Other", ""))[0]


def render_review(current: LifeProfile) -> bool:
    """Show the pending import, if any. Returns True when a review is on screen."""
    plan: ImportPlan | None = st.session_state.get(PLAN)
    if plan is None:
        return False
    name, text = st.session_state[SOURCE]
    first_time = not current.entries

    st.subheader(f"Review what we found in {name}")
    st.markdown(
        "Nothing is saved yet. Tick what is right, fix anything that is wrong, then save. "
        "Nothing you already have is deleted."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("New", len(plan.new))
    c2.metric("Changed", len(plan.changed))
    c3.metric("Already in profile", plan.unchanged)
    c4.metric("⚠️ Please check", plan.problems)

    if plan.basics:
        st.markdown("#### Basic details")
        for i, b in enumerate(plan.basics):
            label = f"**{b.label}:** {b.theirs}" + (f"  \n_now: {b.mine}_" if b.mine else "")
            b.use_theirs = st.checkbox(label, value=b.use_theirs, key=f"basic_{i}")

    if plan.new:
        st.markdown("#### New" if not first_time else "#### What we found")
        for i, item in enumerate(plan.new):
            flag = "⚠️ " if item.problems else ""
            with st.container(border=True):
                item.add = st.checkbox(
                    f"{flag}**{_section(item.entry.kind)}:** {_entry_head(item.entry)}",
                    value=item.add,
                    key=f"new_add_{i}",
                )
                for problem in item.problems:
                    st.warning(problem.capitalize(), icon="⚠️")
                with st.expander("Edit before saving"):
                    e = item.entry
                    title = st.text_input("Title", e.title, key=f"new_t_{i}")
                    org = st.text_input("Company / school / place", e.org, key=f"new_o_{i}")
                    d1, d2 = st.columns(2)
                    start = d1.text_input("Start", e.start, key=f"new_s_{i}")
                    end = d2.text_input("End", e.end, key=f"new_e_{i}")
                    body = st.text_area("Details", e.text, height=140, key=f"new_x_{i}")
                    item.entry = e.model_copy(
                        update={
                            "title": title,
                            "org": org,
                            "start": start,
                            "end": end,
                            "text": body,
                        }
                    )

    if plan.changed:
        st.markdown("#### Changed")
        st.caption(
            "These match something already in your profile, but the CV says more or differs."
        )
        for i, changed in enumerate(plan.changed):
            with st.container(border=True):
                st.markdown(f"**{_section(changed.mine.kind)}:** {_entry_head(changed.mine)}")
                for problem in changed.problems:
                    st.warning(problem.capitalize(), icon="⚠️")
                left, right = st.columns(2)
                left.caption("Your profile now")
                left.text(changed.mine.text or "(empty)")
                right.caption(f"In {name}")
                right.text(changed.theirs.text or "(empty)")
                changed.choice = st.radio(
                    "What should we keep?",
                    list(CHOICES),
                    index=list(CHOICES).index(changed.choice),
                    format_func=CHOICES.__getitem__,
                    key=f"chg_{i}",
                    horizontal=True,
                )

    with st.expander("The text we read from your document"):
        st.text(text)

    save, cancel = st.columns([1, 1])
    if save.button("Save approved changes", type="primary"):
        source_entry = LifeEntry(kind="cv", title=name, text=text)
        new_profile = apply_plan(current, plan, source_entry)
        with session() as s, s.begin():
            save_profile(s, user_id(), new_profile, reason=f"import {name}")
        added = sum(i.add for i in plan.new)
        st.session_state.pop(PLAN)
        st.session_state.pop(SOURCE)
        st.session_state["import_done"] = (
            f"Saved: {added} new, {len(plan.changed)} reviewed. You can undo this under History."
        )
        st.rerun()
    if cancel.button("Cancel, change nothing"):
        st.session_state.pop(PLAN)
        st.session_state.pop(SOURCE)
        st.rerun()
    return True

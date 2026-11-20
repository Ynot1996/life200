"""My profile: start from a CV, then edit details and each section on its own."""

import streamlit as st

from life200.core.config import get_settings
from life200.domain.life import SECTIONS, LifeEntry, LifeProfile
from life200.services.ai_costs import record
from life200.services.cv_import import import_cv, merge
from life200.services.documents import read_cv
from life200.services.life_store import load_profile, save_profile
from life200.services.tailor import TailorError, writer_from_settings
from life200.ui.common import MARKETS, session, user_id


def _save(profile: LifeProfile) -> None:
    with session() as s, s.begin():
        save_profile(s, user_id(), profile)


def _import(upload: object, current: LifeProfile) -> None:
    writer = writer_from_settings(get_settings())
    if writer is None:
        st.error("CV import needs an AI key (LIFE200_GEMINI_API_KEY) in .env.")
        return
    write, model = writer
    text = read_cv(upload.name, upload.getvalue())  # type: ignore[attr-defined]
    with st.spinner(f"Reading your CV with {model}… (about 30 seconds)"):
        try:
            result = import_cv(write, text)
        except TailorError as exc:
            st.error(str(exc))
            return
    keep_cv = LifeEntry(kind="cv", title=upload.name, text=text)  # type: ignore[attr-defined]
    merged = merge(current, result.profile)
    merged = merged.model_copy(update={"entries": [*merged.entries, keep_cv]})
    with session() as s, s.begin():
        save_profile(s, user_id(), merged)
        if result.usage is not None:
            record(s, user_id(), "cv_import", result.usage)
    st.session_state["imported"] = len(result.profile.entries)
    st.rerun()


with session() as s:
    profile = load_profile(s, user_id())

st.title("My profile")

# ---------- First visit: start from a CV ----------
if not profile.entries:
    st.subheader("Start with your CV")
    st.markdown(
        "Upload your current CV and we fill in your details, experience, projects, education "
        "and skills. You can edit everything afterwards. Nothing is invented: we only copy "
        "what your CV says."
    )
    upload = st.file_uploader("Your CV (PDF or Word)", type=["pdf", "docx", "txt", "md"])
    if upload and st.button("Fill in my profile", type="primary"):
        _import(upload, profile)
    st.caption("No CV yet? Fill in the sections below by hand.")

if count := st.session_state.pop("imported", None):
    st.success(f"Imported {count} entries from your CV. Check each section, then add your stories.")

st.caption(
    "This is the only source of facts for your CVs and cover letters. More detail means "
    "better matches and stronger applications."
)

# ---------- Basic details ----------
with st.expander("Basic details", expanded=not profile.full_name), st.form("basics"):
    c1, c2 = st.columns(2)
    full_name = c1.text_input("Full name", profile.full_name)
    email = c2.text_input("Email", profile.email)
    phone = c1.text_input("Phone", profile.phone)
    location = c2.text_input("Location", profile.location)
    headline = st.text_input(
        "Headline", profile.headline, placeholder="MSc CS graduate, Python, data"
    )
    target_roles = st.text_input("Roles I want", profile.target_roles)
    right_to_work = st.text_input(
        "Right to work", profile.right_to_work, placeholder="e.g. UK Graduate visa until 2028"
    )
    links = st.text_area("Links (one per line)", profile.links, height=80)
    markets = st.multiselect(
        "Markets I want to work in",
        list(MARKETS),
        default=[m for m in profile.markets if m in MARKETS],
        format_func=MARKETS.__getitem__,
    )
    if st.form_submit_button("Save details", type="primary"):
        _save(
            profile.model_copy(
                update={
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "location": location,
                    "headline": headline,
                    "target_roles": target_roles,
                    "right_to_work": right_to_work,
                    "links": links,
                    "markets": markets,
                }
            )
        )
        st.success("Saved.")
        st.rerun()

# ---------- One tab per section, one card per entry ----------
SINGULAR = {
    "job": "experience",
    "project": "project",
    "education": "education",
    "skill": "skill group",
    "story": "story",
    "award": "item",
}
TEXT_LABEL = {
    "job": "What you did and achieved (one bullet per line, with numbers)",
    "project": "What you built, with what, and the result",
    "education": "Grade, modules, dissertation",
    "skill": "Skills (comma separated)",
    "story": "Situation, Task, Action, Result",
    "award": "Details",
}


def _entry_form(kind: str, entry: LifeEntry, key: str) -> LifeEntry | None:
    """Fields for one entry. Returns the edited entry when Save is pressed."""
    with st.form(key, border=False):
        title = st.text_input(
            "Title", entry.title, placeholder="Role, project, degree, skill group…"
        )
        if kind not in ("skill",):
            c1, c2, c3 = st.columns([2, 1, 1])
            org = c1.text_input("Company / school / place", entry.org)
            start = c2.text_input("Start", entry.start, placeholder="2024-06")
            end = c3.text_input("End", entry.end, placeholder="Present")
        else:
            org, start, end = entry.org, entry.start, entry.end
        text = st.text_area(
            TEXT_LABEL[kind], entry.text, height=180 if kind in ("job", "project", "story") else 90
        )
        if st.form_submit_button("Save", type="primary"):
            return LifeEntry(kind=kind, title=title, org=org, start=start, end=end, text=text)
    return None


def _replace(index: int | None, kind: str, new: LifeEntry | None) -> None:
    """Swap (or delete, or append) the `index`-th entry of `kind`, keeping the rest in order."""
    out: list[LifeEntry] = []
    seen = -1
    for e in profile.entries:
        if e.kind == kind:
            seen += 1
            if seen == index:
                if new is not None:
                    out.append(new)
                continue
        out.append(e)
    if index is None and new is not None:
        out.append(new)
    _save(profile.model_copy(update={"entries": out}))
    st.rerun()


tabs = st.tabs(
    [
        f"{label} ({sum(e.kind == kind for e in profile.entries)})"
        for kind, (label, _) in SECTIONS.items()
    ]
)
for tab, (kind, (_label, hint)) in zip(tabs, SECTIONS.items(), strict=True):
    with tab:
        st.caption(hint)
        items = [e for e in profile.entries if e.kind == kind]
        for i, entry in enumerate(items):
            when = " to ".join(x for x in (entry.start, entry.end) if x)
            head = " · ".join(x for x in (entry.title or "(untitled)", entry.org, when) if x)
            with st.expander(head):
                edited = _entry_form(kind, entry, key=f"{kind}_{i}")
                if edited is not None:
                    _replace(i, kind, edited)
                if st.button("Delete", key=f"del_{kind}_{i}", icon=":material/delete:"):
                    _replace(i, kind, None)
        with st.expander(f"Add {SINGULAR[kind]}", icon=":material/add:"):
            added = _entry_form(kind, LifeEntry(kind=kind), key=f"add_{kind}")
            if added is not None and (added.title or added.text):
                _replace(None, kind, added)


# ---------- Later imports ----------
if profile.entries:
    with st.expander("Import another CV"):
        st.caption("Adds anything new from the CV. Nothing you already have is changed or removed.")
        again = st.file_uploader("CV (PDF or Word)", type=["pdf", "docx", "txt", "md"], key="again")
        if again and st.button("Add from this CV"):
            _import(again, profile)

with st.expander("What the CV writer sees"):
    st.text(profile.as_text() or "Nothing yet.")

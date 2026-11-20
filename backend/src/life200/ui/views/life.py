"""My profile: start from a CV, then edit details and each section on its own."""

import pandas as pd
import streamlit as st

from life200.core.config import get_settings
from life200.domain.life import SECTIONS, LifeEntry, LifeProfile
from life200.services.ai_costs import record
from life200.services.cv_import import import_cv, merge
from life200.services.documents import read_cv
from life200.services.life_store import load_profile, save_profile
from life200.services.tailor import TailorError, writer_from_settings
from life200.ui.common import MARKETS, session, user_id

COLUMNS = ["title", "org", "start", "end", "text"]
LABELS = {
    "title": "Title",
    "org": "Company / school",
    "start": "Start",
    "end": "End",
    "text": "Details (results, numbers)",
}


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

# ---------- One tab per section ----------
tabs = st.tabs(
    [
        f"{label} ({sum(e.kind == kind for e in profile.entries)})"
        for kind, (label, _) in SECTIONS.items()
    ]
)
for tab, (kind, (label, hint)) in zip(tabs, SECTIONS.items(), strict=True):
    with tab:
        st.caption(hint)
        rows = [e.model_dump() for e in profile.entries if e.kind == kind]
        table = pd.DataFrame(rows, columns=["kind", *COLUMNS])[COLUMNS]
        if kind in ("skill", "story"):
            table = table[["title", "text"]]
        edited = st.data_editor(
            table,
            num_rows="dynamic",
            width="stretch",
            key=f"section_{kind}",
            column_config={
                c: st.column_config.TextColumn(
                    "Story" if (kind == "story" and c == "text") else LABELS[c],
                    width="large" if c == "text" else "medium",
                )
                for c in table.columns
            },
        )
        if st.button(f"Save {label.lower()}", key=f"save_{kind}"):
            new = [
                LifeEntry(
                    kind=kind, **{str(k): ("" if pd.isna(v) else str(v)) for k, v in row.items()}
                )
                for row in edited.to_dict("records")
                if any(str(v).strip() for v in row.values() if not pd.isna(v))
            ]
            others = [e for e in profile.entries if e.kind != kind]
            _save(profile.model_copy(update={"entries": [*others, *new]}))
            st.success(f"Saved {len(new)} {label.lower()}.")
            st.rerun()

# ---------- Later imports ----------
if profile.entries:
    with st.expander("Import another CV"):
        st.caption("Adds anything new from the CV. Nothing you already have is changed or removed.")
        again = st.file_uploader("CV (PDF or Word)", type=["pdf", "docx", "txt", "md"], key="again")
        if again and st.button("Add from this CV"):
            _import(again, profile)

with st.expander("What the CV writer sees"):
    st.text(profile.as_text() or "Nothing yet.")

import pandas as pd
import streamlit as st

from life200.domain.life import ENTRY_KINDS, LifeEntry, LifeProfile
from life200.services.documents import read_cv
from life200.services.life_store import load_profile, save_profile
from life200.ui.common import MARKETS, session, user_id

st.title("My life")
st.caption(
    "Everything here is the only source of facts for your CVs and cover letters. "
    "Add every job, project, course, award and story, with numbers and results. "
    "More detail means better matches and stronger applications."
)

with session() as s:
    profile = load_profile(s, user_id())

with st.form("basics"):
    c1, c2 = st.columns(2)
    full_name = c1.text_input("Full name", profile.full_name)
    email = c2.text_input("Email", profile.email)
    phone = c1.text_input("Phone", profile.phone)
    location = c2.text_input("Location", profile.location)
    headline = st.text_input(
        "Headline", profile.headline, placeholder="MSc CS graduate, Python, data"
    )
    target_roles = st.text_input("Roles I want", profile.target_roles)
    right_to_work = st.text_input("Right to work", profile.right_to_work)
    links = st.text_area("Links (one per line)", profile.links, height=80)
    markets = st.multiselect(
        "Markets I want to work in",
        list(MARKETS),
        default=[m for m in profile.markets if m in MARKETS],
        format_func=MARKETS.__getitem__,
    )
    st.subheader("Experience, projects, education and stories")
    table = pd.DataFrame(
        [e.model_dump() for e in profile.entries], columns=list(LifeEntry.model_fields)
    )
    edited = st.data_editor(
        table,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "kind": st.column_config.SelectboxColumn(
                "Kind", options=list(ENTRY_KINDS), default="story"
            ),
            "text": st.column_config.TextColumn("What happened (results, numbers)", width="large"),
        },
        key="entries",
    )
    if st.form_submit_button("Save", type="primary"):
        entries = [
            LifeEntry(**{str(k): ("" if pd.isna(v) else str(v)) for k, v in row.items()})
            for row in edited.to_dict("records")
            if any(str(v).strip() for v in row.values() if not pd.isna(v))
        ]
        new = LifeProfile(
            full_name=full_name,
            email=email,
            phone=phone,
            location=location,
            headline=headline,
            target_roles=target_roles,
            right_to_work=right_to_work,
            links=links,
            markets=markets,
            entries=entries,
        )
        with session() as s, s.begin():
            save_profile(s, user_id(), new)
        st.success("Saved.")
        st.rerun()

st.subheader("Import an existing CV")
upload = st.file_uploader("PDF, Word or text", type=["pdf", "docx", "txt", "md"])
if upload and st.button("Add its text to my life"):
    text = read_cv(upload.name, upload.getvalue())
    added = profile.model_copy(
        update={"entries": [*profile.entries, LifeEntry(kind="cv", title=upload.name, text=text)]}
    )
    with session() as s, s.begin():
        save_profile(s, user_id(), added)
    st.success(
        f"Added {len(text):,} characters from {upload.name}. "
        "Split it into entries when you have time."
    )
    st.rerun()

with st.expander("What the CV writer sees"):
    st.text(profile.as_text() or "Nothing yet.")

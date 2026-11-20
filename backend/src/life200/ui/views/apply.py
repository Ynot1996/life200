import streamlit as st

from life200.core.config import get_settings
from life200.services.applications import get_application, save_draft, set_status
from life200.services.documents import markdown_to_docx
from life200.services.life_store import load_profile
from life200.services.matching import rank_jobs
from life200.services.tailor import TailorError, tailor, writer_from_settings
from life200.ui.common import (
    MARKETS,
    SOURCE_CREDIT,
    SPONSOR_LABELS,
    junior_jobs,
    market_filters,
    notes_text,
    session,
    user_id,
)

st.title("Matches and apply")

with session() as s:
    profile = load_profile(s, user_id())
profile_text = profile.as_text()
if not profile.entries:
    st.warning("Your profile is empty. Add your experience on **My profile** first.")
    st.page_link("views/life.py", label="Go to My profile", icon="📝")
    st.stop()

jobs = junior_jobs()
jobs = jobs[jobs["Market"].isin(profile.markets or list(MARKETS))]
with st.sidebar:
    needs_sponsor = st.checkbox("UK: only employers that can sponsor", value=True)
    top_n = st.slider("Show top", 10, 200, 50, step=10)
if needs_sponsor:
    jobs = jobs[(jobs["Market"] != "gb") | jobs["Sponsor"].isin(["licensed", "likely"])]
jobs = market_filters(jobs)
if jobs.empty:
    st.info("No junior jobs in your markets yet. Run `make refresh`.")
    st.stop()

ranked = rank_jobs(profile_text, jobs)
jobs = jobs.assign(
    Match=ranked.scores * 100, Because=ranked.reasons, Notes=jobs["Market notes"].map(notes_text)
)
jobs = jobs.sort_values("Match", ascending=False).head(top_n).reset_index(drop=True)

st.dataframe(
    jobs[
        ["Match", "Title", "Company", "Market", "Sponsor", "Notes", "Because", "Posted", "Link"]
    ].assign(Market=jobs["Market"].map(MARKETS), Sponsor=jobs["Sponsor"].map(SPONSOR_LABELS)),
    hide_index=True,
    width="stretch",
    column_config={
        "Match": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Posted": st.column_config.DateColumn(format="D MMM"),
        "Link": st.column_config.LinkColumn(display_text="Open"),
    },
)
st.caption(SOURCE_CREDIT)

labels = [
    f"{m:.0f}% · {t} — {c or '?'}"
    for m, t, c in zip(jobs["Match"], jobs["Title"], jobs["Company"], strict=True)
]
pick = st.selectbox("Pick a job to apply for", range(len(jobs)), format_func=labels.__getitem__)
job = jobs.iloc[pick]
job_id = int(job["Job id"])

with st.expander("Job description"):
    st.write(job["Description"])

with session() as s:
    app = get_application(s, user_id(), job_id)
    draft = (app.cv, app.cover_letter, list(app.warnings), app.status) if app else None

writer = writer_from_settings(get_settings())
if st.button("✍️ Tailor CV and cover letter", type="primary", disabled=writer is None):
    assert writer is not None
    write, model = writer
    with st.spinner(f"Writing from your life profile with {model}… (about a minute)"):
        try:
            result = tailor(write, profile_text, {str(k): v for k, v in job.to_dict().items()})
        except TailorError as exc:
            st.error(str(exc))
            st.stop()
    with session() as s, s.begin():
        save_draft(s, user_id(), job_id, result.cv, result.cover_letter, result.warnings)
    st.rerun()
if writer is None:
    st.info("Set LIFE200_GEMINI_API_KEY or LIFE200_ANTHROPIC_API_KEY in .env to write CVs.")

if draft:
    cv, letter, warnings, status = draft
    if warnings:
        st.warning(
            "Check these before sending. They are not in your profile:\n\n- "
            + "\n- ".join(warnings)
        )
    tab_cv, tab_letter = st.tabs(["CV", "Cover letter"])
    cv = tab_cv.text_area("CV (Markdown, edit freely)", cv, height=500)
    letter = tab_letter.text_area("Cover letter", letter, height=400)
    c1, c2, c3 = st.columns(3)
    if c1.button("Save edits"):
        with session() as s, s.begin():
            save_draft(s, user_id(), job_id, cv, letter, warnings)
        st.success("Saved.")
    name = (profile.full_name or "CV").replace(" ", "_")
    c2.download_button("CV.docx", markdown_to_docx(cv), f"{name}_CV.docx")
    c3.download_button("Cover letter.docx", markdown_to_docx(letter), f"{name}_Cover_Letter.docx")

    st.divider()
    st.markdown(
        f"**Status: {status}.** Applying happens on the employer's site, which needs your own "
        "login and often a CAPTCHA, so open it, upload the two files, then mark it applied."
    )
    a1, a2 = st.columns(2)
    a1.link_button("🚀 Open application page", job["Link"], type="primary")
    if a2.button("✅ I applied"):
        with session() as s, s.begin():
            set_status(s, user_id(), job_id, "applied")
        st.rerun()

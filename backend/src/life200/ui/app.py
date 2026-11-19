"""Life200 jobs table (Streamlit).

Run from the project folder:  make app
"""

from datetime import UTC, datetime, timedelta

import pandas as pd
import streamlit as st

from life200.db.session import get_engine
from life200.services.jobs_view import load_jobs

SPONSOR_LABELS = {
    "licensed": "✅ Licensed",
    "likely": "🟡 Likely",
    "agency": "🏢 Agency",
    "training": "🎓 Paid course",
    "not_found": "❌ Not found",
    "unknown": "❔ Unknown",
}
LEVEL_LABELS = {"junior": "🌱 Junior", "unclear": "❔ Unclear", "not_junior": "⛔ Not junior"}

st.set_page_config(page_title="Life200 — UK junior tech jobs", page_icon="🔎", layout="wide")


@st.cache_data(ttl=300)
def jobs() -> pd.DataFrame:
    return load_jobs(get_engine())


df = jobs()
st.title("UK junior tech jobs")
st.caption(
    "Sponsor = whether the employer is on the Home Office register of licensed sponsors. "
    "A licence means the employer *can* sponsor, not that it will for this role."
)

if df.empty:
    st.info("No jobs yet. Run `make refresh` in the project folder, then reload this page.")
    st.stop()

# ---------- Filters ----------
with st.sidebar:
    st.header("Filters")
    query = st.text_input("Search title or company")
    sponsor_pick = st.multiselect(
        "Sponsor",
        options=list(SPONSOR_LABELS),
        default=["licensed", "likely"],
        format_func=SPONSOR_LABELS.__getitem__,
    )
    level_pick = st.multiselect(
        "Level",
        options=list(LEVEL_LABELS),
        default=["junior", "unclear"],
        format_func=LEVEL_LABELS.__getitem__,
    )
    days = st.slider("Posted within (days)", 1, 60, 30)
    min_salary = st.number_input("Minimum salary (£)", min_value=0, step=1000, value=0)
    include_estimated = st.checkbox("Include estimated salaries", value=True)

view = df[df["Sponsor"].isin(sponsor_pick) & df["Level"].isin(level_pick)]
cutoff = datetime.now(UTC) - timedelta(days=days)
view = view[view["Posted"].isna() | (view["Posted"] >= cutoff)]
if query:
    text = view["Title"].str.contains(query, case=False, na=False) | view["Company"].str.contains(
        query, case=False, na=False
    )
    view = view[text]
if min_salary:
    pay = view["Salary to"].fillna(view["Salary from"])
    view = view[pay >= min_salary]
if not include_estimated:
    view = view[~view["Salary estimated"]]

# ---------- Summary ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Jobs shown", len(view))
c2.metric("Jobs saved", len(df))
c3.metric("Licensed sponsor", f"{(df['Sponsor'] == 'licensed').mean():.0%}")
c4.metric("Truly junior", f"{(df['Level'] == 'junior').mean():.0%}")

# ---------- Table ----------
table = view.assign(
    Sponsor=view["Sponsor"].map(SPONSOR_LABELS),
    Level=view["Level"].map(LEVEL_LABELS),
)
st.dataframe(
    table.drop(columns=["Description", "Register name"]),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Posted": st.column_config.DateColumn(format="D MMM"),
        "Salary from": st.column_config.NumberColumn(format="£%d"),
        "Salary to": st.column_config.NumberColumn(format="£%d"),
        "Salary estimated": st.column_config.CheckboxColumn("Est."),
        "Link": st.column_config.LinkColumn("Link", display_text="Open"),
    },
)
st.caption("Jobs by [Adzuna](https://www.adzuna.co.uk)")

# ---------- Detail ----------
st.subheader("Job details")
if not view.empty:
    labels = (view["Title"] + " — " + view["Company"].fillna("?")).tolist()
    pick = st.selectbox("Pick a job", range(len(view)), format_func=labels.__getitem__)
    job = view.iloc[pick]
    st.markdown(f"**{job['Title']}** at **{job['Company'] or '?'}**, {job['Location'] or ''}")
    st.markdown(
        f"Sponsor: {SPONSOR_LABELS[job['Sponsor']]}"
        + (f" (register: *{job['Register name']}*)" if job["Register name"] else "")
        + f" · Level: {LEVEL_LABELS[job['Level']]} — {job['Why']}"
    )
    st.write(job["Description"])
    st.link_button("Open on Adzuna", job["Link"])

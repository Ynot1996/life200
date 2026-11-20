from datetime import UTC, datetime, timedelta

import streamlit as st

from life200.ui.common import MARKETS, SOURCE_CREDIT, SPONSOR_LABELS, junior_jobs

df = junior_jobs()
st.title("Junior and intern jobs")
st.caption(
    "Only roles whose title says junior, graduate, intern, trainee or similar (and that do not "
    "ask for more than a year of experience). Sponsor applies to UK jobs only."
)
if df.empty:
    st.info("No jobs yet. Run `make refresh` in the project folder, then reload.")
    st.stop()

with st.sidebar:
    query = st.text_input("Search title or company")
    market_pick = st.multiselect(
        "Market", list(MARKETS), default=list(MARKETS), format_func=MARKETS.__getitem__
    )
    sponsor_pick = st.multiselect(
        "Sponsor (UK)",
        list(SPONSOR_LABELS),
        default=["licensed", "likely", "not_uk"],
        format_func=SPONSOR_LABELS.__getitem__,
    )
    days = st.slider("Posted within (days)", 1, 60, 30)

view = df[df["Market"].isin(market_pick) & df["Sponsor"].isin(sponsor_pick)]
cutoff = datetime.now(UTC) - timedelta(days=days)
view = view[view["Posted"].isna() | (view["Posted"] >= cutoff)]
if query:
    hit = view["Title"].str.contains(query, case=False, na=False) | view["Company"].str.contains(
        query, case=False, na=False
    )
    view = view[hit]

cols = st.columns(len(MARKETS) + 1)
cols[0].metric("Shown", len(view))
for col, (code, label) in zip(cols[1:], MARKETS.items(), strict=True):
    col.metric(label, int((df["Market"] == code).sum()))

st.dataframe(
    view.assign(
        Sponsor=view["Sponsor"].map(SPONSOR_LABELS), Market=view["Market"].map(MARKETS)
    ).drop(columns=["Description", "Register name", "Level", "Job id"]),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Posted": st.column_config.DateColumn(format="D MMM"),
        "Salary from": st.column_config.NumberColumn(format="%d"),
        "Salary to": st.column_config.NumberColumn(format="%d"),
        "Salary estimated": st.column_config.CheckboxColumn("Est."),
        "Link": st.column_config.LinkColumn("Link", display_text="Open"),
    },
)
st.caption(SOURCE_CREDIT + ". Salaries are in each market's own currency.")
st.page_link("views/apply.py", label="Find my best matches and apply →", icon="🎯")

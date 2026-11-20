import streamlit as st

from life200.services.applications import STATUSES, list_applications, set_status
from life200.ui.common import MARKETS, session, user_id

st.title("My applications")
with session() as s:
    df = list_applications(s, user_id())
if df.empty:
    st.info("Nothing yet. Tailor a CV on **Matches and apply**.")
    st.stop()

counts = df["Status"].value_counts()
for col, status in zip(st.columns(len(STATUSES)), STATUSES, strict=True):
    col.metric(status.title(), int(counts.get(status, 0)))

edited = st.data_editor(
    df.assign(Market=df["Market"].map(MARKETS)),
    hide_index=True,
    use_container_width=True,
    disabled=["Job id", "Title", "Company", "Market", "Applied", "Link"],
    column_config={
        "Status": st.column_config.SelectboxColumn(options=list(STATUSES)),
        "Applied": st.column_config.DatetimeColumn(format="D MMM YYYY"),
        "Link": st.column_config.LinkColumn(display_text="Open"),
    },
)
changed = edited[edited["Status"] != df["Status"]]
if not changed.empty:
    with session() as s, s.begin():
        for row in changed.itertuples():
            set_status(s, user_id(), int(row[1]), str(row.Status))
    st.rerun()

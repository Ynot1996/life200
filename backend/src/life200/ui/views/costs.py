"""Admin only: what the AI has cost, per application and per user, to set credit prices."""

import streamlit as st

from life200.db.session import get_engine
from life200.services.ai_costs import usage_table

if not st.session_state.get("is_admin"):
    st.error("Admins only.")
    st.stop()

st.title("AI costs")
st.caption(
    "List prices in US dollars. Gemini's free tier bills $0, but this is what a paid "
    "deployment would spend. Use the average cost per application to price credits."
)
df = usage_table(get_engine())
if df.empty:
    st.info("No AI calls recorded yet. Tailor an application to see its cost.")
    st.stop()

tailor = df[df["Feature"] == "tailor"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Applications tailored", len(tailor))
c2.metric("Total cost", f"${df['Cost (USD)'].sum():.4f}")
c3.metric("Average per application", f"${tailor['Cost (USD)'].mean():.4f}" if len(tailor) else "-")
c4.metric("Users", df["User"].nunique())

st.subheader("Per user")
per_user = (
    df.groupby("User")
    .agg(
        Calls=("Model", "size"),
        Cost=("Cost (USD)", "sum"),
        Tokens_in=("Tokens in", "sum"),
        Tokens_out=("Tokens out", "sum"),
    )
    .sort_values("Cost", ascending=False)
)
st.dataframe(
    per_user, width="stretch", column_config={"Cost": st.column_config.NumberColumn(format="$%.4f")}
)

st.subheader("Per model")
st.dataframe(
    df.groupby("Model").agg(
        Calls=("Model", "size"),
        Average=("Cost (USD)", "mean"),
        Avg_tokens_in=("Tokens in", "mean"),
        Avg_tokens_out=("Tokens out", "mean"),
    ),
    width="stretch",
    column_config={"Average": st.column_config.NumberColumn(format="$%.4f")},
)

st.subheader("Every call")
st.dataframe(
    df,
    hide_index=True,
    width="stretch",
    column_config={
        "When": st.column_config.DatetimeColumn(format="D MMM HH:mm"),
        "Cost (USD)": st.column_config.NumberColumn(format="$%.5f"),
    },
)

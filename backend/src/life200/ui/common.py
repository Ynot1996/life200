"""Shared helpers for the Streamlit pages."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from life200.db.session import get_engine, get_sessionmaker
from life200.services.jobs_view import load_jobs

SPONSOR_LABELS = {
    "licensed": "✅ Licensed",
    "likely": "🟡 Likely",
    "agency": "🏢 Agency",
    "training": "🎓 Paid course",
    "not_found": "❌ Not found",
    "unknown": "❔ Unknown",
    "not_uk": "— Outside UK",
}
MARKETS = {"gb": "🇬🇧 UK", "sg": "🇸🇬 Singapore", "jp": "🇯🇵 Japan", "tw": "🇹🇼 Taiwan"}
SOURCE_CREDIT = (
    "Jobs by [Adzuna](https://www.adzuna.co.uk), [Japan Dev](https://japan-dev.com) "
    "and [Jooble](https://jooble.org)"
)


@st.cache_data(ttl=300)
def junior_jobs() -> pd.DataFrame:
    """Only junior and intern roles: everything unclear or senior is left out."""
    df = load_jobs(get_engine())
    return df[df["Level"] == "junior"].reset_index(drop=True)


def google_configured() -> bool:
    """True when secrets.toml has a filled-in [auth.google], so st.login("google") works."""
    try:
        google = st.secrets.get("auth", {}).get("google", {})
    except FileNotFoundError:  # no secrets.toml at all
        return False
    return bool(google.get("client_id")) and bool(google.get("client_secret"))


def signed_in() -> bool:
    return "user_id" in st.session_state


def session() -> Session:
    new: Session = get_sessionmaker()()
    return new


def user_id() -> int:
    uid: int = st.session_state["user_id"]
    return uid


def _has(df: pd.DataFrame, flag: str) -> pd.Series:
    return df["Flags"].apply(lambda flags: flag in (flags or []))


def market_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Sidebar switches for each market's own rules. Defaults favour a foreign junior."""
    markets = set(df["Market"])
    with st.sidebar:
        if "jp" in markets:
            st.markdown("**🇯🇵 Japan**")
            if st.checkbox("Hide jobs that need Japanese", value=True):
                df = df[~((df["Market"] == "jp") & _has(df, "japanese_required"))]
            if st.checkbox("Only jobs open to applicants abroad", value=True):
                df = df[(df["Market"] != "jp") | _has(df, "overseas_ok")]
        if "tw" in markets:
            st.markdown("**🇹🇼 Taiwan**")
            if st.checkbox("Hide jobs asking for a top university", value=True):
                df = df[~((df["Market"] == "tw") & _has(df, "elite_school"))]
        if "sg" in markets:
            st.markdown("**🇸🇬 Singapore**")
            if st.checkbox("Hide citizens/PR-only jobs", value=True):
                df = df[~((df["Market"] == "sg") & _has(df, "local_only"))]
            if st.checkbox("Hide pay below the Employment Pass minimum", value=True):
                df = df[~((df["Market"] == "sg") & _has(df, "below_ep"))]
            if st.checkbox("Hide jobs with no salary", value=False):
                df = df[~((df["Market"] == "sg") & _has(df, "ep_unknown"))]
        if st.checkbox("Highest pay first", value=False):
            df = df.sort_values("Pay per year", ascending=False, na_position="last")
    return df


def notes_text(notes: object) -> str:
    return "; ".join(notes) if isinstance(notes, list) else ""

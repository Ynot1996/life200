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
SOURCE_CREDIT = "Jobs by [Adzuna](https://www.adzuna.co.uk) and [Jooble](https://jooble.org)"


@st.cache_data(ttl=300)
def junior_jobs() -> pd.DataFrame:
    """Only junior and intern roles: everything unclear or senior is left out."""
    df = load_jobs(get_engine())
    return df[df["Level"] == "junior"].reset_index(drop=True)


def session() -> Session:
    new: Session = get_sessionmaker()()
    return new


def user_id() -> int:
    uid: int = st.session_state["user_id"]
    return uid

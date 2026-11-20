"""Read saved jobs as a pandas table for the Streamlit app."""

import pandas as pd
from sqlalchemy import Engine, select

from life200.db.models import JobPostingRow

COLUMNS = {
    "posted_at": "Posted",
    "title": "Title",
    "company": "Company",
    "location": "Location",
    "salary_min": "Salary from",
    "salary_max": "Salary to",
    "salary_is_predicted": "Salary estimated",
    "sponsor_status": "Sponsor",
    "sponsor_match": "Register name",
    "seniority": "Level",
    "seniority_reason": "Why",
    "source": "Source",
    "url": "Link",
    "description": "Description",
}


def load_jobs(engine: Engine) -> pd.DataFrame:
    stmt = select(*(getattr(JobPostingRow, c) for c in COLUMNS)).order_by(
        JobPostingRow.posted_at.desc().nulls_last()
    )
    with engine.connect() as conn:
        df = pd.DataFrame(conn.execute(stmt).mappings().all(), columns=list(COLUMNS))
    for col in ("salary_min", "salary_max"):
        df[col] = pd.to_numeric(df[col])
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True)
    return df.rename(columns=COLUMNS)

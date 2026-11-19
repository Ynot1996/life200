"""A job posting, in one shape no matter which platform it came from.

Every job source (Adzuna now, Reed later) converts its own format into `JobPosting`,
so the rest of the app never needs to know where a job came from.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from life200.domain.profile import DomainModel


class JobPosting(DomainModel):
    source: str  # the platform, e.g. "adzuna"
    source_id: str  # the platform's own id for this job
    title: str = Field(min_length=1)
    company: str | None = None
    location: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_is_predicted: bool = False  # True when the platform estimated the salary
    contract_type: str | None = None  # "permanent", "contract"…
    contract_time: str | None = None  # "full_time", "part_time"
    category: str | None = None  # the platform's job category, e.g. "IT Jobs"
    description: str = ""
    url: str
    posted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)  # the original response, kept for re-parsing

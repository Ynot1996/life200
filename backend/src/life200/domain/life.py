"""The life profile: everything about a user, written once and reused for every application.

It is deliberately loose (free text entries) so people can paste their whole story. The
tailoring step may only *select and reword* what is here, never add to it.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

ENTRY_KINDS = ("job", "education", "project", "award", "skill", "story", "cv")

# The profile page shows one section per kind, in this order.
SECTIONS = {
    "job": ("Experience", "Jobs, internships, part-time work and volunteering."),
    "project": (
        "Projects",
        "Personal, university or open-source projects. Say what you built and what it achieved.",
    ),
    "education": ("Education", "Degrees, courses and certificates."),
    "skill": (
        "Skills",
        "One row per group, e.g. Title: Programming, Details: Python, SQL, pandas.",
    ),
    "story": (
        "Stories",
        "Moments that show who you are, for cover letters and interviews: a challenge, what "
        "you did, and the result (the STAR method). The CV import does not fill these: they "
        "are yours to write.",
    ),
    "award": ("Awards and other", "Awards, scholarships, languages, publications, anything else."),
}


class LifeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    kind: str = "story"  # one of ENTRY_KINDS
    title: str = ""  # "Data Analyst Intern", "MSc Computer Science"
    org: str = ""  # company, school or place
    start: str = ""  # free text, e.g. "2024-06"
    end: str = ""
    text: str = ""  # what happened, results, numbers, feelings: the more the better


class MarketDetails(BaseModel):
    """Contact details for one market. Blank fields fall back to the profile's defaults."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    phone: str = ""  # e.g. a local SIM: +65 ...
    location: str = ""  # "Singapore (relocating June 2027)"
    right_to_work: str = ""  # "Needs an Employment Pass"


class LifeProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    first_name: str = ""
    last_name: str = ""
    preferred_name: str = ""  # what people call you, e.g. "Tony"; shown on CVs if set
    email: str = ""
    phone: str = ""  # default for every market
    location: str = ""
    links: str = ""  # GitHub, LinkedIn, portfolio, one per line
    headline: str = ""  # "MSc CS graduate, Python and data"
    target_roles: str = ""  # "data analyst, ML engineer, backend developer"
    markets: list[str] = Field(default_factory=lambda: ["gb"])  # gb, sg, jp, tw
    right_to_work: str = ""  # "UK Graduate visa until 2028; needs sponsorship after"
    market_details: dict[str, MarketDetails] = Field(default_factory=dict)  # per market
    active_market: str = ""  # the market the user is applying in now
    entries: list[LifeEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _split_full_name(cls, data: Any) -> Any:
        """Profiles saved before names were split keep working: "Alex Doe" -> Alex, Doe."""
        if isinstance(data, dict) and data.get("full_name") and not data.get("first_name"):
            first, _, last = str(data["full_name"]).strip().partition(" ")
            data = {**data, "first_name": first, "last_name": data.get("last_name") or last}
        return data

    @property
    def full_name(self) -> str:
        """The name on a CV: preferred name if set, e.g. "Tony Kang"."""
        return " ".join(x for x in (self.preferred_name or self.first_name, self.last_name) if x)

    def details_for(self, market: str | None) -> MarketDetails:
        """Phone, location and right to work for one market, falling back to the defaults."""
        own = self.market_details.get(market or "") or MarketDetails()
        return MarketDetails(
            phone=own.phone or self.phone,
            location=own.location or self.location,
            right_to_work=own.right_to_work or self.right_to_work,
        )

    def as_text(self, market: str | None = None) -> str:
        """The whole profile as plain text: the only facts the tailoring step may use.

        Contact details are those for `market` (default: the market chosen now). Raw
        imported CV text is left out once the CV has been split into entries, so the same
        facts are not given twice.
        """
        return self._as_text(
            market if market is not None else self.active_market,
            include_raw_cv=not any(e.kind != "cv" for e in self.entries),
        )

    def _as_text(self, market: str, include_raw_cv: bool) -> str:
        d = self.details_for(market)
        legal = " ".join(x for x in (self.first_name, self.last_name) if x)
        lines = [
            f"Name: {self.full_name}",
            f"Legal name: {legal if legal != self.full_name else ''}",
            f"Email: {self.email}",
            f"Phone: {d.phone}",
            f"Location: {d.location}",
            f"Links: {self.links}",
            f"Headline: {self.headline}",
            f"Target roles: {self.target_roles}",
            f"Right to work: {d.right_to_work}",
        ]
        for e in self.entries:
            if e.kind == "cv" and not include_raw_cv:
                continue
            when = " to ".join(x for x in (e.start, e.end) if x)
            head = " | ".join(x for x in (e.kind.upper(), e.title, e.org, when) if x)
            lines += ["", head, e.text]
        return "\n".join(line for line in lines if line.split(":", 1)[-1].strip())

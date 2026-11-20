"""The life profile: everything about a user, written once and reused for every application.

It is deliberately loose (free text entries) so people can paste their whole story. The
tailoring step may only *select and reword* what is here, never add to it.
"""

from pydantic import BaseModel, ConfigDict, Field

ENTRY_KINDS = ("job", "education", "project", "award", "skill", "story", "cv")


class LifeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    kind: str = "story"  # one of ENTRY_KINDS
    title: str = ""  # "Data Analyst Intern", "MSc Computer Science"
    org: str = ""  # company, school or place
    start: str = ""  # free text, e.g. "2024-06"
    end: str = ""
    text: str = ""  # what happened, results, numbers, feelings: the more the better


class LifeProfile(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: str = ""  # GitHub, LinkedIn, portfolio, one per line
    headline: str = ""  # "MSc CS graduate, Python and data"
    target_roles: str = ""  # "data analyst, ML engineer, backend developer"
    markets: list[str] = Field(default_factory=lambda: ["gb"])  # gb, sg, jp, tw
    right_to_work: str = ""  # "UK Graduate visa until 2028; needs sponsorship after"
    entries: list[LifeEntry] = Field(default_factory=list)

    def as_text(self) -> str:
        """The whole profile as plain text: the only facts the tailoring step may use."""
        lines = [
            f"Name: {self.full_name}",
            f"Email: {self.email}",
            f"Phone: {self.phone}",
            f"Location: {self.location}",
            f"Links: {self.links}",
            f"Headline: {self.headline}",
            f"Target roles: {self.target_roles}",
            f"Right to work: {self.right_to_work}",
        ]
        for e in self.entries:
            when = " to ".join(x for x in (e.start, e.end) if x)
            head = " | ".join(x for x in (e.kind.upper(), e.title, e.org, when) if x)
            lines += ["", head, e.text]
        return "\n".join(line for line in lines if line.split(":", 1)[-1].strip())

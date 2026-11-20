"""Turn an uploaded CV into a structured life profile, so a new user starts with their
details, experience, projects, education and skills already filled in.

The AI only copies what the CV says: it must not invent anything. Stories are left empty on
purpose, since a CV rarely contains them.
"""

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from life200.domain.life import LifeEntry, LifeProfile
from life200.services.ai_costs import Usage
from life200.services.tailor import TailorError, Writer

SYSTEM = """You extract a CV into JSON. Copy facts only; never invent or improve anything.

Return ONLY a JSON object with these keys (use "" or [] when the CV does not say):
{
  "full_name": "", "email": "", "phone": "", "location": "",
  "links": "one URL per line", "headline": "the CV's own summary line, if any",
  "right_to_work": "visa or work permission, only if the CV states it",
  "entries": [
    {"kind": "job" | "project" | "education" | "skill" | "award",
     "title": "role, project name, degree, skill group or award",
     "org": "company, school, or place",
     "start": "as written, e.g. 2024-06 or Sep 2023", "end": "as written, or Present",
     "text": "all the CV's bullet points for this entry, one per line, word for word"}
  ]
}
Rules: one entry per job, internship, project, degree and award. Skills: one entry per group
the CV uses (title = group name, text = the skills, comma separated). Languages, certificates
and publications go in "award". Keep numbers exactly as written. Keep the CV's language."""


@dataclass(frozen=True, slots=True)
class Imported:
    profile: LifeProfile
    usage: Usage | None


def import_cv(write: Writer, cv_text: str) -> Imported:
    if len(cv_text.strip()) < 50:
        raise TailorError("could not read enough text from that file; is it a scanned image?")
    try:
        reply, usage = write(SYSTEM, f"<cv>\n{cv_text}\n</cv>")
    except Exception as exc:
        raise TailorError(f"the AI service failed: {type(exc).__name__}") from exc
    try:
        data = json.loads(_json_part(reply))
        profile = LifeProfile.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise TailorError("the AI reply was not a readable profile; please try again") from exc
    entries = [
        e for e in profile.entries if e.kind in {"job", "project", "education", "skill", "award"}
    ]
    return Imported(profile.model_copy(update={"entries": entries}), usage)


def _json_part(reply: str) -> str:
    """The JSON object in a reply, even when wrapped in ```json fences or prose."""
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    return m.group(0) if m else reply


def merge(current: LifeProfile, imported: LifeProfile) -> LifeProfile:
    """Fill empty basics from the import and add its entries; keep everything already there."""
    basics = {
        name: getattr(imported, name)
        for name in (
            "full_name",
            "email",
            "phone",
            "location",
            "links",
            "headline",
            "right_to_work",
        )
        if not getattr(current, name) and getattr(imported, name)
    }
    seen = {(e.kind, e.title.casefold(), e.org.casefold()) for e in current.entries}
    new = [
        e for e in imported.entries if (e.kind, e.title.casefold(), e.org.casefold()) not in seen
    ]
    return current.model_copy(update={**basics, "entries": [*current.entries, *new]})


__all__ = ["Imported", "LifeEntry", "import_cv", "merge"]

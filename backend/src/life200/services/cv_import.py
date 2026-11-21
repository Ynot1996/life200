"""Turn an uploaded CV into a structured life profile, so a new user starts with their
details, experience, projects, education and skills already filled in.

The AI only copies what the CV says: it must not invent anything. Stories are left empty on
purpose, since a CV rarely contains them.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from google.genai import types
from pydantic import ValidationError

from life200.core.config import Settings
from life200.domain.life import LifeEntry, LifeProfile
from life200.services.ai_costs import Usage
from life200.services.tailor import (
    TailorError,
    Writer,
    claude_client,
    gemini_client,
)

SYSTEM = """You extract a CV into JSON. Copy facts only; never invent or improve anything.

Return ONLY a JSON object with these keys (use "" or [] when the CV does not say):
{
  "first_name": "", "last_name": "family name",
  "preferred_name": "only if the CV shows one, e.g. Tony",
  "email": "", "phone": "", "location": "",
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


TRANSCRIBE = (
    "Transcribe this document to plain text, exactly as written, in reading order. "
    "Keep every line, date and number. Do not summarise, translate or add anything."
)


def transcribe(settings: Settings, data: bytes, mime: str) -> tuple[str, Usage | None]:
    """Read an image or scanned PDF with the AI (it can see the page)."""
    try:
        if settings.anthropic_api_key is not None:
            import base64

            client = claude_client(settings.anthropic_api_key.get_secret_value())
            kind = "document" if mime == "application/pdf" else "image"
            source = {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}
            content: Any = [{"type": kind, "source": source}, {"type": "text", "text": TRANSCRIBE}]
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=16000,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in response.content if b.type == "text")
            u = response.usage
            return text, Usage("anthropic", settings.claude_model, u.input_tokens, u.output_tokens)
        if settings.gemini_api_key is not None:
            gclient = gemini_client(settings.gemini_api_key.get_secret_value())
            gresponse = gclient.models.generate_content(
                model=settings.gemini_model,
                contents=types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=data, mime_type=mime),
                        types.Part(text=TRANSCRIBE),
                    ],
                ),
            )
            meta = gresponse.usage_metadata
            usage = None
            if meta is not None:
                out = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
                usage = Usage("google", settings.gemini_model, meta.prompt_token_count or 0, out)
            return gresponse.text or "", usage
    except Exception as exc:
        raise TailorError(f"the AI could not read that file: {type(exc).__name__}") from exc
    raise TailorError("reading images and scans needs an AI key in .env")


def merge(current: LifeProfile, imported: LifeProfile) -> LifeProfile:
    """Fill empty basics from the import and add its entries; keep everything already there."""
    basics = {
        name: getattr(imported, name)
        for name in (
            "first_name",
            "last_name",
            "preferred_name",
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

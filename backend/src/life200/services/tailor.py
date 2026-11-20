"""Write a tailored CV and cover letter for one job, using only facts from the life profile.

Claude writes the drafts; `check_facts` then flags any number, email or link in the output
that appears in neither the profile nor the job ad, since those are the facts an LLM most
often invents. Flags are shown to the user before they apply.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

SYSTEM = """You write job applications for one candidate.

Hard rules:
- Use ONLY facts found in the candidate's profile. Never invent employers, dates, grades,
  numbers, skills, tools or results. You may select, reorder, shorten and reword.
- If the job asks for something the profile does not show, leave it out of the CV. In the
  cover letter you may say the candidate is keen to learn it, nothing more.
- Match the job's own words where the profile truly supports them, so screening software
  finds them.
- CV: Markdown, at most two pages: name and contact line, a 2-3 line profile, skills,
  experience, projects, education. Bullets start with a verb and include results.
- Cover letter: Markdown, under 300 words, addressed to the company, specific to this job.
- Write in the language of the job ad (English, Japanese or Chinese).

Reply with exactly two blocks: <cv>...</cv> then <cover_letter>...</cover_letter>."""


class TailorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Tailored:
    cv: str
    cover_letter: str
    warnings: list[str] = field(default_factory=list)


def job_prompt(job: dict[str, Any]) -> str:
    return (
        f"Job title: {job.get('Title')}\nCompany: {job.get('Company') or 'unknown'}\n"
        f"Location: {job.get('Location') or ''}\n\nJob description:\n{job.get('Description') or ''}"
    )


def tailor(client: Any, model: str, profile_text: str, job: dict[str, Any]) -> Tailored:
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, retry on a fallback model
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"<profile>\n{profile_text}\n</profile>\n\n<job>\n{job_prompt(job)}\n</job>"
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise TailorError("Claude declined to write this application")
    text = "".join(b.text for b in response.content if b.type == "text")
    cv = _block(text, "cv")
    letter = _block(text, "cover_letter")
    if not cv or not letter:
        raise TailorError("Claude's reply was missing the CV or the cover letter")
    source = profile_text + "\n" + job_prompt(job)
    return Tailored(cv, letter, check_facts(cv + "\n" + letter, source))


def _block(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


_NUMBER = re.compile(r"\d[\d,.]*%?")
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://\S+|www\.\S+")


def _norm_number(n: str) -> str:
    return n.replace(",", "").rstrip(".")


def check_facts(output: str, source: str) -> list[str]:
    """Numbers, emails and links in `output` that do not appear anywhere in `source`."""
    known_numbers = {_norm_number(n) for n in _NUMBER.findall(source)}
    warnings = []
    for n in sorted({_norm_number(n) for n in _NUMBER.findall(output)}):
        if n and n.rstrip("%") not in {k.rstrip("%") for k in known_numbers}:
            warnings.append(f'number "{n}" is not in your profile or the job ad')
    for c in sorted(set(_CONTACT.findall(output))):
        if c.rstrip(".,)") not in source:
            warnings.append(f'"{c}" is not in your profile')
    return warnings


def make_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)

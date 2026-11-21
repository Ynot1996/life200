"""Write a tailored CV and cover letter for one job, using only facts from the life profile.

An LLM (Claude, or Gemini when there is no Anthropic key) writes the drafts. `check_facts`
then flags any number, email or link in the output that appears in neither the profile nor
the job ad, since those are the facts an LLM most often invents. Flags are shown before applying.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from life200.core.config import Settings
from life200.services.ai_costs import Usage

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
    usage: Usage | None = None  # tokens used, for cost tracking


def job_prompt(job: dict[str, Any]) -> str:
    return (
        f"Job title: {job.get('Title')}\nCompany: {job.get('Company') or 'unknown'}\n"
        f"Location: {job.get('Location') or ''}\n\nJob description:\n{job.get('Description') or ''}"
    )


# A writer takes (system prompt, user message) and returns the model's text and token usage.
Writer = Callable[[str, str], tuple[str, Usage | None]]


# Never let a user wait for ever: one capped attempt per model (main, then fallback), so the
# worst case is about two minutes before a clear error.
REQUEST_TIMEOUT_SECONDS = 60


def claude_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS * 2, max_retries=1)


def gemini_client(api_key: str) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_SECONDS * 1000,  # milliseconds
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def claude_writer(api_key: str, model: str) -> Writer:
    client = claude_client(api_key)

    def write(system: str, user: str) -> tuple[str, Usage | None]:
        # Haiku has no server-side refusal fallback; bigger models retry on one if declined.
        extra: dict[str, Any] = (
            {}
            if "haiku" in model
            else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        )
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            output_config={"effort": "medium"},
            **extra,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason == "refusal":
            raise TailorError("Claude declined to write this application")
        text = "".join(b.text for b in response.content if b.type == "text")
        u = response.usage
        tokens_in = (
            u.input_tokens + (u.cache_creation_input_tokens or 0) + (u.cache_read_input_tokens or 0)
        )
        return text, Usage("anthropic", model, tokens_in, u.output_tokens)

    return write


def gemini_writer(api_key: str, model: str, fallback: str | None = None) -> Writer:
    """Gemini, switching to `fallback` once when Google is overloaded (5xx, e.g. 503)."""
    client = gemini_client(api_key)

    def call(name: str, system: str, user: str) -> tuple[str, Usage | None]:
        response = client.models.generate_content(
            model=name,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=16000),
        )
        meta = response.usage_metadata
        usage = None
        if meta is not None:
            out = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
            usage = Usage("google", name, meta.prompt_token_count or 0, out)
        return response.text or "", usage

    def write(system: str, user: str) -> tuple[str, Usage | None]:
        try:
            return call(model, system, user)
        except (genai_errors.ServerError, httpx.TimeoutException):
            if not fallback or fallback == model:
                raise
            return call(fallback, system, user)

    return write


def with_backup(first: Writer, backup: Writer) -> Writer:
    """Use `backup` when `first` fails for a reason other than declining the request."""

    def write(system: str, user: str) -> tuple[str, Usage | None]:
        try:
            return first(system, user)
        except TailorError:
            raise
        except Exception:
            return backup(system, user)

    return write


def writer_from_settings(settings: Settings) -> tuple[Writer, str] | None:
    """Claude if its key is set (Gemini as backup), else Gemini, else None, plus a UI label."""
    gemini = None
    if settings.gemini_api_key is not None:
        gemini = gemini_writer(
            settings.gemini_api_key.get_secret_value(),
            settings.gemini_model,
            settings.gemini_fallback_model,
        )
    if settings.anthropic_api_key is not None:
        claude = claude_writer(settings.anthropic_api_key.get_secret_value(), settings.claude_model)
        return (with_backup(claude, gemini) if gemini else claude), settings.claude_model
    if gemini is not None:
        return gemini, settings.gemini_model
    return None


def tailor(write: Writer, profile_text: str, job: dict[str, Any]) -> Tailored:
    user = f"<profile>\n{profile_text}\n</profile>\n\n<job>\n{job_prompt(job)}\n</job>"
    try:
        text, usage = write(SYSTEM, user)
    except TailorError:
        raise
    except Exception as exc:  # network, quota or key problems from either SDK
        raise TailorError(f"the AI service failed: {type(exc).__name__}") from exc
    cv = _block(text, "cv")
    letter = _block(text, "cover_letter")
    if not cv or not letter:
        raise TailorError("the reply was missing the CV or the cover letter")
    source = profile_text + "\n" + job_prompt(job)
    return Tailored(cv, letter, check_facts(cv + "\n" + letter, source), usage)


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

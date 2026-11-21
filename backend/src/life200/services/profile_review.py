"""Compare an imported CV with the saved profile, so the user approves every change.

Rules that keep a profile safe:
  * Nothing is saved until the user approves it.
  * Nothing is ever deleted by an import.
  * Fields the user already filled in are kept unless they choose the CV's version.
  * Every imported line and number is checked against the document's own text. Anything
    not found there is flagged and unticked, because that is where AI mistakes hide.
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from life200.domain.life import LifeEntry, LifeProfile

BASIC_FIELDS = {
    "full_name": "Full name",
    "email": "Email",
    "phone": "Phone",
    "location": "Location",
    "links": "Links",
    "headline": "Headline",
    "right_to_work": "Right to work",
}
MATCH_THRESHOLD = 80  # how alike two entries must be to count as the same job/degree/project
LINE_FOUND = 85  # how closely an imported line must appear in the document
_NUMBER = re.compile(r"\d[\d,.]*%?")


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w%+.,/]", " ", text.casefold()).split())


def unverified(entry: LifeEntry, source: str) -> list[str]:
    """Parts of an imported entry that do not appear in the document it came from."""
    src = _norm(source)
    src_numbers = {n.rstrip(".,") for n in _NUMBER.findall(src.replace(",", ""))}
    problems: list[str] = []
    for label, value in (("title", entry.title), ("organisation", entry.org)):
        if value and fuzz.partial_ratio(_norm(value), src) < LINE_FOUND:
            problems.append(f'{label} "{value}" not found in the document')
    for line in entry.text.splitlines():
        clean = _norm(line.lstrip("-•* "))
        if len(clean) >= 12 and fuzz.partial_ratio(clean, src) < LINE_FOUND:
            problems.append(f'line not found in the document: "{line.strip()[:80]}"')
        for n in _NUMBER.findall(line.replace(",", "")):
            if n.rstrip(".,") not in src_numbers:
                problems.append(f'number "{n}" not found in the document')
    return problems


def _same(a: LifeEntry, b: LifeEntry) -> float:
    if a.kind != b.kind:
        return 0.0
    title = fuzz.token_set_ratio(a.title.casefold(), b.title.casefold())
    if not (a.org or b.org):
        return float(title)
    org = fuzz.token_set_ratio(a.org.casefold(), b.org.casefold())
    return 0.6 * title + 0.4 * org


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def combine_text(mine: str, theirs: str) -> str:
    """My lines, plus any CV lines I do not already have (nothing of mine is lost)."""
    out = _lines(mine)
    for line in _lines(theirs):
        if all(fuzz.ratio(_norm(line), _norm(have)) < 90 for have in out):
            out.append(line)
    return "\n".join(out)


@dataclass
class BasicChange:
    field: str
    label: str
    mine: str
    theirs: str
    use_theirs: bool  # default decision: only fill empty fields


@dataclass
class NewItem:
    entry: LifeEntry
    problems: list[str]
    add: bool  # default decision: add when nothing looks wrong


@dataclass
class ChangedItem:
    index: int  # position in current.entries
    mine: LifeEntry
    theirs: LifeEntry
    problems: list[str]
    choice: str = "combine"  # "keep", "theirs", or "combine" (keep mine + add new lines)

    def result(self) -> LifeEntry:
        if self.choice == "theirs":
            return self.theirs
        if self.choice == "combine":
            return self.mine.model_copy(
                update={
                    "text": combine_text(self.mine.text, self.theirs.text),
                    "org": self.mine.org or self.theirs.org,
                    "start": self.mine.start or self.theirs.start,
                    "end": self.mine.end or self.theirs.end,
                }
            )
        return self.mine


@dataclass
class ImportPlan:
    source_name: str
    basics: list[BasicChange] = field(default_factory=list)
    new: list[NewItem] = field(default_factory=list)
    changed: list[ChangedItem] = field(default_factory=list)
    unchanged: int = 0

    @property
    def problems(self) -> int:
        return sum(bool(i.problems) for i in self.new) + sum(bool(i.problems) for i in self.changed)


def plan_import(
    current: LifeProfile, imported: LifeProfile, source_text: str, source_name: str
) -> ImportPlan:
    plan = ImportPlan(source_name)
    for name, label in BASIC_FIELDS.items():
        mine, theirs = getattr(current, name), getattr(imported, name)
        if theirs and _norm(theirs) != _norm(mine):
            plan.basics.append(BasicChange(name, label, mine, theirs, use_theirs=not mine))

    taken: set[int] = set()
    for entry in imported.entries:
        problems = unverified(entry, source_text)
        best, best_score = None, 0.0
        for i, have in enumerate(current.entries):
            if i not in taken and (score := _same(have, entry)) > best_score:
                best, best_score = i, score
        if best is None or best_score < MATCH_THRESHOLD:
            plan.new.append(NewItem(entry, problems, add=not problems))
            continue
        taken.add(best)
        mine = current.entries[best]
        if _norm(combine_text(mine.text, entry.text)) == _norm(mine.text):
            plan.unchanged += 1  # nothing new in the CV's version
        else:
            plan.changed.append(
                ChangedItem(best, mine, entry, problems, choice="keep" if problems else "combine")
            )
    return plan


def apply_plan(current: LifeProfile, plan: ImportPlan, source_entry: LifeEntry) -> LifeProfile:
    """The profile after the user's decisions. Existing entries keep their order."""
    basics = {b.field: b.theirs for b in plan.basics if b.use_theirs}
    entries = list(current.entries)
    for item in plan.changed:
        entries[item.index] = item.result()
    entries += [item.entry for item in plan.new if item.add]
    entries.append(source_entry)  # keep the original document text for reference
    return current.model_copy(update={**basics, "entries": entries})

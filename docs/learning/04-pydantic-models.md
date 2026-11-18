# Lesson 4: Pydantic models

Goal: understand data classes that check themselves. You will use Pydantic for API data, for
job postings, and for every LLM output in this project.

Try this first:

```bash
cd backend && uv run python
```

```python
from datetime import date
from life200.domain.profile import Period

Period(start=date(2026, 1, 1), end=date(2026, 6, 1))   # works
Period(start=date(2026, 6, 1), end=date(2026, 1, 1))   # ValidationError
```

The second line fails because of a **validator** in `domain/profile.py`:

```python
@model_validator(mode="after")
def _end_after_start(self) -> "Period":
    if self.end is not None and self.end < self.start:
        raise ValueError("period end must not be before start")
    return self
```

A validator runs when the object is created. If it raises, the object never exists, so the
rest of the program never has to handle bad data.

## Three settings every model here shares

```python
model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
```

| Setting | Effect |
|---|---|
| `extra="forbid"` | An unknown field is an error. Catches an LLM inventing fields |
| `frozen=True` | The object cannot be changed after creation |
| `str_strip_whitespace=True` | Strings are trimmed |

## The shape of a profile

```
MasterProfile → experiences / projects / education → achievements
```

An `Achievement` is one CV bullet: the smallest fact in the system.

## Try it

Add `SOFT = "soft"` to `SkillCategory`, then create a `Skill` with that category in the
Python prompt.

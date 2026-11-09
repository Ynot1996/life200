# Lesson 6: tests

Goal: read a pytest test and write one.

Run only the fact guard tests, with names shown:

```bash
cd backend && uv run pytest tests/test_fact_guard.py -v
```

## A test is a function with an assert

```python
def test_invented_number_is_flagged(dissertation_achievement: Achievement) -> None:
    rewritten = "Ran 10,000 task-runs, cutting cost by 1.8x."
    violations = check_rewrite(rewritten, [dissertation_achievement])
    assert [v.value for v in violations] == ["10000"]
```

The name says what should happen. The `assert` line is the check.

## Fixtures: shared setup

`dissertation_achievement` in the parameter list is a **fixture**. pytest finds a function
with that name in `tests/conftest.py`, runs it, and passes in the result. You write sample
data once and any test can ask for it by name.

## Parametrize: one test, many inputs

```python
@pytest.mark.parametrize(("text", "expected"), [
    ("6,810 task-runs", {"6810"}),
    ("42.9% of tasks", {"42.9"}),
])
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected
```

## The full check

`make check` runs three tools. CI runs the same three on every push.

| Tool | Checks |
|---|---|
| ruff | Formatting and common mistakes |
| mypy | Type hints are consistent |
| pytest | Tests pass |

## Try it

Write a test for the `GET /version` endpoint from lesson 3. Copy `tests/test_health.py` as a
starting point.

## Next

Sprint 1 lessons: calling a job API with httpx, storing jobs in Postgres, then pandas.

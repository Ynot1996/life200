# Lesson 5: the fact guard

Goal: learn the most useful habit in AI engineering — **if plain code can check an LLM's
output, do not ask another model to.**

Later, an LLM will reword your CV bullets for each job. It might invent a number.
`backend/src/life200/services/fact_guard.py` catches that.

Try it:

```bash
cd backend && uv run python
```

```python
from life200.services.fact_guard import extract_numbers

extract_numbers("Ran 6,810 task-runs at 42.9% success")
# {'6810', '42.9'}
```

It works with a regular expression:

```python
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
```

Read it as: a digit, then any digits or commas, then optionally a dot and more digits.

`check_rewrite(rewritten, sources)` then compares two sets:

```
numbers in the reworded text  −  numbers in the original  =  invented numbers
```

Anything left over is returned as a `Violation`. `check_skills` does the same for skill names.

## Why not use an LLM to check?

A checking model can be wrong too, costs money on every call, and gives different answers on
different runs. This check is free, instant and always gives the same answer.

## Try it

Does the guard catch `6,810` reworded as "six thousand eight hundred and ten"? Test it in the
Python prompt. This is a known gap.

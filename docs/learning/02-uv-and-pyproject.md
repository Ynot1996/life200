# Lesson 2: uv and pyproject.toml

Goal: know where packages come from and how to add one.

Open `backend/pyproject.toml`.

- `dependencies` lists the packages the app needs to run (FastAPI, Pydantic).
- `[dependency-groups] dev` lists packages only developers need (pytest, ruff, mypy).
- The `[tool.*]` sections configure those tools.

Three files work together:

| File | Role |
|---|---|
| `pyproject.toml` | What you want: "fastapi 0.115 or newer" |
| `uv.lock` | What you got: the exact version of every package |
| `.venv/` | The installed packages. Never committed |

The lock file is why the project installs identically on your Mac and in CI.

## Commands you will use

```bash
uv add pandas
```

```bash
uv add --dev ipykernel
```

```bash
uv run pytest
```

`uv run` means "run this inside the project's `.venv`".

## Try it

From `backend/`, run `uv add httpx` and look at what changed in `pyproject.toml` and `uv.lock`
with `git diff`. Sprint 1 needs httpx, so keep the change.

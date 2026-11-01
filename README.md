# Life200

A job-search co-pilot. Life200 keeps **one master profile** of everything you have done,
finds matching roles across job boards, drafts a **JD-tailored CV and answers** for each one,
pre-fills the application form, and tracks every application — while **you** review and press submit.

> **Design rule:** the LLM may *select, reorder and reword* facts from the master profile.
> It may never *add* one. Every tailored CV passes a deterministic fact check
> (`backend/src/life200/services/fact_guard.py`) before you see it.

## Status

Phase 0 (foundation) complete — see [ROADMAP.md](ROADMAP.md).

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Most-requested backend/AI language in UK job ads |
| API | FastAPI + Pydantic v2 | Typed, async, auto-generated OpenAPI docs |
| Database | PostgreSQL 16 + pgvector | One store for relational data and embeddings |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Industry standard for Python + Postgres |
| Background jobs | Celery + Redis | Scheduled job search, LLM calls, form filling |
| Browser automation | Playwright | Pre-filling application forms |
| Frontend | Next.js + TypeScript + Tailwind | Review workspace: side-by-side CV diff and inline edit |
| Tooling | uv, ruff, mypy (strict), pytest, pre-commit | Fast, modern Python toolchain |
| Infra | Docker Compose, GitHub Actions | Reproducible local dev and CI on every push |

## Quick start (macOS)

```bash
# one-time
brew install uv                       # Python package/project manager
brew install --cask docker            # or OrbStack — runs Postgres + Redis
uv tool install pre-commit

cd life200
cp .env.example .env                  # fill in API keys later
git init && pre-commit install

make install                          # creates backend/.venv and uv.lock
make check                            # lint + type check + tests (same as CI)
make up                               # start Postgres + Redis
make dev                              # API on http://localhost:8000/docs
```

Commit `backend/uv.lock` — CI installs with `uv sync --frozen`, so the lock file is required.

## Repository layout

```
life200/
├── backend/            Python API, workers, domain logic
│   ├── src/life200/
│   │   ├── api/        HTTP routes (thin: validate input, call services)
│   │   ├── core/       config, logging, shared infrastructure
│   │   ├── domain/     Pydantic models — the language of the business
│   │   └── services/   business logic (fact guard, tailoring, matching…)
│   └── tests/
├── frontend/           Next.js review workspace (Phase 4)
├── docs/
│   ├── architecture.md
│   └── learning/       one lesson per concept, written as the code is built
├── docker-compose.yml
└── Makefile
```

## What Life200 deliberately does not do

- **Create accounts on job sites automatically.** It breaches most platforms' terms and
  risks your real accounts. For sites that need an account, Life200 prepares everything and
  you sign up yourself.
- **Submit without review.** Every application stops at a pre-filled form for you to confirm.
- **Scrape LinkedIn.** LinkedIn roles arrive via its own job-alert emails instead.

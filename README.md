# Life200

A job-search co-pilot for the UK, in two halves on one job-data pipeline:

- **Find:** new jobs from several platforms in one sortable table, each tagged with whether
  the employer holds a visa-sponsor licence and whether the role is truly junior.
- **Apply:** one master profile of everything you have done, a JD-tailored CV and answers for
  each role, a pre-filled application form, and a tracker — while **you** review and press submit.

> **Design rule:** the LLM may *select, reorder and reword* facts from the master profile.
> It may never *add* one. Every tailored CV passes a deterministic fact check
> (`backend/src/life200/services/fact_guard.py`) before you see it.

## Status

Phase 0 (foundation) complete. Next: Phase 1, job data and sponsor match.

- [ROADMAP.md](ROADMAP.md) — phases
- [docs/product/brief.md](docs/product/brief.md) — what the product is and who it is for
- [docs/product/backlog.md](docs/product/backlog.md) — stories and the current sprint
- [docs/learning/](docs/learning/README.md) — short lessons, one idea each

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | One language for the API, data science and AI |
| Data science | pandas, scikit-learn, Jupyter | Market analysis and the truly-junior classifier |
| API | FastAPI + Pydantic v2 | Typed, async, auto-generated OpenAPI docs |
| Database | PostgreSQL 16 + pgvector | One store for relational data and embeddings |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Industry standard for Python + Postgres |
| Background jobs | Celery + Redis | Scheduled job search, LLM calls, form filling |
| Browser automation | Playwright | Pre-filling application forms |
| Frontend | Streamlit | Jobs table, charts and CV review, all in Python |
| Tooling | uv, ruff, mypy (strict), pytest, pre-commit | Fast, modern Python toolchain |
| Infra | Docker Compose, GitHub Actions | Reproducible local dev and CI on every push |

## Quick start (macOS)

```bash
# one-time
brew install uv                       # Python package/project manager
brew install --cask docker            # or OrbStack — runs Postgres + Redis
uv tool install pre-commit

cd ~/Desktop/Applications/life200     # every command below runs from here
cp .env.example .env                  # fill in API keys later
pre-commit install

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
├── frontend/           Streamlit app (Phase 3)
├── docs/
│   ├── architecture.md
│   ├── product/        brief and backlog
│   └── learning/       short lessons, one idea each
├── docker-compose.yml
└── Makefile
```

## What Life200 deliberately does not do

- **Create accounts on job sites automatically.** It breaches most platforms' terms and
  risks your real accounts. For sites that need an account, Life200 prepares everything and
  you sign up yourself.
- **Submit without review.** Every application stops at a pre-filled form for you to confirm.
- **Scrape LinkedIn.** LinkedIn roles arrive via its own job-alert emails instead.

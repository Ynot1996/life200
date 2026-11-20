# Life200

A job-search co-pilot for junior and intern roles in the UK, Singapore, Japan and Taiwan, in two halves on one job-data pipeline:

- **Find:** new jobs from several platforms in one sortable table, each tagged with whether
  the employer holds a visa-sponsor licence and whether the role is truly junior.
- **Apply:** one master profile of everything you have done, a JD-tailored CV and answers for
  each role, a pre-filled application form, and a tracker — while **you** review and press submit.

> **Design rule:** the LLM may *select, reorder and reword* facts from the master profile.
> It may never *add* one. Every tailored CV passes a deterministic fact check
> (`backend/src/life200/services/fact_guard.py`) before you see it.

## Status

**Find and apply both work.** Log in, and the app has four pages:

- **Matches and apply:** your best-fitting junior jobs, ranked against your life profile
  (TF-IDF similarity, with the shared words shown). Pick one, press **Tailor CV and cover
  letter**, and Claude or Gemini writes both from your profile only. Any number, email or link that is
  not in your profile or the job ad is flagged. Edit, download as Word, open the
  application page, then mark it applied.
- **All junior jobs:** only roles tagged junior or intern. Unclear and senior roles are hidden.
  The table filters by market, sponsor (UK) and posting date.
- **My life:** your details, and every job, project, course, award and story. You can import
  an existing CV (PDF or Word). This is the only source of facts for applications.
- **My applications:** a tracker with the statuses draft, applied, interview, offer and rejected.

Jobs come from Adzuna (UK and Singapore) and Jooble (Japan and Taiwan). Each UK job is
tagged licensed, likely, agency, paid course or not found, matched against the Home Office
register of licensed sponsors.

- [ROADMAP.md](ROADMAP.md) — phases
- [docs/product/brief.md](docs/product/brief.md) — what the product is and who it is for
- [docs/product/backlog.md](docs/product/backlog.md) — stories and the current sprint
- [docs/learning/](docs/learning/README.md) — short lessons, one idea each

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | One language for the API, data science and AI |
| Job data | httpx, Adzuna and Jooble APIs | UK, Singapore, Japan and Taiwan jobs, with retries |
| Data science | pandas, scikit-learn, Jupyter | Market analysis and the truly-junior classifier |
| API | FastAPI + Pydantic v2 | Typed, async, auto-generated OpenAPI docs |
| Database | PostgreSQL 16 + pgvector | One store for relational data and embeddings |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Industry standard for Python + Postgres |
| Background jobs | Celery + Redis | Scheduled job search, LLM calls, form filling |
| Browser automation | Playwright | Pre-filling application forms |
| Frontend | Streamlit | Login, jobs table, life profile, CV review, tracker, all in Python |
| AI | Claude API or Gemini API | Tailored CV and cover letter per job |
| Documents | python-docx, pypdf | Word downloads, CV import |
| Matching | rapidfuzz, pandas | Company names against the sponsor register; data for the table |
| Tooling | uv, ruff, mypy (strict), pytest, pre-commit | Fast, modern Python toolchain |
| Infra | Docker Compose, GitHub Actions | Reproducible local dev and CI on every push |

## Quick start (macOS)

```bash
# one-time
brew install uv                       # Python package/project manager
brew install --cask orbstack          # runs Postgres + Redis in Docker
uv tool install pre-commit

cd ~/Desktop/Applications/life200     # every command below runs from here
cp .env.example .env                  # Adzuna, Anthropic and Jooble keys (see below)
pre-commit install

make install                          # creates backend/.venv and uv.lock
make check                            # lint + type check + tests (same as CI)
make up                               # start Postgres + Redis (needs Docker or OrbStack)
make migrate                          # create the database tables
make admin EMAIL=you@example.com      # create your login (asks for a password)
make refresh                          # sponsor register + jobs from all four markets, tagged
make app                              # log in on http://localhost:8501
make dev                              # API on http://localhost:8000/docs
```

Keys in `.env`:

- `LIFE200_ADZUNA_APP_ID` and `LIFE200_ADZUNA_APP_KEY`: the UK and Singapore jobs.
- `LIFE200_GEMINI_API_KEY` or `LIFE200_ANTHROPIC_API_KEY`: tailored CVs and cover letters. Claude
  is used if its key is set, otherwise Gemini (free key from aistudio.google.com; on the free
  tier Google may use what you send to improve its products). Models are set with
  `LIFE200_CLAUDE_MODEL` (default `claude-opus-5-5`) and `LIFE200_GEMINI_MODEL` (default
  `gemini-3.8-flash`).
- `LIFE200_JOOBLE_KEY`: Japan and Taiwan jobs. One free key from jooble.org/api/about covers
  both. Without it, those markets are skipped.

Commit `backend/uv.lock` — CI installs with `uv sync --frozen`, so the lock file is required.

## Repository layout

```
life200/
├── backend/            Python API, workers, domain logic
│   ├── src/life200/
│   │   ├── api/        HTTP routes (thin: validate input, call services)
│   │   ├── core/       config, logging, shared infrastructure
│   │   ├── db/         database tables and connection (SQLAlchemy)
│   │   ├── domain/     Pydantic models — the language of the business
│   │   ├── services/   business logic (jobs, tags, auth, matching, tailoring, tracker)
│   │   ├── sources/    job platforms (Adzuna, Jooble) and the sponsor register
│   │   ├── ui/         Streamlit app: login, then pages in ui/views/ (`make app`)
│   │   └── cli.py      command line: `make admin`, `make refresh`, `make fetch`, `make sponsors`
│   ├── migrations/     Alembic scripts that change the database
│   └── tests/
├── docs/
│   ├── architecture.md
│   ├── product/        brief and backlog
│   └── learning/       short lessons, one idea each
├── docker-compose.yml
└── Makefile
```

## Known limits of the MVP

- A sponsor **licence** means an employer can sponsor, not that it will for a given role.
- Recruitment agencies hide the real employer, so their jobs are tagged "agency".
- Adzuna descriptions are cut short, so an experience requirement late in a job ad can be missed.
- Tags are rules, not machine learning yet; each one shows its reason so it can be checked.
- Japan and Taiwan junior tags rely on title words such as 新卒, 未経験, 實習 and 新鮮人, so
  some junior roles there are missed. The Jooble endpoints for jp and tw are untested with a
  real key.
- Matching is word overlap (TF-IDF), not meaning, so it can miss a strong match that is
  described in different words.
- **Applying is not automatic.** Each employer's site needs your own account and often a
  CAPTCHA, and auto-submitting breaks most sites' terms. Life200 prepares the documents and
  opens the page, and you submit.

## What Life200 deliberately does not do

- **Create accounts on job sites automatically.** It breaches most platforms' terms and
  risks your real accounts. For sites that need an account, Life200 prepares everything and
  you sign up yourself.
- **Submit without review.** Every application stops at a pre-filled form for you to confirm.
- **Scrape LinkedIn.** LinkedIn roles arrive via its own job-alert emails instead.

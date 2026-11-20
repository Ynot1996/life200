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

**Find and apply both work, for anyone.**

- **Without an account:** search junior and intern jobs in the UK, Singapore, Japan and
  Taiwan, with each market's filters (sponsor licence, Japanese required, Employment Pass
  salary, top-university requirement).
- **With a free account** (Continue with Google):
  - **My profile:** on the first visit, upload your CV and the AI fills in your details,
    experience, projects, education and skills, copying only what the CV says. After that,
    each section has its own tab to edit: Experience, Projects, Education, Skills, Stories
    (STAR moments for cover letters and interviews, written by you), and Awards and other.
    It is the only source of facts for applications.
  - **Matches and apply:** jobs ranked against your profile. Press **Tailor CV and cover
    letter** and the AI writes both from your profile only, flagging any number or link that
    is not in your profile or the job ad. Edit, download as Word, open the application page,
    mark it applied.
  - **My applications:** your history, with the statuses draft, applied, interview, offer and rejected.

Each user's profile and applications are private to their account. Every account has a
`plan` (all "free" today), ready for paid tiers later. Every AI call is logged with its user,
model, tokens and list-price cost (`ai_usage` table), and admins see totals on **AI costs**,
so credit prices can be set from real numbers.

Each market has its own sources and rules. Every rule is a sidebar switch, and each job
shows why it was flagged.

| Market | Source | Rules (on by default) |
|---|---|---|
| 🇬🇧 UK | Adzuna | Employer on the Home Office sponsor register (licensed, likely, agency, paid course, not found) |
| 🇸🇬 Singapore | Adzuna | Hide citizens/PR-only ads; hide pay below the Employment Pass minimum (S$5,600/month in 2026, S$6,000 from 2027) |
| 🇯🇵 Japan | Japan Dev | Hide jobs needing Japanese; only jobs open to applicants abroad; visa sponsorship shown |
| 🇹🇼 Taiwan | Jooble Taiwan (needs a tw.jooble.org key) | Hide jobs asking for a top university (台清交成, 頂大…); highest pay first, monthly pay ×12 |

- [ROADMAP.md](ROADMAP.md) — phases
- [docs/product/brief.md](docs/product/brief.md) — what the product is and who it is for
- [docs/product/backlog.md](docs/product/backlog.md) — stories and the current sprint
- [docs/learning/](docs/learning/README.md) — short lessons, one idea each

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | One language for the API, data science and AI |
| Job data | httpx; Adzuna, Japan Dev, Jooble | UK, Singapore, Japan and Taiwan jobs, with retries |
| Data science | pandas, scikit-learn, Jupyter | Market analysis and the truly-junior classifier |
| API | FastAPI + Pydantic v2 | Typed, async, auto-generated OpenAPI docs |
| Database | PostgreSQL 16 + pgvector | One store for relational data and embeddings |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Industry standard for Python + Postgres |
| Background jobs | Celery + Redis | Scheduled job search, LLM calls, form filling |
| Browser automation | Playwright | Pre-filling application forms |
| Frontend | Streamlit | Public job search; Google sign-in; profile, CV review, tracker |
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
make admin EMAIL=you@example.com      # optional: an admin login with a password
make refresh                          # sponsor register + jobs from all four markets, tagged
make app                              # http://localhost:8501: search, or sign in
make dev                              # API on http://localhost:8000/docs
```

Keys in `.env`:

- `LIFE200_ADZUNA_APP_ID` and `LIFE200_ADZUNA_APP_KEY`: the UK and Singapore jobs.
- `LIFE200_GEMINI_API_KEY` or `LIFE200_ANTHROPIC_API_KEY`: tailored CVs and cover letters. Claude
  is used if its key is set, otherwise Gemini (free key from aistudio.google.com; on the free
  tier Google may use what you send to improve its products). Models are set with
  `LIFE200_CLAUDE_MODEL` (default `claude-opus-5-5`) and `LIFE200_GEMINI_MODEL` (default
  `gemini-3.8-flash`).
- `LIFE200_JOOBLE_TW_KEY`: Taiwan jobs. Jooble keys only work on the site that issued them,
  so request it at tw.jooble.org/api/about. Without it, Taiwan is skipped.

### Google sign-in

Users sign in with Google; their account is created on first sign-in. Set it up once:

1. Open console.cloud.google.com and create a project (for example "Life200").
2. Go to **Google Auth Platform**, click **Get started**, and enter the app name and your
   email. Choose **External** for the audience.
3. Under **Audience**, add your Google email as a test user. While the app is in testing
   mode, only test users can sign in. Press **Publish app** when real users should get in.
4. Under **Clients**, create a client of type **Web application**. Add this to
   **Authorized redirect URIs**: `http://localhost:8501/oauth2callback`
5. Paste the client ID and client secret into `backend/.streamlit/secrets.toml`. The file
   is git-ignored, and `secrets.example.toml` shows the format. Restart `make app`.

Only the basic scopes are used (`openid`, `email`, `profile`), so Google does not need to
review the app. When the app is deployed, add the public address as a second redirect URI
and set `redirect_uri` to it.

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
│   │   ├── services/   business logic (jobs, tags, market rules, auth, matching, tailoring)
│   │   ├── sources/    job platforms (Adzuna, Japan Dev, Jooble) and the sponsor register
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
- Japan Dev serves its 60 newest jobs per visit, so Japan grows with each daily refresh. Most
  English-friendly jobs in Japan are mid-level or senior, so few are junior.
- Taiwan has no working source yet. Cake, Yourator and TokyoDev block automated visits with a
  bot check, which Life200 does not bypass.
- Most Singapore ads on Adzuna have no salary, so Employment Pass chances are often unknown.
  Interns usually need a Training Employment Pass instead, which these rules do not check.
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

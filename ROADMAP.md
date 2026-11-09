# Roadmap

Each phase ends with something you can demo. Each has a matching lesson in `docs/learning/`.
Product brief: [docs/product/brief.md](docs/product/brief.md). Stories:
[docs/product/backlog.md](docs/product/backlog.md).

The market-insights half ships first: it needs no user accounts, it tests whether anyone
wants the product, and its job data feeds the apply assistant that follows.

| # | Phase | Delivers | You learn |
|---|---|---|---|
| 0 | **Foundation** ✅ | Repo, tooling, CI, health API, master-profile schema, fact guard | Project layout, uv, Pydantic, pytest, typing |
| 1 | **Job data + sponsor match** | Adzuna postings in Postgres, deduped; Home Office sponsor register loaded; employers matched; notebook answering "what share of junior postings come from licensed sponsors?" | httpx, SQLAlchemy 2.0, Alembic, pandas, Jupyter, fuzzy matching |
| 2 | **Market analysis** | Hand-labelled set; "truly junior" classifier vs a baseline; skills demand; salary estimate | Labelling, scikit-learn, evaluation, statistics, statsmodels |
| 3 | **Public insights page** | Deployed page with filtered role list and charts; daily collection; weekly email; visitor analytics | Celery + Redis scheduling, Next.js, deployment, product analytics |
| 4 | **Master profile** | Upload past CVs (PDF/DOCX) → LLM extracts achievements → review and merge into Postgres | File uploads, structured LLM output |
| 5 | **Match + tailor** | JD → structured requirements → fit score → selected and reworded bullets → fact guard → CV (DOCX/PDF) + cover letter + answers | Prompt design, embeddings/pgvector, LLM evaluation |
| 6 | **Review workspace** | Tailored CV beside the master version, highlighted changes, inline edit, approve | React, TypeScript, Tailwind, API integration |
| 7 | **Apply** | Playwright pre-fills no-account ATS forms (Greenhouse, Lever, Ashby) and stops before submit | Browser automation, resilience, retries |
| 8 | **Track** | Application pipeline, Gmail status parsing, Companies House enrichment, funnel analytics per CV version | OAuth, background parsing, analytics queries |
| 9 | **Harden** | Structured logging, Sentry, cost dashboard | Observability, running a service in production |

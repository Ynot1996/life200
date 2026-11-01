# Roadmap

Each phase ends with something you can demo. Each has a matching lesson in `docs/learning/`.

| # | Phase | Delivers | You learn |
|---|---|---|---|
| 0 | **Foundation** ✅ | Repo, tooling, CI, health API, master-profile schema, fact guard | Project layout, uv, Pydantic, pytest, typing |
| 1 | **Master profile** | Upload past CVs (PDF/DOCX) → LLM extracts achievements → review and merge into Postgres | SQLAlchemy 2.0, Alembic, file uploads, structured LLM output |
| 2 | **Job discovery** | Saved searches (title, salary, posted-within, sources); Adzuna, Reed, Greenhouse, Lever, Ashby connectors; dedupe; UK visa-sponsor filter | HTTP clients, Celery + Redis scheduling, idempotency |
| 3 | **Match + tailor** | JD → structured requirements → fit score → selected and reworded bullets → fact guard → CV (DOCX/PDF) + cover letter + answers | Prompt design, embeddings/pgvector, evaluation |
| 4 | **Review workspace** | Next.js UI: tailored CV beside the master version, highlighted changes, inline edit, approve | React, TypeScript, Tailwind, API integration |
| 5 | **Apply** | Playwright pre-fills no-account ATS forms (Greenhouse, Lever, Ashby) and stops before submit | Browser automation, resilience, retries |
| 6 | **Track** | Application pipeline, Gmail status parsing, Companies House enrichment, funnel analytics per CV version | OAuth, background parsing, analytics queries |
| 7 | **Ship** | Deploy to AWS, structured logging, Sentry, cost dashboard | Docker in production, cloud, observability |

# Architecture

## Data flow

```
 past CVs ──► parse ──► MASTER PROFILE (Postgres) ◄── you edit / approve
                               │
 saved searches ─► job sources ─► jobs (deduped) ─► match score
                               │                        │
                               └────────► tailor ◄──────┘
                                            │
                                       FACT GUARD  ── fails ─► flagged for review
                                            │
                                    review workspace (you edit)
                                            │
                                pre-filled form ─► you submit ─► tracker
```

## Layering rule

`api → services → domain`. Arrows only point inward.

- **domain/** knows nothing about HTTP, databases or LLMs. Pure Pydantic models and rules.
- **services/** holds business logic. It may call the database or an LLM through small interfaces.
- **api/** is thin: parse the request, call a service, return a response.

This is why `fact_guard` can be unit-tested without a server, a database or an API key.

## Why the master profile is the centre

Every downstream output (CV, cover letter, form answers) is a *view* of the master profile.
Facts are atomic `Achievement`s with `sources` pointing to the uploaded CV they came from, so
any line on any generated CV can be traced back to evidence.

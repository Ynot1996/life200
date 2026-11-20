# Lesson 8: storing jobs in Postgres

Goal: understand tables, migrations and upserts.

## The table, in Python

Open `backend/src/life200/db/models.py`. Each `Mapped[...]` line is a column:

```python
title: Mapped[str] = mapped_column(Text)              # required text
company: Mapped[str | None] = mapped_column(Text)     # optional: `| None` allows empty
```

This is SQLAlchemy, the standard way to work with databases from Python.

## Migrations: changing the real database

Changing `models.py` does not change the database. A **migration** does: a small script in
`backend/migrations/versions/` with `upgrade()` and `downgrade()` steps.

```bash
make migrate
```

Alembic records which migrations have run, so every database (yours, CI, production) ends up
with the same tables. To change a table later:

```bash
cd backend && uv run alembic revision --autogenerate -m "add sponsor column"
```

Alembic compares `models.py` with the database and writes the migration. Always read it
before running it.

## No duplicates: the upsert

`backend/src/life200/services/ingest.py` saves jobs with an **upsert**: insert the row, or, if
a row with the same `(source, source_id)` exists, update it. The unique constraint in
`models.py` is what makes this work. Run `make fetch` twice: the second run says
"0 new".

## Look at the data yourself

```bash
docker compose exec db psql -U life200 -d life200
```

```sql
SELECT title, company, salary_min FROM job_postings ORDER BY posted_at DESC LIMIT 5;
```

Type `\q` to leave.

## Tests use their own database

Tests run against `life200_test`, and each test's changes are rolled back afterwards, so
tests never touch your real jobs or each other.

## Try it

Count how many saved jobs have a salary that Adzuna estimated rather than one the employer
published:

```sql
SELECT salary_is_predicted, count(*) FROM job_postings GROUP BY salary_is_predicted;
```

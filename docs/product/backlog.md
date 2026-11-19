# Life200 backlog

Last updated: 2026-11-09 · Size is relative effort: 2 small, 3 a day or two, 5 most of a week.

## Sprint 1 — job data and sponsor tag

Goal: real jobs in the database, each tagged with whether the employer holds a sponsor licence.

| # | Story | Done when | Size |
|---|---|---|---|
| 1 | ✅ Fetch Adzuna jobs into Postgres | One command saves jobs with title, employer, salary, location, date, URL and source | 5 |
| 2 | ✅ No duplicates | Fetching twice leaves the row count unchanged | 3 |
| 3 | ✅ Load the sponsor register | Home Office CSV is in Postgres | 3 |
| 4 | ✅ Tag each job's employer | "Monzo Bank Ltd" matches "MONZO BANK LIMITED"; 95 of 100 hand-checked tags are right | 5 |
| 5 | ✅ First look at the data (as the Streamlit table instead of a notebook) | A notebook showing the tagged jobs as a table, with the sponsor share | 2 |

Run: `make up`, `make migrate`, `make refresh`, then `make app`.

## Next

| Story | Size |
|---|---|
| ✅ Truly junior filter, rule-based (MVP). Next: label 200 jobs, train a model, beat the rule | 8 |
| ✅ Jobs table page: sortable, filterable, click for full description | 5 |
| Daily automatic collection | 5 |
| Second source (Reed), with duplicates merged | 5 |
| Skills demand and salary estimate | 5 |
| Visitor tracking | 2 |

## Later

Master profile from uploaded CVs · role matching and skills gap · tailored CV with fact guard ·
pre-filled application forms · application tracker.

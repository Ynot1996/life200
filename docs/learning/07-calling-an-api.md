# Lesson 7: calling an API with httpx

Goal: understand how the app gets jobs from Adzuna.

Run it from the project folder:

```bash
make fetch
```

Then open `backend/src/life200/sources/adzuna.py`.

## One request

```python
response = self._http.get(url, params=params)
```

`params` becomes the query string: `?app_id=...&what=junior+software+engineer&where=London`.
`response.status_code` says what happened, and `response.json()` turns the body into Python
dicts and lists.

## Parsing is separate from fetching

`parse_job(item)` turns one Adzuna result into a `JobPosting` (from `domain/job.py`). It does
no network calls, so it is easy to test. Each future source (Reed…) gets its own `parse_job`,
and the rest of the app only ever sees `JobPosting`.

## When things go wrong

| Problem | What the client does |
|---|---|
| 429 (too many requests) or 5xx (server trouble) | Waits 2s, 4s, then gives up |
| Network error, no response | Same: retry with growing waits |
| 401 (bad key) or other 4xx | Fails at once: retrying cannot fix it |

Waiting longer after each failure is called **exponential backoff**.

The API key is in the request URL, so the code never logs URLs or puts them in errors.

## Testing without the internet

`tests/test_adzuna.py` uses `httpx.MockTransport`: a fake network that returns whatever the
test decides. That is how the tests check retries and errors without calling Adzuna.

## Try it

Fetch a different search and watch the counts:

```bash
make fetch WHAT="junior data analyst" PAGES=2
```

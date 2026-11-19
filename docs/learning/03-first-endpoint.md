# Lesson 3: the first endpoint

Goal: follow one request from the browser to the code and back.

Open `backend/src/life200/api/health.py`:

```python
router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str
    version: str

@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
```

- `router` is a group of endpoints.
- `@router.get("/health")` says: when someone sends `GET /health`, call this function.
- `HealthResponse` describes the shape of the answer. FastAPI converts it to JSON and uses it
  to build the `/docs` page.

Now open `backend/src/life200/main.py`:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Life200", version=__version__)
    app.include_router(health.router)
    return app
```

`create_app()` builds the app and plugs the router in. It is a function so that each test can
build its own clean app.

## Where code goes

```
api/        endpoints: receive a request, call a service, return the answer
services/   the actual logic
domain/     data models
sources/    job platforms (lesson 7)
db/         database tables (lesson 8)
core/       settings
```

Rule: `api` uses `services`, `services` use `domain`. Never the other way.

## Try it

Add `GET /version` that returns `{"version": "0.1.0"}`. Check it appears on `/docs`.

"""FastAPI application entry point.

Run locally:  uv run uvicorn life200.main:app --reload
"""

from fastapi import FastAPI

from life200 import __version__
from life200.api import health


def create_app() -> FastAPI:
    """App factory: builds a fresh app (tests can create isolated instances)."""
    app = FastAPI(title="Life200", version=__version__)
    app.include_router(health.router)
    return app


app = create_app()

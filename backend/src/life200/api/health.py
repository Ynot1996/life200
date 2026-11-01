"""Liveness endpoint — used by Docker, load balancers and uptime monitors."""

from fastapi import APIRouter
from pydantic import BaseModel

from life200 import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)

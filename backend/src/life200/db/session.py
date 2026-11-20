"""Database connection.

The engine holds a pool of connections to Postgres. A Session is one unit of work:
open it, read or write, commit, close.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from life200.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url)


def get_sessionmaker() -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(get_engine())

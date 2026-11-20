"""Shared pytest fixtures."""

import json
import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from life200.db.models import Base
from life200.domain.profile import (
    Achievement,
    Education,
    MasterProfile,
    Period,
    Skill,
    SkillCategory,
    SourceRef,
)
from life200.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def dissertation_achievement() -> Achievement:
    return Achievement(
        text=(
            "Ran a controlled study of 6,810 task-runs across 5 agent conditions; "
            "resampling was 1.8-4.2x cheaper per problem solved."
        ),
        skills=("Python", "LangGraph"),
        tags=("evaluation", "research"),
        sources=(SourceRef(document="Tony_Kang_CV_AI_Engineer.docx"),),
    )


@pytest.fixture
def profile(dissertation_achievement: Achievement) -> MasterProfile:
    return MasterProfile(
        full_name="Tony Kang",
        location="London",
        skills=(
            Skill(name="Python", category=SkillCategory.LANGUAGE),
            Skill(name="LangGraph", category=SkillCategory.FRAMEWORK),
            Skill(name="PostgreSQL", category=SkillCategory.TOOL, aliases=("Postgres",)),
        ),
        education=(
            Education(
                institution="University of Birmingham",
                qualification="MSc Computer Science",
                period=Period(start=date(2025, 9, 1), end=date(2026, 9, 1)),
                achievements=(dissertation_achievement,),
            ),
        ),
    )


# ---------- Job data ----------

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def adzuna_response() -> dict[str, Any]:
    """A recorded-style Adzuna search response (made-up companies, real field names)."""
    data: dict[str, Any] = json.loads((FIXTURES / "adzuna_search.json").read_text())
    return data


# ---------- Database ----------
# Tests use a separate database, life200_test, so they never touch your real data.

TEST_DATABASE_URL = os.environ.get(
    "LIFE200_TEST_DATABASE_URL",
    "postgresql+psycopg://life200:life200@localhost:5432/life200_test",
)


def _create_test_database(url: str) -> None:
    """Create the test database if it does not exist yet (connects to the default one)."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    except OperationalError as exc:
        pytest.fail(f"Cannot reach Postgres for tests. Is it running? Try `make up`.\n{exc}")
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """One engine for the whole test run, with fresh tables."""
    _create_test_database(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A session whose changes are rolled back after each test, so tests never affect each other."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()

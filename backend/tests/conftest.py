"""Shared pytest fixtures."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

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

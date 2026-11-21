"""Load and save a user's life profile."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from life200.db.models import LifeProfileRow, ProfileVersionRow
from life200.domain.life import LifeProfile

KEEP_VERSIONS = 30


def load_profile(session: Session, user_id: int) -> LifeProfile:
    row = session.get(LifeProfileRow, user_id)
    return LifeProfile.model_validate(row.data) if row else LifeProfile()


def save_profile(
    session: Session, user_id: int, profile: LifeProfile, reason: str = "edit"
) -> None:
    """Save, first keeping a copy of what was there so the change can be undone."""
    row = session.get(LifeProfileRow, user_id)
    data = profile.model_dump()
    if row is None:
        session.add(LifeProfileRow(user_id=user_id, data=data))
    elif row.data != data:
        session.add(ProfileVersionRow(user_id=user_id, data=row.data, reason=reason))
        row.data = data
        _prune(session, user_id)
    session.flush()


def _prune(session: Session, user_id: int) -> None:
    old = session.scalars(
        select(ProfileVersionRow)
        .where(ProfileVersionRow.user_id == user_id)
        .order_by(ProfileVersionRow.created_at.desc(), ProfileVersionRow.id.desc())
        .offset(KEEP_VERSIONS)
    ).all()
    for version in old:
        session.delete(version)


def list_versions(session: Session, user_id: int) -> list[tuple[int, datetime, str]]:
    """(id, when, what changed next), newest first."""
    rows = session.execute(
        select(ProfileVersionRow.id, ProfileVersionRow.created_at, ProfileVersionRow.reason)
        .where(ProfileVersionRow.user_id == user_id)
        .order_by(ProfileVersionRow.created_at.desc(), ProfileVersionRow.id.desc())
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]


def restore_version(session: Session, user_id: int, version_id: int) -> None:
    version = session.get(ProfileVersionRow, version_id)
    if version is None or version.user_id != user_id:
        raise ValueError("no such version")
    save_profile(session, user_id, LifeProfile.model_validate(version.data), reason="undo")

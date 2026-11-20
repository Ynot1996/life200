"""Load and save a user's life profile."""

from sqlalchemy.orm import Session

from life200.db.models import LifeProfileRow
from life200.domain.life import LifeProfile


def load_profile(session: Session, user_id: int) -> LifeProfile:
    row = session.get(LifeProfileRow, user_id)
    return LifeProfile.model_validate(row.data) if row else LifeProfile()


def save_profile(session: Session, user_id: int, profile: LifeProfile) -> None:
    row = session.get(LifeProfileRow, user_id)
    data = profile.model_dump()
    if row is None:
        session.add(LifeProfileRow(user_id=user_id, data=data))
    else:
        row.data = data
    session.flush()

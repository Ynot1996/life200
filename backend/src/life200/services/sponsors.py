"""Store the sponsor register in the database (replacing the previous copy)."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from life200.db.models import SponsorRow
from life200.services.tagging import name_key
from life200.sources.sponsor_register import Sponsor

_BATCH = 5000


def replace_register(session: Session, sponsors: Sequence[Sponsor], register_date: date) -> int:
    session.execute(delete(SponsorRow))
    rows = [
        {
            "name": s.name,
            "name_key": name_key(s.name),
            "town": s.town,
            "county": s.county,
            "rating": s.rating,
            "route": s.route,
            "register_date": register_date,
        }
        for s in sponsors
    ]
    for start in range(0, len(rows), _BATCH):
        session.execute(insert(SponsorRow), rows[start : start + _BATCH])
    return len(rows)

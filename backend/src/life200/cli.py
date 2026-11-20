"""Command-line entry point.

From the project folder:
    make refresh     # sponsor register (if stale) + all default searches + tagging
    make fetch       # one search, see Makefile for options
    make sponsors    # download the latest sponsor register
"""

import argparse
import logging
import sys
from datetime import date

import httpx
from sqlalchemy import func, select

from life200.core.config import get_settings
from life200.db.models import SponsorRow
from life200.db.session import get_sessionmaker
from life200.services.ingest import save_jobs
from life200.services.sponsors import replace_register
from life200.services.tagging import tag_jobs
from life200.sources.adzuna import AdzunaClient, AdzunaError
from life200.sources.sponsor_register import download_register

# The searches `refresh` runs, UK-wide in Adzuna's IT category. Adzuna requires every word to
# match, so broad single words find far more than "junior software engineer". The seniority
# tag then sorts out which jobs are truly junior. Each page of 50 costs one API call.
DEFAULT_SEARCHES = ("junior", "graduate", "entry level", "trainee", "apprentice")
CATEGORY = "it-jobs"
PAGE_DELAY_SECONDS = 3.0  # Adzuna's free tier allows about 25 calls a minute


def _adzuna_client() -> AdzunaClient | None:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        print("Missing LIFE200_ADZUNA_APP_ID or LIFE200_ADZUNA_APP_KEY in .env", file=sys.stderr)
        return None
    return AdzunaClient(
        settings.adzuna_app_id,
        settings.adzuna_app_key.get_secret_value(),
        page_delay_seconds=PAGE_DELAY_SECONDS,
    )


def fetch(what: str, where: str, pages: int, max_days_old: int | None) -> int:
    client = _adzuna_client()
    if client is None:
        return 1
    jobs = list(client.search(what, where=where, pages=pages, max_days_old=max_days_old))

    with get_sessionmaker()() as session, session.begin():  # commits at the end, or rolls back
        result = save_jobs(session, jobs)
        tag_jobs(session)

    print(
        f"Fetched {result.received} jobs for {what!r} in {where}: "
        f"{result.new} new, {result.updated} already saved."
    )
    return 0


def sponsors() -> int:
    with httpx.Client(timeout=120) as http:
        register, register_date = download_register(http)
    with get_sessionmaker()() as session, session.begin():
        count = replace_register(session, register, register_date)
        tag_jobs(session)
    print(f"Loaded {count} licensed sponsors (register dated {register_date}).")
    return 0


def refresh(where: str | None, pages: int, max_days_old: int) -> int:
    with get_sessionmaker()() as session:
        latest = session.scalar(select(func.max(SponsorRow.register_date)))
    if latest is None or latest < date.today():
        sponsors()

    client = _adzuna_client()
    if client is None:
        return 1
    total_new = 0
    for what in DEFAULT_SEARCHES:
        try:
            jobs = list(
                client.search(
                    what, where=where, pages=pages, max_days_old=max_days_old, category=CATEGORY
                )
            )
        except AdzunaError as exc:  # one failed search should not stop the rest
            print(f"  {what!r}: failed ({exc})", file=sys.stderr)
            continue
        with get_sessionmaker()() as session, session.begin():
            result = save_jobs(session, jobs)
        total_new += result.new
        print(f"  {what!r}: {result.received} jobs, {result.new} new")

    with get_sessionmaker()() as session, session.begin():
        tagged = tag_jobs(session)
    print(f"Done: {total_new} new jobs. {tagged} jobs in the database, all re-tagged.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="life200")
    commands = parser.add_subparsers(dest="command", required=True)

    f = commands.add_parser("fetch", help="Fetch one search from Adzuna into the database")
    f.add_argument("what", help='Search keywords, e.g. "junior software engineer"')
    f.add_argument("--where", default="London")
    f.add_argument("--pages", type=int, default=1, help="Pages of 50 jobs (default 1)")
    f.add_argument("--max-days-old", type=int, default=None)

    commands.add_parser("sponsors", help="Download the latest Home Office sponsor register")

    r = commands.add_parser("refresh", help="Sponsor register + all default searches + tagging")
    r.add_argument("--where", default=None, help="A town or region; default is the whole UK")
    r.add_argument("--pages", type=int, default=10, help="Max pages of 50 per search")
    r.add_argument("--max-days-old", type=int, default=30)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    # httpx logs every request URL at INFO, and Adzuna URLs contain the API key.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "fetch":
        return fetch(args.what, args.where, args.pages, args.max_days_old)
    if args.command == "sponsors":
        return sponsors()
    return refresh(args.where, args.pages, args.max_days_old)


if __name__ == "__main__":
    raise SystemExit(main())

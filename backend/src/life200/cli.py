"""Command-line entry point.

Run from backend/:  uv run python -m life200.cli fetch "junior software engineer" --pages 2
Or from the project folder:  make fetch
"""

import argparse
import logging
import sys

from life200.core.config import get_settings
from life200.db.session import get_sessionmaker
from life200.services.ingest import save_jobs
from life200.sources.adzuna import AdzunaClient


def fetch(what: str, where: str, pages: int, max_days_old: int | None) -> int:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        print("Missing LIFE200_ADZUNA_APP_ID or LIFE200_ADZUNA_APP_KEY in .env", file=sys.stderr)
        return 1

    client = AdzunaClient(settings.adzuna_app_id, settings.adzuna_app_key.get_secret_value())
    jobs = list(client.search(what, where=where, pages=pages, max_days_old=max_days_old))

    with get_sessionmaker()() as session, session.begin():  # commits at the end, or rolls back
        result = save_jobs(session, jobs)

    print(
        f"Fetched {result.received} jobs for {what!r} in {where}: "
        f"{result.new} new, {result.updated} already saved."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="life200")
    commands = parser.add_subparsers(dest="command", required=True)

    f = commands.add_parser("fetch", help="Fetch jobs from Adzuna into the database")
    f.add_argument("what", help='Search keywords, e.g. "junior software engineer"')
    f.add_argument("--where", default="London")
    f.add_argument("--pages", type=int, default=1, help="Pages of 50 jobs (default 1)")
    f.add_argument("--max-days-old", type=int, default=None)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx logs every request URL, which contains the API key. Keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return fetch(args.what, args.where, args.pages, args.max_days_old)


if __name__ == "__main__":
    raise SystemExit(main())

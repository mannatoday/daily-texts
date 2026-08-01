from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime

from daily_texts.composition.container import build_container
from daily_texts.infrastructure.config import Settings
from daily_texts.presentation.scheduler import run_scheduler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="daily-texts", description="Moravian Daily Texts pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch and localize today's (or a given) daily text")
    fetch.add_argument("--date", type=_parse_date, default=None, help="Target date YYYY-MM-DD")
    fetch.add_argument("--force", action="store_true", help="Overwrite existing output")
    fetch.add_argument(
        "--formats",
        type=str,
        default=None,
        help="Comma-separated formats: markdown,html,text",
    )
    fetch.add_argument("-v", "--verbose", action="store_true")

    sched = sub.add_parser("run-scheduler", help="Run the daily cron scheduler")
    sched.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose)

    if args.command == "fetch":
        asyncio.run(_cmd_fetch(args))
    elif args.command == "run-scheduler":
        run_scheduler(verbose=args.verbose)
    else:
        parser.error(f"Unknown command: {args.command}")


async def _cmd_fetch(args: argparse.Namespace) -> None:
    settings = Settings()
    if args.formats:
        settings.formats = [f.strip() for f in args.formats.split(",") if f.strip()]  # type: ignore[assignment]

    container = build_container(settings)
    try:
        result = await container.use_case.run(args.date, force=args.force)
    finally:
        await container.aclose()

    if result.skipped:
        logging.getLogger(__name__).warning("Skipped: %s", result.skip_reason)
        print(result.skip_reason)
        return

    out_dir = settings.output_dir / result.raw.date.isoformat()
    print(f"Fetched {result.raw.date_display}")
    print(f"Wrote {len(result.outputs)} file(s) to {out_dir}")
    for item in result.outputs:
        print(f"  - {item.filename}")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _configure_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


if __name__ == "__main__":
    main()

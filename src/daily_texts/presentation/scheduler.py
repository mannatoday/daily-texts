from __future__ import annotations

import asyncio
import logging
from datetime import date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from daily_texts.composition.container import build_container
from daily_texts.infrastructure.config import Settings

logger = logging.getLogger(__name__)


def run_scheduler(*, verbose: bool = False) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    settings = Settings()
    tz = ZoneInfo(settings.schedule_timezone)
    hours = sorted(set(settings.schedule_retry_hours) | {settings.schedule_hour})

    scheduler = BlockingScheduler(timezone=tz)

    for hour in hours:
        trigger = CronTrigger(hour=hour, minute=0, timezone=tz)
        scheduler.add_job(
            _run_job,
            trigger=trigger,
            id=f"daily-texts-{hour:02d}",
            kwargs={"hour": hour},
            replace_existing=True,
        )
        logger.info(
            "Scheduled fetch at %02d:00 %s",
            hour,
            settings.schedule_timezone,
        )

    logger.info("Scheduler started; press Ctrl+C to stop")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def _run_job(*, hour: int) -> None:
    asyncio.run(_async_job(hour=hour))


async def _async_job(*, hour: int) -> None:
    settings = Settings()
    today = date.today()
    logger.info("Scheduler tick hour=%s expecting date=%s", hour, today)

    container = build_container(settings)
    try:
        result = await container.use_case.run(
            force=False,
            expect_date=today,
        )
        if result.skipped:
            logger.warning("Job skipped: %s", result.skip_reason)
        else:
            logger.info(
                "Job complete for %s (%d outputs)",
                result.raw.date,
                len(result.outputs),
            )
    except Exception:
        logger.exception("Scheduled fetch failed")
    finally:
        await container.aclose()

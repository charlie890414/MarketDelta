import asyncio
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_settings
from app.jobs.pipeline import run_fixture_pipeline


def run_pipeline() -> None:
    asyncio.run(run_fixture_pipeline())


def main() -> None:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        "interval",
        hours=settings.pipeline_interval_hours,
        id="market-pipeline",
        replace_existing=True,
        max_instances=1,
        next_run_time=datetime.now(UTC) if settings.pipeline_run_on_start else None,
    )
    scheduler.start()


if __name__ == "__main__":
    main()

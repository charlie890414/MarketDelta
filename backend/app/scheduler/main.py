import asyncio

from apscheduler.schedulers.blocking import BlockingScheduler

from app.jobs.pipeline import run_fixture_pipeline


def run_pipeline() -> None:
    asyncio.run(run_fixture_pipeline())


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        "interval",
        hours=6,
        id="market-pipeline",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()


if __name__ == "__main__":
    main()

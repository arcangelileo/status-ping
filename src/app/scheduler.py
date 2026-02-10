"""
APScheduler integration — manages per-monitor check jobs.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.database import get_session_factory
from app.models.monitor import Monitor
from app.checker import perform_check, prune_old_results

logger = logging.getLogger("statusping.scheduler")

scheduler = AsyncIOScheduler()


async def start_scheduler() -> None:
    """Initialize the scheduler, load all active monitors, schedule checks."""
    async with get_session_factory()() as db:
        result = await db.execute(
            select(Monitor).where(Monitor.is_active == True)  # noqa: E712
        )
        monitors = result.scalars().all()

        for monitor in monitors:
            schedule_monitor(monitor.id, monitor.check_interval)
            logger.info(
                f"Scheduled monitor '{monitor.name}' "
                f"(every {monitor.check_interval}s)"
            )

    # Schedule retention pruning every hour
    scheduler.add_job(
        prune_old_results,
        trigger=IntervalTrigger(hours=1),
        id="prune_old_results",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started with {len(monitors)} monitor(s)")


def schedule_monitor(monitor_id: str, interval_seconds: int) -> None:
    """Add or update a scheduled check job for a monitor."""
    job_id = f"check_{monitor_id}"
    scheduler.add_job(
        perform_check,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id=job_id,
        args=[monitor_id],
        replace_existing=True,
        max_instances=1,
    )


def unschedule_monitor(monitor_id: str) -> None:
    """Remove a scheduled check job for a monitor."""
    job_id = f"check_{monitor_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # Job may not exist


def stop_scheduler() -> None:
    """Shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

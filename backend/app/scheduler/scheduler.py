"""
scheduler/scheduler.py — APScheduler wrapper for automated pipeline runs.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.agents.lead_agent import run_pipeline
from app.database.db import SessionLocal
from app.config import SCHEDULER_INTERVAL_HOURS
from app.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scheduled_run() -> None:
    """Called automatically by APScheduler."""
    logger.info("Scheduler triggered — starting pipeline run …")
    db = SessionLocal()
    try:
        result = run_pipeline(db)
        logger.info("Scheduled run complete: %s", result.to_dict())
    except Exception as exc:
        logger.error("Scheduled run failed: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background scheduler (call once at app startup)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running — skipping start.")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_scheduled_run,
        trigger=IntervalTrigger(hours=SCHEDULER_INTERVAL_HOURS),
        id="lead_agent_job",
        name="AI Lead Agent",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — pipeline will run every %d hour(s).",
        SCHEDULER_INTERVAL_HOURS,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

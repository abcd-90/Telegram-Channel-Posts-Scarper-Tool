import logging
import asyncio
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class ScheduledMirror:
    def __init__(self, enable: bool = False, cron_expr: str = "0 2 * * *"):
        self.enable = enable
        self.cron_expr = cron_expr
        self.scheduler = None

    def start(self, job_func: Callable):
        if not self.enable:
            return

        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            self.scheduler = AsyncIOScheduler()
            trigger = CronTrigger.from_crontab(self.cron_expr)
            self.scheduler.add_job(job_func, trigger=trigger)
            self.scheduler.start()
            logger.info(f"📅 [Scheduler] Next clone scheduled with cron ({self.cron_expr})")
        except Exception as e:
            logger.warning(f"⚠️ [Scheduler] Cron scheduler failed to start ({e}). Continuing real-time mode.")

# valutatrade_hub/parser_service/scheduler.py
import schedule
import time
import threading
import logging
from typing import Optional

from .updater import RatesUpdater
from .config import ParserConfig

logger = logging.getLogger(__name__)


class RatesScheduler:

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self.updater = RatesUpdater(self.config)
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

    def scheduled_update(self):
        logger.info("Running scheduled rates update...")
        try:
            result = self.update.update_rates()

            # Логируем результат
            if result["total_rates"] > 0:
                logger.info(f"Scheduled update successful: {result['total_rates']} rates updated")
            else:
                logger.warning("Scheduled update completed but no rates were updated")

        except Exception as e:
            logger.error(f"Error in scheduled update: {e}")

    def start(self, interval_minutes: int = 15):

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler is already running")
            return

        schedule.every(interval_minutes).minutes.do(self.scheduled_update)

        logger.info("Running initial update...")
        self.scheduled_update()

        self.stop_event.clear()
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="RatesScheduler"
        )
        self.scheduler_thread.start()

        logger.info(f"Scheduler started with {interval_minutes} minute interval")

    def _scheduler_loop(self):
        logger.info("Scheduler loop started")

        while not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(60)

        logger.info("Scheduler loop stopped")

    def stop(self):
        if self.scheduler_thread:
            self.stop_event.set()
            self.scheduler_thread.join(timeout=5)
            self.scheduler_thread = None
            logger.info("Scheduler stopped")

    def run_once(self):
        return self.updater.update_rates()
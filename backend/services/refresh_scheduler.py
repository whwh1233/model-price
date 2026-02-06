"""Background scheduler for periodic full pricing refresh."""

import asyncio
import logging
from contextlib import suppress

from .fetcher import Fetcher

logger = logging.getLogger(__name__)


class RefreshScheduler:
    """Runs periodic full refresh in the background."""

    def __init__(self, interval_seconds: int, include_metadata: bool = True):
        self.interval_seconds = max(interval_seconds, 60)
        self.include_metadata = include_metadata
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        """Start the scheduler loop."""
        if self._task and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="pricing-refresh-scheduler")
        logger.info(
            "Auto refresh scheduler started (interval=%ss, include_metadata=%s)",
            self.interval_seconds,
            self.include_metadata,
        )

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        if not self._task:
            return

        self._stop_event.set()
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task

        self._task = None
        logger.info("Auto refresh scheduler stopped")

    async def _run(self) -> None:
        """Main scheduler loop. First execution happens after one interval."""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
                break
            except TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            try:
                result = await Fetcher.refresh_all(
                    include_metadata=self.include_metadata
                )
                logger.info(
                    "Scheduled full refresh completed: %s models",
                    result["models_count"],
                )
            except Exception:
                logger.exception("Scheduled full refresh failed")

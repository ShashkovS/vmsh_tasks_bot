"""Bounded best-effort ingestion; docs/performance/followups-20261018.md."""

import asyncio
import logging

from prometheus_client import Counter, Gauge

from db_methods.pwa.product_analytics import insert_events

logger = logging.getLogger(__name__)
EVENTS = Counter(
    "vmsh_product_analytics_events", "Best-effort telemetry events", ["outcome"]
)
QUEUED = Gauge(
    "vmsh_product_analytics_queued", "Telemetry events waiting for a batch",
    multiprocess_mode="liveall",
)

READY = Gauge(
    "vmsh_product_analytics_ready", "Product telemetry store is available",
    multiprocess_mode="liveall",
)
STARTUP_FAILURES = Counter(
    "vmsh_product_analytics_startup_failures", "Failed telemetry store startup attempts"
)


class ProductAnalyticsIngestor:
    """One bounded writer per app; domain/audit writes never use this queue."""

    def __init__(self, factory, *, capacity=5120, batch_size=200, delay=0.05):
        if capacity < 20 or batch_size < 1 or delay < 0:
            raise ValueError("Invalid analytics queue limits")
        self.factory = factory
        self.queue = asyncio.Queue(maxsize=capacity)
        self.batch_size = batch_size
        self.delay = delay
        self.closed = False
        self._close_task = None
        self.worker = asyncio.create_task(self._run())

    def submit(self, rows):
        # No await: acceptance of a request batch is atomic on the app loop.
        rows = tuple(tuple(row) for row in rows)
        if self.closed or len(rows) > self.queue.maxsize - self.queue.qsize():
            EVENTS.labels("dropped").inc(len(rows))
            return False
        for row in rows:
            self.queue.put_nowait(row)
        QUEUED.inc(len(rows))
        EVENTS.labels("accepted").inc(len(rows))
        return True

    async def _run(self):
        while True:
            first = await self.queue.get()
            if first is None:
                self.queue.task_done()
                return
            rows = [first]
            QUEUED.dec()
            stop = False
            try:
                deadline = asyncio.get_running_loop().time() + self.delay
                while len(rows) < self.batch_size:
                    try:
                        row = self.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            break
                        try:
                            row = await asyncio.wait_for(self.queue.get(), remaining)
                        except TimeoutError:
                            break
                    if row is None:
                        self.queue.task_done()
                        stop = True
                        break
                    rows.append(row)
                    QUEUED.dec()
                await self.factory.run_write_async(lambda c: insert_events(c, rows))
                EVENTS.labels("written").inc(len(rows))
            except asyncio.CancelledError:
                EVENTS.labels("cancelled").inc(len(rows))
                raise
            except Exception:
                EVENTS.labels("failed").inc(len(rows))
                logger.warning("Product analytics batch failed", exc_info=True)
            finally:
                for _ in rows:
                    self.queue.task_done()
            if stop:
                return

    async def aclose(self, *, timeout=5):
        async def close():
            try:
                async with asyncio.timeout(timeout):
                    if not self.worker.done():
                        await self.queue.put(None)
                    await asyncio.shield(self.worker)
            except asyncio.CancelledError:
                # Legacy shutdown may already cancel background tasks. SQLite
                # cancellation drains its dispatched callback before this ends.
                if not self.worker.cancelled():
                    raise
            except TimeoutError:
                self.worker.cancel()
                try:
                    await self.worker
                except asyncio.CancelledError:
                    pass
            finally:
                while not self.queue.empty():
                    row = self.queue.get_nowait()
                    self.queue.task_done()
                    if row is not None:
                        QUEUED.dec()
                        EVENTS.labels("dropped").inc()

        if self._close_task is None:
            self.closed = True
            self._close_task = asyncio.create_task(close())
        # Keep the store locked until dispatched SQLite work has actually ended.
        await self.factory._drain_on_cancel(self._close_task)

import asyncio

import uvloop
from aiohttp.worker import GunicornWebWorker
from gunicorn.workers import base


class GunicornUVLoopWebWorkerFixed(GunicornWebWorker):
    def init_process(self) -> None:
        # Close any inherited loop if it exists (gunicorn pre-fork quirks)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop is not None and not loop.is_closed():
            loop.close()

        # Install uvloop policy
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        # Create & set a fresh loop for THIS worker process
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Call gunicorn base init_process (NOT aiohttp's again)
        base.Worker.init_process(self)

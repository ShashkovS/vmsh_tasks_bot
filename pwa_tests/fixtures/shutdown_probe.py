"""Credential-free subprocess fixture; vmshpwa/docs/graceful-shutdown.md."""

import asyncio
import os
from pathlib import Path

from aiohttp import web


def stalled_symbolic_worker(pipe):
    """Real child that ignores TERM and never answers; deadline regression."""
    import signal
    import threading

    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pipe.send(("ready",))
    pipe.recv()
    threading.Event().wait()


def create_app():
    if os.environ.get("VMSH_RUNTIME_PROFILE") != "pwa-e2e":
        raise RuntimeError("Shutdown probe requires pwa-e2e")
    from helpers import checkers
    from helpers.config import Config
    from main import create_app as compose

    class Probe:
        @staticmethod
        def configure(app):
            async def symbolic(_request):
                equal = await asyncio.to_thread(checkers.symb_eq, "a+b", "b+a")
                return web.json_response({
                    "pid": os.getpid(),
                    "child": checkers.worker.process.pid,
                    "method": checkers.worker.method,
                    "equal": equal,
                })

            app.router.add_get("/symbolic", symbolic)

    return compose(
        [Probe],
        runtime_config=Config(
            runtime_profile="pwa-e2e",
            config_name="e2e-shutdown-probe",
            pwa_instance="e2e-shutdown-probe",
            db_filename=str(Path(os.environ["VMSH_DB_FILENAME"]).resolve()),
        ),
        analytics_enabled=False,
    )

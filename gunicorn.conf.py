"""Gunicorn hooks shared by the production worker processes."""

import os

from prometheus_client import multiprocess


def child_exit(server, worker) -> None:
    del server
    # The same config is also used by the legacy Telegram Gunicorn service,
    # which does not run in Prometheus multiprocess mode.  Passing ``None`` to
    # prometheus_client makes graceful shutdown fail inside os.path.join().
    # The PWA systemd unit owns this environment variable and directory.
    multiprocess_directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiprocess_directory:
        return
    multiprocess.mark_process_dead(worker.pid, path=multiprocess_directory)

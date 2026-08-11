"""Gunicorn hooks shared by the production PWA worker processes."""

from prometheus_client import multiprocess


def child_exit(server, worker) -> None:
    del server
    multiprocess.mark_process_dead(worker.pid)

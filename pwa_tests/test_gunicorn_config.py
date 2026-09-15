from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

from prometheus_client import multiprocess


ROOT = Path(__file__).resolve().parents[1]


def test_child_exit_marks_prometheus_worker_dead(monkeypatch) -> None:
    observed: list[int] = []
    monkeypatch.setattr(multiprocess, "mark_process_dead", observed.append)
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    config["child_exit"](object(), SimpleNamespace(pid=17942))

    assert observed == [17942]

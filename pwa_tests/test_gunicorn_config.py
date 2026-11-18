from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

from prometheus_client import multiprocess


ROOT = Path(__file__).resolve().parents[1]


def test_child_exit_marks_prometheus_worker_dead(monkeypatch, tmp_path) -> None:
    observed: list[tuple[int, str | None]] = []
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    monkeypatch.setattr(
        multiprocess,
        "mark_process_dead",
        lambda pid, path=None: observed.append((pid, path)),
    )
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    config["child_exit"](object(), SimpleNamespace(pid=17942))

    assert observed == [(17942, str(tmp_path))]


def test_child_exit_is_a_noop_outside_prometheus_multiprocess_mode(
    monkeypatch,
) -> None:
    observed: list[int] = []
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setattr(
        multiprocess,
        "mark_process_dead",
        lambda pid, path=None: observed.append(pid),
    )
    config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

    config["child_exit"](object(), SimpleNamespace(pid=17942))

    assert observed == []

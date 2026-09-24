import fcntl
import sqlite3
from types import SimpleNamespace

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)
from vmshpwa.scripts import course_analytics


def test_iterative_migration_roundtrip(tmp_path):
    path = tmp_path / "analytics.sqlite3"
    current = "0084.pwa_iterative_analytics"
    _apply(path, {m.id for m in _migrations() if m.id < current})
    with sqlite3.connect(path) as db:
        baseline_foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
    _apply(path, {current})
    with sqlite3.connect(path) as db:
        assert "simple_smooth" in [
            r[1] for r in db.execute("PRAGMA table_info(student_lesson_metrics)")
        ]
        # Historical seed migrations leave legacy kv_logins orphans; this
        # migration must introduce no additional violations.
        assert (
            db.execute("PRAGMA foreign_key_check").fetchall() == baseline_foreign_keys
        )
    _rollback(path, {current})
    with sqlite3.connect(path) as db:
        assert "simple_smooth" not in [
            r[1] for r in db.execute("PRAGMA table_info(student_lesson_metrics)")
        ]
    _apply(path, {current})
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_manual_and_timer_run_share_nonblocking_lock(tmp_path, monkeypatch):
    path = tmp_path / "analytics.sqlite3"
    config = SimpleNamespace(
        runtime_profile="pwa-e2e", pwa_instance="test", db_filename=str(path)
    )
    monkeypatch.setattr(course_analytics, "require_current_schema", lambda _: None)

    def must_not_run(*args, **kwargs):
        raise AssertionError("Concurrent calculator must not run")

    monkeypatch.setattr(course_analytics, "calculate_active_courses", must_not_run)
    with open(str(path) + ".analytics.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert course_analytics.run(config) == []

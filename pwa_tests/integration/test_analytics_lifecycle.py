import fcntl
from types import SimpleNamespace

from vmshpwa.scripts import course_analytics


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

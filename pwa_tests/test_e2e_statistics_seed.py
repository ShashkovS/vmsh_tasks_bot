import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from db_methods.pwa import apply_schema_migrations
from vmshpwa.scripts.seed_e2e_statistics import (
    RUN_PUBLIC_ID,
    _require_e2e_target,
    _seed,
)


def _owners(connection: sqlite3.Connection) -> None:
    # Historical migrations seed legacy groups. This disposable fixture owns
    # the complete group set, just like scripts/seed_runtime.py does.
    connection.execute("DELETE FROM groups")
    connection.execute(
        "INSERT INTO seasons "
        "(id, public_id, code, title, starts_on, ends_on, session_expires_on, status, "
        "created_at, updated_at) VALUES "
        "(1, 'season.e2e', 'e2e', 'E2E', '2026-01-01', '2026-12-31', "
        "'2027-08-10', 'active', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    connection.execute(
        "INSERT INTO courses "
        "(id, public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(1, 'course-fixture-math-5-7', 1, 'math', 'Math', 'math', 'active', 1, "
        "'math', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    connection.executemany(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, public_id, course_id, status, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, 1, 0, 1.0, ?, 1, "
        "'active', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        [
            ("н", "н", "Начинающие", 1, 1, "group-fixture-beginner"),
            ("п", "п", "Продолжающие", 2, 0, "group-fixture-continuing"),
        ],
    )
    connection.executemany(
        "INSERT INTO users (id, public_id, type, group_id, name, surname, online) "
        "VALUES (?, ?, 1, ?, 'E2E', 'Student', 1)",
        [
            (101, "user-student-online-fixture", "н"),
            (102, "user-student-in-person-fixture", "п"),
        ],
    )


def test_statistics_seed_is_atomic_and_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "statistics.sqlite3"
    apply_schema_migrations(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _owners(connection)
        assert _seed(connection) == 4
        assert _seed(connection) == 0
        assert (
            connection.execute(
                "SELECT count(*) FROM student_lesson_metrics AS metric "
                "JOIN analytics_runs AS run ON run.id = metric.run_id "
                "WHERE run.public_id = ?",
                (RUN_PUBLIC_ID,),
            ).fetchone()[0]
            == 4
        )


def test_statistics_seed_target_guard_is_exact() -> None:
    allowed = SimpleNamespace(
        runtime_profile="pwa-e2e",
        pwa_instance="e2e",
        db_filename="db/vmshpwa_e2e.sqlite3",
        pwa_media_root=".runtime/vmshpwa/e2e",
    )
    assert _require_e2e_target(allowed).name == "vmshpwa_e2e.sqlite3"

    for changed in (
        SimpleNamespace(**{**vars(allowed), "runtime_profile": "pwa-agent"}),
        SimpleNamespace(**{**vars(allowed), "pwa_instance": "human"}),
        SimpleNamespace(
            **{**vars(allowed), "db_filename": str(Path("db") / "other.sqlite3")}
        ),
    ):
        with pytest.raises(RuntimeError):
            _require_e2e_target(changed)

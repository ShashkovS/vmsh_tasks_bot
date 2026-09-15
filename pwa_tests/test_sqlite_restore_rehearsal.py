from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts import sqlite_restore_rehearsal as rehearsal


RECORDED_AT = "2026-07-30T14:00:00Z"


def _source_database(path: Path) -> Path:
    apply_schema_migrations(path)
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO users "
            "(id, type, group_id, name, surname, token, online) "
            "VALUES (101, 1, 'н', 'Анна', 'Белова', 'secret', 1)"
        )
        connection.execute(
            "INSERT INTO lessons (id, group_id, lesson) VALUES (201, 'н', 1)"
        )
        connection.execute(
            "INSERT INTO problems "
            "(id, group_id, lesson, prob, item, title, prob_text, prob_type, synonyms) "
            "VALUES (301, 'н', 1, 1, '', 'Задача', '', 2, '301')"
        )
        connection.execute(
            "INSERT INTO results "
            "(id, student_id, problem_id, group_id, lesson, ts, verdict) "
            "VALUES (401, 101, 301, 'н', 1, ?, 1)",
            (RECORDED_AT,),
        )
        connection.execute(
            "INSERT INTO written_tasks_discussions "
            "(id, ts, student_id, problem_id, text) "
            "VALUES (501, ?, 101, 301, 'Решение')",
            (RECORDED_AT,),
        )
    return path


@pytest.fixture
def restore_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "restores"
    monkeypatch.setattr(rehearsal, "REHEARSAL_ROOT", root)
    return root


def test_restore_keeps_legacy_rows_and_migrates_only_the_copy(
    tmp_path: Path, restore_root: Path
) -> None:
    source = _source_database(tmp_path / "source.sqlite3")
    target = restore_root / "restored.sqlite3"

    report = rehearsal.rehearse_restore(source, target, RECORDED_AT)

    assert report["legacyRowCounts"] == {
        "users": 1,
        "lessons": 1,
        "problems": 1,
        "results": 1,
        "written_tasks_discussions": 1,
    }
    assert report["legacyRowCountParity"] is True
    assert report["schemaCurrent"] is True
    assert report["integrityCheck"] == "ok"
    assert report["journalMode"] == "wal"
    assert report["sourceDatabaseRowsUpdated"] == 0
    assert report["reportContainsPersonalData"] is False
    assert report["rpoMeasured"] is False
    assert target.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(source) as connection:
        assert connection.execute(
            "SELECT name, surname, token FROM users WHERE id = 101"
        ).fetchone() == ("Анна", "Белова", "secret")


def test_restore_refuses_existing_and_out_of_scope_targets(
    tmp_path: Path, restore_root: Path
) -> None:
    source = _source_database(tmp_path / "source.sqlite3")
    existing = restore_root / "existing.sqlite3"
    existing.parent.mkdir(parents=True)
    existing.touch()

    with pytest.raises(ValueError, match="already exists"):
        rehearsal.rehearse_restore(source, existing, RECORDED_AT)
    with pytest.raises(ValueError, match="below the Phase 11"):
        rehearsal.rehearse_restore(
            source, tmp_path / "outside.sqlite3", RECORDED_AT
        )

"""Executable proof for the one-time classroom Excel import."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo
from openpyxl import Workbook

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from helpers.pwa.classroom_import import (
    ClassroomImportSourceError,
    read_classroom_export,
)
from models.pwa.classroom_import import (
    ClassroomImportRejected,
    analyze_classroom_import,
    apply_classroom_import,
)


MIGRATION_ID = "0060.pwa_classroom_import_receipts"
NOW = "2026-07-29T18:00:00+00:00"


def _migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(selected))


def _rollback(database_path: Path, migration_ids: Collection[str]) -> None:
    selected = _migrations().filter(lambda item: item.id in migration_ids)
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(selected))


def _write_export(path: Path, rows: list[tuple[object, object, object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Итог"
    sheet.append(("Одноразовый экспорт", None, None))
    sheet.append(("IDd", "Уровень", "Аудитория"))
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


def _seed_event(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO users (id, type, name, surname) VALUES "
        "(101, 1, 'Иван', 'Иванов'), "
        "(102, 1, 'Пётр', 'Петров'), "
        "(900, 128, 'Анна', 'Администратор')"
    )
    connection.execute(
        "INSERT INTO seasons "
        "(id, code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) VALUES "
        "(1, '2025-26', '2025/26', '2025-09-01', "
        "'2026-05-31', '2026-08-10', 'active', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO courses "
        "(id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) VALUES "
        "(1, 1, 'math', 'Математика', 'math', 'active', 1, "
        "'math', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO groups "
        "(group_id, short_code, public_name, sort_order, is_active, is_default, "
        "allow_self_switch, is_system, score_weight, course_id, "
        "status, color_key, created_at, updated_at) VALUES "
        "('import-n', 'н', 'Начинающие', 1, 1, 1, 1, 0, 1.0, "
        "1, 'active', 'level-1', ?, ?)",
        (NOW, NOW),
    )
    connection.executemany(
        "INSERT INTO course_enrollments "
        "(id, student_user_id, course_id, active_group_id, "
        "attendance_mode, status, created_at, updated_at) "
        "VALUES (?, ?, 1, 'import-n', 'in_person', 'active', ?, ?)",
        (
            (1, 101, NOW, NOW),
            (2, 102, NOW, NOW),
        ),
    )
    course_lesson_id = connection.execute(
        "INSERT INTO course_lessons "
        "(course_id, lesson_number, created_at, updated_at) "
        "VALUES (1, 41, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    group_lesson_id = connection.execute(
        "INSERT INTO group_lessons "
        "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
        "business_timezone, status, created_at, updated_at) VALUES "
        "(?, 1, 'import-n', '2026-01-01', "
        "'Europe/Moscow', 'active', ?, ?) RETURNING id",
        (course_lesson_id, NOW, NOW),
    ).fetchone()[0]
    event_id = connection.execute(
        "INSERT INTO in_person_events "
        "(season_id, name, starts_at, ends_at, status, "
        "created_by_user_id, updated_by_user_id, created_at, updated_at) VALUES "
        "(1, 'Очное занятие', '2026-02-01T10:00:00Z', "
        "'2026-02-01T13:00:00Z', 'scheduled', 900, 900, ?, ?) RETURNING id",
        (NOW, NOW),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO in_person_event_group_lessons "
        "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
        "VALUES (?, ?, 900, ?)",
        (event_id, group_lesson_id, NOW),
    )


def test_classroom_import_receipt_migration_up_down_up(tmp_path):
    database_path = tmp_path / "classroom-import-migration.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0059.pwa_classroom_assignments"
    }
    preceding = {item.id for item in migrations.values() if item.id != MIGRATION_ID}
    _apply(database_path, preceding)

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE name LIKE 'classroom_import_receipts%'"
            )
        }
        assert names == {"classroom_import_receipts"}
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_schema WHERE name = 'classroom_import_receipts'"
            ).fetchone()
            is None
        )
    _apply(database_path, {MIGRATION_ID})


def test_export_reader_requires_exact_headers_and_normalizes_rooms(tmp_path):
    source = tmp_path / "classrooms.xlsx"
    _write_export(source, [(101, " н ", " Актовый зал ")])

    source_hash, header_row, rows = read_classroom_export(source)

    assert len(source_hash) == 64
    assert header_row == 2
    assert rows == [
        {
            "row_number": 3,
            "user_id": 101,
            "raw_user_id": "101",
            "group_label": "н",
            "room_name": "Актовый зал",
            "room_key": "актовый зал",
        }
    ]

    bad_source = tmp_path / "bad.xlsx"
    workbook = Workbook()
    workbook.active.title = "Итог"
    workbook.active.append(("ID", "Группа", "Комната"))
    workbook.save(bad_source)
    workbook.close()
    with pytest.raises(ClassroomImportSourceError, match="IDd"):
        read_classroom_export(bad_source)


def test_import_reports_blockers_without_writing(tmp_path):
    database_path = tmp_path / "classroom-import-blockers.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    source = tmp_path / "blockers.xlsx"
    _write_export(
        source,
        [
            (101, "н", "Актовый зал"),
            (101, "н", "актовый зал"),
            (999, "неизвестная", "201"),
        ],
    )
    source_hash, header_row, rows = read_classroom_export(source)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_event(connection)
        report, _plan = analyze_classroom_import(
            connection,
            event_public_id="ipe-1",
            source_sha256=source_hash,
            source_sheet="Итог",
            header_row=header_row,
            rows=rows,
        )
        assert report["canApply"] is False
        assert report["issues"]["duplicateStudentIds"] == [101]
        assert report["issues"]["unknownStudentIds"] == [999]
        assert report["issues"]["unknownGroupLabels"] == ["неизвестная"]
        assert report["issues"]["normalizedRoomAliases"] == ["Актовый зал"]
        assert report["issues"]["missingEligibleStudentIds"] == [102]
        assert connection.execute("SELECT count(*) FROM classrooms").fetchone()[0] == 0


def test_reviewed_import_applies_atomically_and_replays(tmp_path):
    database_path = tmp_path / "classroom-import.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    source = tmp_path / "classrooms.xlsx"
    _write_export(source, [(101, "н", " 201 "), (102, "Начинающие", "Актовый зал")])
    source_hash, header_row, rows = read_classroom_export(source)

    with sqlite3.connect(database_path, autocommit=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        _seed_event(connection)
        connection.execute("COMMIT")
        report, _plan = analyze_classroom_import(
            connection,
            event_public_id="ipe-1",
            source_sha256=source_hash,
            source_sheet="Итог",
            header_row=header_row,
            rows=rows,
        )
        assert report["canApply"] is True
        assert report["counts"]["proposedClassrooms"] == 2

        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(ClassroomImportRejected, match="preview hash"):
            apply_classroom_import(
                connection,
                event_public_id="ipe-1",
                source_sha256=source_hash,
                source_sheet="Итог",
                header_row=header_row,
                rows=rows,
                confirmed_source_sha256=source_hash,
                confirmed_preview_sha256="0" * 64,
                actor_user_id=900,
                now=NOW,
            )
        connection.execute("ROLLBACK")
        assert connection.execute("SELECT count(*) FROM classrooms").fetchone()[0] == 0

        connection.execute("BEGIN IMMEDIATE")
        receipt = apply_classroom_import(
            connection,
            event_public_id="ipe-1",
            source_sha256=source_hash,
            source_sheet="Итог",
            header_row=header_row,
            rows=rows,
            confirmed_source_sha256=source_hash,
            confirmed_preview_sha256=str(report["previewSha256"]),
            actor_user_id=900,
            now=NOW,
        )
        connection.execute("COMMIT")

        assert receipt["replayed"] is False
        assert receipt["assignment_count"] == 2
        assert (
            connection.execute(
                "SELECT state FROM classroom_layout_versions"
            ).fetchone()[0]
            == "confirmed"
        )
        assert (
            connection.execute(
                "SELECT state FROM classroom_assignment_plans"
            ).fetchone()[0]
            == "confirmed"
        )
        assert {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT source FROM classroom_assignments"
            )
        } == {"import"}
        assert {
            row[0]
            for row in connection.execute("SELECT normalized_name FROM classrooms")
        } == {"201", "актовый зал"}

        connection.execute("BEGIN IMMEDIATE")
        replay = apply_classroom_import(
            connection,
            event_public_id="ipe-1",
            source_sha256=source_hash,
            source_sheet="Итог",
            header_row=header_row,
            rows=rows,
            confirmed_source_sha256=source_hash,
            confirmed_preview_sha256=str(report["previewSha256"]),
            actor_user_id=900,
            now=NOW,
        )
        connection.execute("COMMIT")
        assert replay["replayed"] is True
        assert (
            connection.execute(
                "SELECT count(*) FROM classroom_import_receipts"
            ).fetchone()[0]
            == 1
        )

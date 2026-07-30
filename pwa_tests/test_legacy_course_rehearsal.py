"""Phase 11 rehearsal of the legacy course/enrollment mapping."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts import legacy_course_rehearsal as rehearsal


RECORDED_AT = "2026-07-30T10:00:00Z"


def _seed_source(path: Path) -> Path:
    apply_schema_migrations(path)
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.executemany(
            "INSERT INTO users "
            "(id, chat_id, type, group_id, name, surname, middlename, token, "
            "online, grade, birthday, allowed_groups) "
            "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    101,
                    700_101,
                    "н",
                    "Анна",
                    "Белова",
                    "Игоревна",
                    "private-token-a",
                    1,
                    6,
                    "2013-02-03",
                    ";н;п;э;",
                ),
                (
                    102,
                    700_102,
                    "э",
                    "Борис",
                    "Ветров",
                    None,
                    "private-token-b",
                    2,
                    7,
                    "2012-04-05",
                    "",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO user_changes_log (ts, user_id, change_type, new_value) "
            "VALUES (?, ?, ?, ?)",
            (
                ("2025-09-01T10:00:00", 101, "G", "н"),
                ("2025-09-02T10:00:00", 101, "G", "н"),
                ("2025-10-01T10:00:00", 101, "G", "п"),
                ("2025-09-01T11:00:00", 101, "O", "1"),
                ("2025-10-01T11:00:00", 101, "O", "2"),
            ),
        )
        connection.executemany(
            "INSERT INTO lessons (id, group_id, lesson) VALUES (?, ?, ?)",
            ((201, "н", 0), (202, "н", 1), (203, "п", 1), (204, "э", 2)),
        )
    path.chmod(0o600)
    return path


@pytest.fixture
def rehearsal_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "phase11-rehearsal"
    monkeypatch.setattr(rehearsal, "REHEARSAL_ROOT", root)
    return root


def test_copy_is_anonymized_and_source_stays_unchanged(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    target = rehearsal_root / "copy.sqlite3"

    fingerprint = rehearsal.prepare_copy(source, target)

    assert len(fingerprint) == 64
    with sqlite3.connect(source) as connection:
        assert connection.execute(
            "SELECT name, surname, chat_id, token, birthday FROM users WHERE id = 101"
        ).fetchone() == (
            "Анна",
            "Белова",
            700_101,
            "private-token-a",
            "2013-02-03",
        )
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT name, surname, middlename, chat_id, token, birthday "
            "FROM users WHERE id = 101"
        ).fetchone() == (
            "Ученик",
            "Тестовый000101",
            None,
            None,
            "rehearsal-token-101",
            "2012-01-18",
        )
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_backfill_preserves_legacy_ids_and_matches_student_state(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)

    report = rehearsal.backfill_course(target, RECORDED_AT)

    assert report == {
        "schemaVersion": 1,
        "operation": "phase11-course-enrollment-rehearsal",
        "recordedAt": RECORDED_AT,
        "coursePublicId": "course-math-5-7",
        "legacyStudents": 2,
        "courseEnrollments": 2,
        "groupsAttached": 4,
        "activeGroupAccessRows": 4,
        "insertedEnrollments": 2,
        "insertedAccessRows": 4,
        "groupMismatches": 0,
        "attendanceModeMismatches": 0,
        "integrityCheck": "ok",
        "reportContainsPersonalData": False,
        "sourceDatabaseRowsUpdated": 0,
        "legacyGroupIdsChanged": 0,
    }
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT group_id, course_id IS NOT NULL FROM groups ORDER BY sort_order"
        ).fetchall() == [("н", 1), ("п", 1), ("э", 1), ("no_level", 1)]
        assert connection.execute(
            "SELECT student_user_id, active_group_id, attendance_mode "
            "FROM course_enrollments ORDER BY student_user_id"
        ).fetchall() == [(101, "н", "online"), (102, "э", "in_person")]
        assert connection.execute(
            "SELECT group_id FROM course_group_access "
            "JOIN course_enrollments ON course_enrollments.id = enrollment_id "
            "WHERE student_user_id = 101 ORDER BY group_id"
        ).fetchall() == [("н",), ("п",), ("э",)]


def test_backfill_is_repeatable(tmp_path: Path, rehearsal_root: Path) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)
    rehearsal.backfill_course(target, RECORDED_AT)

    second = rehearsal.backfill_course(target, RECORDED_AT)

    assert second["insertedEnrollments"] == 0
    assert second["insertedAccessRows"] == 0
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM course_enrollment_events"
            ).fetchone()[0]
            == 2
        )


def test_history_coalesces_no_ops_and_reconciles_current_state(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)
    rehearsal.backfill_course(target, RECORDED_AT)

    first = rehearsal.backfill_enrollment_history(target, RECORDED_AT)
    second = rehearsal.backfill_enrollment_history(target, RECORDED_AT)

    assert first == {
        "legacyHistoryRows": 5,
        "baselineRows": 2,
        "coalescedNoOpRows": 1,
        "transitionEvents": 2,
        "currentStateCorrectionEvents": 2,
        "storedHistoryEvents": 4,
        "insertedHistoryEvents": 4,
        "legacyHistoryRowsUpdated": 0,
        "legacyTimestampSemantics": "preserved-naive",
    }
    assert second["insertedHistoryEvents"] == 0
    assert second["storedHistoryEvents"] == 4
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT event_type, previous_group_id, new_group_id, "
            "previous_attendance_mode, new_attendance_mode "
            "FROM course_enrollment_events WHERE event_type <> 'created' "
            "ORDER BY occurred_at, id"
        ).fetchall() == [
            ("active_group_changed", "н", "п", None, None),
            ("attendance_mode_changed", None, None, "online", "in_person"),
            ("active_group_changed", "п", "н", None, None),
            ("attendance_mode_changed", None, None, "in_person", "online"),
        ]
        assert connection.execute(
            "SELECT new_group_id, new_attendance_mode "
            "FROM course_enrollment_events WHERE enrollment_id = 1 "
            "AND event_type = 'created'"
        ).fetchone() == ("н", "online")


def test_lessons_share_course_identity_and_keep_group_rows(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)
    rehearsal.backfill_course(target, RECORDED_AT)

    first = rehearsal.backfill_lessons(target, RECORDED_AT)
    second = rehearsal.backfill_lessons(target, RECORDED_AT)

    assert first == {
        "legacyLessonRows": 4,
        "legacyLessonZeroRowsExcluded": 1,
        "courseLessons": 2,
        "groupLessons": 3,
        "insertedCourseLessons": 2,
        "insertedGroupLessons": 3,
        "legacyLessonRowsUpdated": 0,
    }
    assert second["insertedCourseLessons"] == 0
    assert second["insertedGroupLessons"] == 0
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT course_lesson.lesson_number, group_lesson.group_id, "
            "group_lesson.cycle_anchor_date "
            "FROM group_lessons AS group_lesson "
            "JOIN course_lessons AS course_lesson "
            "ON course_lesson.id = group_lesson.course_lesson_id "
            "ORDER BY course_lesson.lesson_number, group_lesson.group_id"
        ).fetchall() == [
            (1, "н", "2025-09-01"),
            (1, "п", "2025-09-01"),
            (2, "э", "2025-09-08"),
        ]


def test_copy_refuses_an_existing_or_out_of_scope_target(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    existing = rehearsal_root / "existing.sqlite3"
    existing.parent.mkdir(parents=True)
    existing.touch()

    with pytest.raises(ValueError, match="already exists"):
        rehearsal.prepare_copy(source, existing)
    with pytest.raises(ValueError, match="below .runtime"):
        rehearsal.prepare_copy(source, tmp_path / "outside.sqlite3")


def test_backfill_rejects_an_unmapped_group(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    with sqlite3.connect(source, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, "
            "is_default, allow_self_switch, is_system, score_weight) "
            "VALUES ('future', 'f', 'Future', 200, 1, 0, 1, 0, 1.0)"
        )
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)

    with pytest.raises(RuntimeError, match="group set differs"):
        rehearsal.backfill_course(target, RECORDED_AT)
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT count(*) FROM courses").fetchone()[0] == 0


def test_history_rejects_an_unknown_value_without_partial_events(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    with sqlite3.connect(source, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO user_changes_log (ts, user_id, change_type, new_value) "
            "VALUES ('2026-01-01T10:00:00', 101, 'G', 'future')"
        )
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)
    rehearsal.backfill_course(target, RECORDED_AT)

    with pytest.raises(RuntimeError, match="Unknown group"):
        rehearsal.backfill_enrollment_history(target, RECORDED_AT)
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM course_enrollment_events "
                "WHERE event_type <> 'created'"
            ).fetchone()[0]
            == 0
        )


def test_lessons_reject_an_unmapped_number_without_partial_rows(
    tmp_path: Path, rehearsal_root: Path
) -> None:
    source = _seed_source(tmp_path / "source.sqlite3")
    with sqlite3.connect(source, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO lessons (id, group_id, lesson) VALUES (999, 'н', 99)"
        )
    target = rehearsal_root / "copy.sqlite3"
    rehearsal.prepare_copy(source, target)
    rehearsal.backfill_course(target, RECORDED_AT)

    with pytest.raises(RuntimeError, match="outside the reviewed mapping"):
        rehearsal.backfill_lessons(target, RECORDED_AT)
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute("SELECT count(*) FROM course_lessons").fetchone()[0] == 0
        )

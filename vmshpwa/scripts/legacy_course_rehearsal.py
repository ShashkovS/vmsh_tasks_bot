"""Rehearse the legacy Student-to-course backfill on a disposable database copy.

This is a one-off Phase 11 maintenance command, not runtime application code.
It copies SQLite through the backup API, removes direct user identifiers from
the copy, applies the current migrations, and adds the first course plus its
enrollments.  ``db/vmsh.db`` is opened read-only and is never an apply target.

See ``vmshpwa/dev/development-plan/15-phase-11-hardening-and-rollout.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts.report_io import atomic_write_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITATIVE_DATABASE = REPOSITORY_ROOT / "db" / "vmsh.db"
REHEARSAL_ROOT = REPOSITORY_ROOT / ".runtime" / "phase11-rehearsal"
SEASON_CODE = "2025-26"
COURSE_CODE = "math-5-7"
GROUPS = {
    "н": "beginner",
    "п": "continuing",
    "э": "expert",
    "no_level": "neutral",
}
LESSON_DATES = {
    1: "2025-09-01",
    2: "2025-09-08",
    3: "2025-09-15",
    4: "2025-09-22",
    5: "2025-09-29",
    6: "2025-10-06",
    7: "2025-10-13",
    8: "2025-10-20",
    9: "2025-10-27",
    10: "2025-11-03",
    11: "2025-11-10",
    12: "2025-11-17",
    13: "2025-11-24",
    14: "2025-12-01",
    15: "2025-12-08",
    16: "2025-12-15",
    17: "2025-12-22",
    18: "2025-12-29",
    19: "2026-01-12",
    20: "2026-01-19",
    21: "2026-01-26",
    22: "2026-02-02",
    23: "2026-02-09",
    24: "2026-02-16",
    25: "2026-02-24",
    26: "2026-03-02",
    27: "2026-03-09",
    28: "2026-03-16",
    29: "2026-03-23",
    30: "2026-03-30",
    31: "2026-04-06",
    32: "2026-04-13",
    33: "2026-04-20",
    34: "2026-04-27",
    35: "2026-05-04",
    36: "2026-05-13",
    37: "2026-05-18",
    38: "2026-05-25",
}


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _check_target(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ValueError("Source database does not exist")
    if not _inside(target, REHEARSAL_ROOT):
        raise ValueError("Rehearsal database must be below .runtime/phase11-rehearsal")
    if target.exists():
        raise ValueError("Rehearsal database already exists")
    if source.resolve() == target.resolve():
        raise ValueError("Source and rehearsal database must be different files")


def _source_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_copy(source: Path, target: Path) -> str:
    """Create one anonymized, migrated copy and return the source fingerprint."""

    _check_target(source, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    source_sha256 = _source_sha256(source)
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        with sqlite3.connect(target) as target_connection:
            source_connection.backup(target_connection)
    target.chmod(0o600)

    with sqlite3.connect(target, autocommit=False) as connection:
        connection.execute(
            "UPDATE users SET "
            "name = 'Ученик', "
            "surname = printf('Тестовый%06d', id), "
            "middlename = NULL, "
            "chat_id = NULL, "
            "token = CASE WHEN token IS NULL THEN NULL "
            "ELSE printf('rehearsal-token-%d', id) END, "
            "birthday = CASE WHEN birthday IS NULL THEN NULL "
            "ELSE printf('2012-01-%02d', 1 + (id % 28)) END"
        )
        connection.commit()

    apply_schema_migrations(target)
    return source_sha256


def _parse_allowed_groups(value: object, active_group_id: str) -> set[str]:
    allowed = {
        item.strip() for item in str(value or "").split(";") if item.strip() in GROUPS
    }
    allowed.add(active_group_id)
    return allowed


def _insert_scope(connection: sqlite3.Connection, recorded_at: str) -> int:
    connection.execute(
        "INSERT OR IGNORE INTO seasons "
        "(code, title, starts_on, ends_on, timezone, "
        "session_expires_on, status, created_at, updated_at) "
        "VALUES (?, '2025–26', '2025-08-01', '2026-08-09', "
        "'Europe/Moscow', '2026-08-10', 'active', ?, ?)",
        (SEASON_CODE, recorded_at, recorded_at),
    )
    season = connection.execute(
        "SELECT id FROM seasons WHERE code = ?", (SEASON_CODE,)
    ).fetchone()
    if season is None:
        raise RuntimeError("Could not resolve rehearsal season")
    season_id = int(season[0])
    connection.execute(
        "INSERT OR IGNORE INTO courses "
        "(season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) "
        "VALUES (?, ?, 'Математика 5–7', 'math', 'active', 10, "
        "'math', ?, ?)",
        (season_id, COURSE_CODE, recorded_at, recorded_at),
    )
    course = connection.execute(
        "SELECT id, season_id FROM courses WHERE season_id = ? AND code = ?",
        (season_id, COURSE_CODE),
    ).fetchone()
    if course is None or int(course[1]) != season_id:
        raise RuntimeError("Existing rehearsal course conflicts with the season")
    return int(course[0])


def _course_id(connection: sqlite3.Connection) -> int:
    course = connection.execute(
        "SELECT course.id FROM courses AS course "
        "JOIN seasons AS season ON season.id = course.season_id "
        "WHERE season.code = ? AND course.code = ?",
        (SEASON_CODE, COURSE_CODE),
    ).fetchone()
    if course is None:
        raise RuntimeError("Course enrollment backfill must run first")
    return int(course[0])


def _attach_groups(
    connection: sqlite3.Connection, course_id: int, recorded_at: str
) -> None:
    observed = {
        str(row[0]) for row in connection.execute("SELECT group_id FROM groups")
    }
    if observed != set(GROUPS):
        raise RuntimeError("Legacy group set differs from the reviewed 2025–26 mapping")
    for group_id, color_key in GROUPS.items():
        row = connection.execute(
            "SELECT course_id FROM groups WHERE group_id = ?", (group_id,)
        ).fetchone()
        if row is None or (row[0] is not None and int(row[0]) != course_id):
            raise RuntimeError(f"Legacy group {group_id!r} belongs to another course")
        connection.execute(
            "UPDATE groups SET course_id = ?, color_key = ?, "
            "created_at = COALESCE(created_at, ?), updated_at = ? "
            "WHERE group_id = ?",
            (course_id, color_key, recorded_at, recorded_at, group_id),
        )


def _insert_enrollments(
    connection: sqlite3.Connection, course_id: int, recorded_at: str
) -> tuple[int, int]:
    inserted_enrollments = 0
    inserted_access = 0
    students = connection.execute(
        "SELECT id, group_id, online, allowed_groups FROM users "
        "WHERE type = 1 ORDER BY id"
    ).fetchall()
    for student_id, group_id, online, allowed_groups in students:
        if group_id not in GROUPS or online not in (1, 2):
            raise RuntimeError("A Student has an unmapped group or attendance mode")
        before = connection.total_changes
        connection.execute(
            "INSERT OR IGNORE INTO course_enrollments "
            "(student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (
                student_id,
                course_id,
                group_id,
                "online" if online == 1 else "in_person",
                recorded_at,
                recorded_at,
            ),
        )
        inserted_enrollments += connection.total_changes > before
        enrollment = connection.execute(
            "SELECT id, active_group_id, attendance_mode FROM course_enrollments "
            "WHERE student_user_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        expected_mode = "online" if online == 1 else "in_person"
        if enrollment is None or (enrollment[1], enrollment[2]) != (
            group_id,
            expected_mode,
        ):
            raise RuntimeError("Existing enrollment conflicts with legacy Student data")
        enrollment_id = int(enrollment[0])

        connection.execute(
            "INSERT OR IGNORE INTO course_enrollment_events "
            "(enrollment_id, course_id, event_type, new_group_id, "
            "new_attendance_mode, new_status, source, request_id, occurred_at, created_at) "
            "VALUES (?, ?, 'created', ?, ?, 'active', 'import', ?, ?, ?)",
            (
                enrollment_id,
                course_id,
                group_id,
                expected_mode,
                f"phase11-import:{student_id}",
                recorded_at,
                recorded_at,
            ),
        )
        for allowed_group_id in sorted(
            _parse_allowed_groups(allowed_groups, str(group_id))
        ):
            before = connection.total_changes
            connection.execute(
                "INSERT OR IGNORE INTO course_group_access "
                "(enrollment_id, course_id, group_id, valid_from, reason, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 'legacy import', ?, ?)",
                (
                    enrollment_id,
                    course_id,
                    allowed_group_id,
                    recorded_at,
                    recorded_at,
                    recorded_at,
                ),
            )
            inserted_access += connection.total_changes > before
    return inserted_enrollments, inserted_access


def backfill_course(database: Path, recorded_at: str) -> dict[str, object]:
    """Backfill the first course and return an aggregate parity report."""

    if not _inside(database, REHEARSAL_ROOT):
        raise ValueError("Backfill target must be below .runtime/phase11-rehearsal")
    if database.resolve() == AUTHORITATIVE_DATABASE.resolve():
        raise ValueError("The authoritative database cannot be a backfill target")

    with sqlite3.connect(database, autocommit=False) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        course_id = _insert_scope(connection, recorded_at)
        _attach_groups(connection, course_id, recorded_at)
        inserted_enrollments, inserted_access = _insert_enrollments(
            connection, course_id, recorded_at
        )
        connection.commit()

        legacy_students = connection.execute(
            "SELECT count(*) FROM users WHERE type = 1"
        ).fetchone()[0]
        enrollments = connection.execute(
            "SELECT count(*) FROM course_enrollments WHERE course_id = ?",
            (course_id,),
        ).fetchone()[0]
        access_rows = connection.execute(
            "SELECT count(*) FROM course_group_access WHERE course_id = ? "
            "AND valid_to IS NULL",
            (course_id,),
        ).fetchone()[0]
        group_mismatches = connection.execute(
            "SELECT count(*) FROM users AS student "
            "JOIN course_enrollments AS enrollment "
            "ON enrollment.student_user_id = student.id AND enrollment.course_id = ? "
            "WHERE student.type = 1 AND student.group_id <> enrollment.active_group_id",
            (course_id,),
        ).fetchone()[0]
        mode_mismatches = connection.execute(
            "SELECT count(*) FROM users AS student "
            "JOIN course_enrollments AS enrollment "
            "ON enrollment.student_user_id = student.id AND enrollment.course_id = ? "
            "WHERE student.type = 1 AND "
            "CASE student.online WHEN 1 THEN 'online' ELSE 'in_person' END "
            "<> enrollment.attendance_mode",
            (course_id,),
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        course_public_id = connection.execute(
            "SELECT public_id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()[0]

    if legacy_students != enrollments or group_mismatches or mode_mismatches:
        raise RuntimeError("Course enrollment parity check failed")
    return {
        "schemaVersion": 1,
        "operation": "phase11-course-enrollment-rehearsal",
        "recordedAt": recorded_at,
        "coursePublicId": str(course_public_id),
        "legacyStudents": legacy_students,
        "courseEnrollments": enrollments,
        "groupsAttached": len(GROUPS),
        "activeGroupAccessRows": access_rows,
        "insertedEnrollments": inserted_enrollments,
        "insertedAccessRows": inserted_access,
        "groupMismatches": group_mismatches,
        "attendanceModeMismatches": mode_mismatches,
        "integrityCheck": integrity,
        "reportContainsPersonalData": False,
        "sourceDatabaseRowsUpdated": 0,
        "legacyGroupIdsChanged": 0,
    }


def _history_value(change_type: str, value: str) -> str:
    if change_type == "G":
        if value not in GROUPS:
            raise RuntimeError(f"Unknown group in user_changes_log: {value!r}")
        return value
    if value not in {"1", "2"}:
        raise RuntimeError(f"Unknown attendance mode in user_changes_log: {value!r}")
    return "online" if value == "1" else "in_person"


def _insert_history_event(
    connection: sqlite3.Connection,
    *,
    enrollment_id: int,
    course_id: int,
    change_type: str,
    previous: str,
    new: str,
    request_id: str,
    occurred_at: str,
) -> bool:
    fields = {
        "G": (
            "active_group_changed",
            "previous_group_id",
            "new_group_id",
        ),
        "O": (
            "attendance_mode_changed",
            "previous_attendance_mode",
            "new_attendance_mode",
        ),
    }
    event_type, previous_column, new_column = fields[change_type]
    before = connection.total_changes
    connection.execute(
        f"INSERT OR IGNORE INTO course_enrollment_events "
        f"(enrollment_id, course_id, event_type, "
        f"{previous_column}, {new_column}, source, request_id, occurred_at, created_at) "
        f"VALUES (?, ?, ?, ?, ?, 'import', ?, ?, ?)",
        (
            enrollment_id,
            course_id,
            event_type,
            previous,
            new,
            request_id,
            occurred_at,
            occurred_at,
        ),
    )
    return connection.total_changes > before


def backfill_enrollment_history(database: Path, recorded_at: str) -> dict[str, object]:
    """Convert recoverable G/O transitions without rewriting the legacy log."""

    if not _inside(database, REHEARSAL_ROOT):
        raise ValueError("History target must be below .runtime/phase11-rehearsal")
    with sqlite3.connect(database, autocommit=False) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        course_id = _course_id(connection)
        enrollments = {
            int(row[0]): {
                "id": int(row[1]),
                "group": str(row[2]),
                "mode": str(row[3]),
            }
            for row in connection.execute(
                "SELECT student_user_id, id, active_group_id, attendance_mode "
                "FROM course_enrollments WHERE course_id = ?",
                (course_id,),
            )
        }
        sequences: dict[tuple[int, str], list[tuple[int, str, str]]] = {}
        source_rows = connection.execute(
            "SELECT changes.rowid, changes.user_id, changes.change_type, "
            "changes.new_value, changes.ts "
            "FROM user_changes_log AS changes "
            "JOIN users AS student ON student.id = changes.user_id "
            "WHERE student.type = 1 AND changes.change_type IN ('G', 'O') "
            "ORDER BY changes.user_id, changes.change_type, changes.ts, changes.rowid"
        ).fetchall()
        for rowid, student_id, change_type, new_value, timestamp in source_rows:
            if int(student_id) not in enrollments:
                raise RuntimeError("A legacy history row has no course enrollment")
            normalized = _history_value(str(change_type), str(new_value))
            sequences.setdefault((int(student_id), str(change_type)), []).append(
                (int(rowid), normalized, str(timestamp))
            )

        baseline_rows = 0
        no_op_rows = 0
        transition_events = 0
        correction_events = 0
        inserted_events = 0
        for student_id, enrollment in enrollments.items():
            group_rows = sequences.get((student_id, "G"), [])
            mode_rows = sequences.get((student_id, "O"), [])
            baseline_group = group_rows[0][1] if group_rows else enrollment["group"]
            baseline_mode = mode_rows[0][1] if mode_rows else enrollment["mode"]
            baseline_rows += bool(group_rows) + bool(mode_rows)
            request_id = f"phase11-import:{student_id}"
            connection.execute(
                "UPDATE course_enrollment_events SET new_group_id = ?, "
                "new_attendance_mode = ? WHERE enrollment_id = ? "
                "AND event_type = 'created' AND request_id = ?",
                (baseline_group, baseline_mode, enrollment["id"], request_id),
            )

            for change_type, rows, current_value in (
                ("G", group_rows, enrollment["group"]),
                ("O", mode_rows, enrollment["mode"]),
            ):
                previous = rows[0][1] if rows else current_value
                for rowid, new, timestamp in rows[1:]:
                    if new == previous:
                        no_op_rows += 1
                        continue
                    history_request_id = f"phase11-history:{change_type}:{rowid}"
                    inserted_events += _insert_history_event(
                        connection,
                        enrollment_id=int(enrollment["id"]),
                        course_id=course_id,
                        change_type=change_type,
                        previous=previous,
                        new=new,
                        request_id=history_request_id,
                        occurred_at=timestamp,
                    )
                    transition_events += 1
                    previous = new
                if previous != current_value:
                    correction_request_id = (
                        f"phase11-history-current:{change_type}:{student_id}"
                    )
                    inserted_events += _insert_history_event(
                        connection,
                        enrollment_id=int(enrollment["id"]),
                        course_id=course_id,
                        change_type=change_type,
                        previous=previous,
                        new=str(current_value),
                        request_id=correction_request_id,
                        occurred_at=recorded_at,
                    )
                    correction_events += 1
        connection.commit()
        stored_events = connection.execute(
            "SELECT count(*) FROM course_enrollment_events "
            "WHERE course_id = ? AND event_type <> 'created'",
            (course_id,),
        ).fetchone()[0]

    return {
        "legacyHistoryRows": len(source_rows),
        "baselineRows": baseline_rows,
        "coalescedNoOpRows": no_op_rows,
        "transitionEvents": transition_events,
        "currentStateCorrectionEvents": correction_events,
        "storedHistoryEvents": stored_events,
        "insertedHistoryEvents": inserted_events,
        "legacyHistoryRowsUpdated": 0,
        "legacyTimestampSemantics": "preserved-naive",
    }


def backfill_lessons(database: Path, recorded_at: str) -> dict[str, object]:
    """Create shared course lessons and concrete group lessons for lessons 1+."""

    if not _inside(database, REHEARSAL_ROOT):
        raise ValueError("Lesson target must be below .runtime/phase11-rehearsal")
    with sqlite3.connect(database, autocommit=False) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        course_id = _course_id(connection)
        legacy_rows = connection.execute(
            "SELECT group_id, lesson FROM lessons ORDER BY lesson, group_id"
        ).fetchall()
        mapped_rows = [
            (str(group_id), int(lesson))
            for group_id, lesson in legacy_rows
            if int(lesson) > 0
        ]
        for group_id, lesson_number in mapped_rows:
            if group_id not in GROUPS or lesson_number not in LESSON_DATES:
                raise RuntimeError("A legacy lesson is outside the reviewed mapping")

        inserted_course_lessons = 0
        course_lesson_ids: dict[int, int] = {}
        for lesson_number in sorted({lesson for _group, lesson in mapped_rows}):
            before = connection.total_changes
            connection.execute(
                "INSERT OR IGNORE INTO course_lessons "
                "(course_id, lesson_number, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (course_id, lesson_number, recorded_at, recorded_at),
            )
            inserted_course_lessons += connection.total_changes > before
            row = connection.execute(
                "SELECT id, course_id, lesson_number FROM course_lessons "
                "WHERE course_id = ? AND lesson_number = ?",
                (course_id, lesson_number),
            ).fetchone()
            if row is None or (int(row[1]), int(row[2])) != (
                course_id,
                lesson_number,
            ):
                raise RuntimeError("Existing course lesson conflicts with legacy data")
            course_lesson_ids[lesson_number] = int(row[0])

        inserted_group_lessons = 0
        for group_id, lesson_number in mapped_rows:
            before = connection.total_changes
            connection.execute(
                "INSERT OR IGNORE INTO group_lessons "
                "(course_lesson_id, course_id, group_id, "
                "cycle_anchor_date, business_timezone, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'Europe/Moscow', 'active', ?, ?)",
                (
                    course_lesson_ids[lesson_number],
                    course_id,
                    group_id,
                    LESSON_DATES[lesson_number],
                    recorded_at,
                    recorded_at,
                ),
            )
            inserted_group_lessons += connection.total_changes > before
            row = connection.execute(
                "SELECT course_lesson_id, course_id, group_id, cycle_anchor_date "
                "FROM group_lessons WHERE course_lesson_id = ? AND group_id = ?",
                (course_lesson_ids[lesson_number], group_id),
            ).fetchone()
            expected = (
                course_lesson_ids[lesson_number],
                course_id,
                group_id,
                LESSON_DATES[lesson_number],
            )
            if row is None or tuple(row) != expected:
                raise RuntimeError("Existing group lesson conflicts with legacy data")
        connection.commit()
        stored_course_lessons = connection.execute(
            "SELECT count(*) FROM course_lessons WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        stored_group_lessons = connection.execute(
            "SELECT count(*) FROM group_lessons WHERE course_id = ?", (course_id,)
        ).fetchone()[0]

    if stored_group_lessons != len(mapped_rows):
        raise RuntimeError("Group lesson parity check failed")
    return {
        "legacyLessonRows": len(legacy_rows),
        "legacyLessonZeroRowsExcluded": len(legacy_rows) - len(mapped_rows),
        "courseLessons": stored_course_lessons,
        "groupLessons": stored_group_lessons,
        "insertedCourseLessons": inserted_course_lessons,
        "insertedGroupLessons": inserted_group_lessons,
        "legacyLessonRowsUpdated": 0,
    }


def _normalized_title(title: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", title).split()).casefold()


def reconcile_problem_synonyms(database: Path) -> dict[str, object]:
    """Validate legacy logical synonym sets without moving problem data."""

    if not _inside(database, REHEARSAL_ROOT):
        raise ValueError("Synonym target must be below .runtime/phase11-rehearsal")
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT id, group_id, lesson, title, synonyms FROM problems "
            "WHERE lesson > 0 ORDER BY id"
        ).fetchall()

    problems = {
        int(problem_id): {
            "group": str(group_id),
            "lesson": int(lesson),
            "title": _normalized_title(str(title)),
            "synonyms": str(synonyms),
        }
        for problem_id, group_id, lesson, title, synonyms in rows
    }
    references: dict[int, frozenset[int]] = {}
    for problem_id, problem in problems.items():
        tokens = [token.strip() for token in problem["synonyms"].split(";")]
        if not tokens or any(not token.isdecimal() for token in tokens):
            raise RuntimeError("A legacy problem has an invalid synonym list")
        members = frozenset(int(token) for token in tokens)
        if len(members) != len(tokens) or problem_id not in members:
            raise RuntimeError("A legacy synonym list is duplicated or omits itself")
        references[problem_id] = members

    for problem_id, members in references.items():
        problem = problems[problem_id]
        member_groups: set[str] = set()
        for member_id in members:
            member = problems.get(member_id)
            if member is None:
                raise RuntimeError("A legacy synonym refers to an unknown problem")
            if member["lesson"] != problem["lesson"]:
                raise RuntimeError("A legacy synonym crosses lesson boundaries")
            if references[member_id] != members:
                raise RuntimeError("A legacy synonym set is not reciprocal and complete")
            if member["group"] in member_groups:
                raise RuntimeError("A legacy synonym set repeats one group lesson")
            member_groups.add(member["group"])

    components = {min(members): members for members in references.values()}
    linked_components = {
        root: members for root, members in components.items() if len(members) > 1
    }
    title_groups: dict[tuple[int, str], set[int]] = {}
    for problem_id, problem in problems.items():
        title_groups.setdefault(
            (int(problem["lesson"]), str(problem["title"])), set()
        ).add(problem_id)
    duplicate_titles = [members for members in title_groups.values() if len(members) > 1]
    linked_duplicate_titles = sum(
        1
        for members in duplicate_titles
        if references[min(members)] == frozenset(members)
    )
    same_title_components = sum(
        1
        for members in linked_components.values()
        if len({problems[member_id]["title"] for member_id in members}) == 1
    )

    return {
        "legacyProblems": len(problems),
        "legacySynonymReferences": sum(len(members) for members in references.values()),
        "logicalProblemComponents": len(components),
        "linkedSynonymComponents": len(linked_components),
        "singletonProblemComponents": len(components) - len(linked_components),
        "largestSynonymComponent": max(map(len, components.values()), default=0),
        "duplicateNormalizedTitleGroups": len(duplicate_titles),
        "duplicateTitlesAlreadyLinked": linked_duplicate_titles,
        "duplicateTitlesNotLinked": len(duplicate_titles) - linked_duplicate_titles,
        "linkedComponentsWithSameTitle": same_title_components,
        "linkedComponentsWithDifferentTitles": len(linked_components)
        - same_title_components,
        "legacyProblemRowsUpdated": 0,
        "synonymDataMoved": False,
    }


def audit_written_discussions(database: Path) -> dict[str, object]:
    """Count recoverable legacy written-thread data without reading message bodies."""

    if not database.is_file():
        raise ValueError("Discussion audit database does not exist")
    database_uri = f"{database.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        legacy_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions"
        ).fetchone()[0]
        submission_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions WHERE problem_id > 0"
        ).fetchone()[0]
        question_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions WHERE problem_id < 0"
        ).fetchone()[0]
        zero_problem_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions WHERE problem_id = 0"
        ).fetchone()[0]
        lesson_zero_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE discussion.problem_id > 0 AND problem.lesson = 0"
        ).fetchone()[0]
        product_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0"
        ).fetchone()[0]
        product_threads = connection.execute(
            "SELECT count(*) FROM ("
            "SELECT 1 FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0 "
            "GROUP BY discussion.student_id, discussion.problem_id)"
        ).fetchone()[0]
        product_text_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0 "
            "AND trim(coalesce(discussion.text, '')) <> ''"
        ).fetchone()[0]
        product_attachment_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0 "
            "AND trim(coalesce(discussion.attach_path, '')) <> ''"
        ).fetchone()[0]
        telegram_reference_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0 "
            "AND trim(coalesce(discussion.text, '')) = '' "
            "AND trim(coalesce(discussion.attach_path, '')) = '' "
            "AND discussion.chat_id IS NOT NULL "
            "AND discussion.tg_msg_id IS NOT NULL"
        ).fetchone()[0]
        recoverable_telegram_rows = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE problem.lesson > 0 "
            "AND trim(coalesce(discussion.text, '')) = '' "
            "AND trim(coalesce(discussion.attach_path, '')) = '' "
            "AND EXISTS (SELECT 1 FROM messages_log AS message "
            "WHERE message.chat_id = discussion.chat_id "
            "AND message.tg_msg_id = discussion.tg_msg_id)"
        ).fetchone()[0]
        missing_students = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "LEFT JOIN users AS student ON student.id = discussion.student_id "
            "WHERE student.id IS NULL"
        ).fetchone()[0]
        missing_problems = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "LEFT JOIN problems AS problem ON problem.id = discussion.problem_id "
            "WHERE discussion.problem_id > 0 AND problem.id IS NULL"
        ).fetchone()[0]
        missing_teachers = connection.execute(
            "SELECT count(*) FROM written_tasks_discussions AS discussion "
            "LEFT JOIN users AS teacher ON teacher.id = discussion.teacher_id "
            "WHERE discussion.teacher_id IS NOT NULL AND teacher.id IS NULL"
        ).fetchone()[0]

    if legacy_rows != submission_rows + question_rows + zero_problem_rows:
        raise RuntimeError("Legacy written discussion scope is inconsistent")
    return {
        "legacyDiscussionRows": legacy_rows,
        "submissionDiscussionRows": submission_rows,
        "questionRowsExcluded": question_rows,
        "zeroProblemRows": zero_problem_rows,
        "lessonZeroDiscussionRowsExcluded": lesson_zero_rows,
        "productDiscussionRows": product_rows,
        "productDiscussionThreads": product_threads,
        "productTextRows": product_text_rows,
        "productLocalAttachmentRows": product_attachment_rows,
        "productTelegramReferenceOnlyRows": telegram_reference_rows,
        "telegramReferencesRecoverableFromMessagesLog": recoverable_telegram_rows,
        "missingStudentReferences": missing_students,
        "missingProblemReferences": missing_problems,
        "missingTeacherReferences": missing_teachers,
        "legacyDiscussionRowsUpdated": 0,
        "discussionMigrationReady": False,
        "discussionMigrationBlockers": [
            "owner-reviewed-problem-revisions-required",
            "telegram-media-recovery-required",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--recorded-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    arguments = parser.parse_args()
    discussion_report = audit_written_discussions(arguments.source)
    source_sha256 = prepare_copy(arguments.source, arguments.target)
    report = backfill_course(arguments.target, arguments.recorded_at)
    report.update(backfill_enrollment_history(arguments.target, arguments.recorded_at))
    report.update(backfill_lessons(arguments.target, arguments.recorded_at))
    report.update(reconcile_problem_synonyms(arguments.target))
    report.update(discussion_report)
    report["sourceSha256"] = source_sha256
    atomic_write_text(
        arguments.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

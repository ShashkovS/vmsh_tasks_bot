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
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts.report_io import atomic_write_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITATIVE_DATABASE = REPOSITORY_ROOT / "db" / "vmsh.db"
REHEARSAL_ROOT = REPOSITORY_ROOT / ".runtime" / "phase11-rehearsal"
PUBLIC_ID_NAMESPACE = UUID("1d387e30-c870-4cb9-9c6d-2fa5703014f4")

SEASON_PUBLIC_ID = "season-2025-26"
COURSE_PUBLIC_ID = "course-math-5-7"
GROUPS = {
    "н": ("group-math-5-7-n", "beginner"),
    "п": ("group-math-5-7-p", "continuing"),
    "э": ("group-math-5-7-e", "expert"),
    "no_level": ("group-math-5-7-no-level", "neutral"),
}


def _public_id(prefix: str, value: object) -> str:
    return f"{prefix}.{uuid5(PUBLIC_ID_NAMESPACE, str(value)).hex}"


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
        "(public_id, code, title, starts_on, ends_on, timezone, "
        "session_expires_on, status, created_at, updated_at) "
        "VALUES (?, '2025-26', '2025–26', '2025-08-01', '2026-08-09', "
        "'Europe/Moscow', '2026-08-10', 'active', ?, ?)",
        (SEASON_PUBLIC_ID, recorded_at, recorded_at),
    )
    season = connection.execute(
        "SELECT id FROM seasons WHERE public_id = ?", (SEASON_PUBLIC_ID,)
    ).fetchone()
    if season is None:
        raise RuntimeError("Could not resolve rehearsal season")
    season_id = int(season[0])
    connection.execute(
        "INSERT OR IGNORE INTO courses "
        "(public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at) "
        "VALUES (?, ?, 'math-5-7', 'Математика 5–7', 'math', 'active', 10, "
        "'math', ?, ?)",
        (COURSE_PUBLIC_ID, season_id, recorded_at, recorded_at),
    )
    course = connection.execute(
        "SELECT id, season_id FROM courses WHERE public_id = ?", (COURSE_PUBLIC_ID,)
    ).fetchone()
    if course is None or int(course[1]) != season_id:
        raise RuntimeError("Existing rehearsal course conflicts with the season")
    return int(course[0])


def _attach_groups(
    connection: sqlite3.Connection, course_id: int, recorded_at: str
) -> None:
    observed = {
        str(row[0]) for row in connection.execute("SELECT group_id FROM groups")
    }
    if observed != set(GROUPS):
        raise RuntimeError("Legacy group set differs from the reviewed 2025–26 mapping")
    for group_id, (public_id, color_key) in GROUPS.items():
        row = connection.execute(
            "SELECT course_id FROM groups WHERE group_id = ?", (group_id,)
        ).fetchone()
        if row is None or (row[0] is not None and int(row[0]) != course_id):
            raise RuntimeError(f"Legacy group {group_id!r} belongs to another course")
        connection.execute(
            "UPDATE groups SET public_id = ?, course_id = ?, color_key = ?, "
            "created_at = COALESCE(created_at, ?), updated_at = ? "
            "WHERE group_id = ?",
            (public_id, course_id, color_key, recorded_at, recorded_at, group_id),
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
        public_id = _public_id("enrollment", f"{COURSE_PUBLIC_ID}:{student_id}")
        before = connection.total_changes
        connection.execute(
            "INSERT OR IGNORE INTO course_enrollments "
            "(public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (
                public_id,
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
            "WHERE public_id = ?",
            (public_id,),
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
            "(public_id, enrollment_id, course_id, event_type, new_group_id, "
            "new_attendance_mode, new_status, source, request_id, occurred_at, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, 'active', 'import', ?, ?, ?)",
            (
                _public_id("enrollment-event", public_id),
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

    if legacy_students != enrollments or group_mismatches or mode_mismatches:
        raise RuntimeError("Course enrollment parity check failed")
    return {
        "schemaVersion": 1,
        "operation": "phase11-course-enrollment-rehearsal",
        "recordedAt": recorded_at,
        "coursePublicId": COURSE_PUBLIC_ID,
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
    source_sha256 = prepare_copy(arguments.source, arguments.target)
    report = backfill_course(arguments.target, arguments.recorded_at)
    report["sourceSha256"] = source_sha256
    atomic_write_text(
        arguments.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

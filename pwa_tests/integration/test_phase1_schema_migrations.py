from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT, apply_schema_migrations


AUTH_MIGRATION_ID = "0039.pwa_auth_accounts_sessions"
COURSE_MIGRATION_ID = "0040.pwa_courses_access"
PHASE_1_MIGRATION_IDS = {AUTH_MIGRATION_ID, COURSE_MIGRATION_ID}
BASELINE_MIGRATION_IDS = {
    "0030.initial_merged",
    "0031.check_stat",
    "0032.sos_questions",
    "0033.verdicts",
    "0034.surveys",
    "0035.new_reation",
    "0036.settings_and_texts_from_sheet",
    "0037.groups",
    "0038.kv_logins",
}
PHASE_1_TABLES = {
    "seasons",
    "auth_accounts",
    "family_student_links",
    "auth_sessions",
    "auth_refresh_consumed_secrets",
    "auth_events",
    "auth_throttle_buckets",
    "courses",
    "course_enrollments",
    "course_group_access",
    "course_enrollment_events",
    "staff_scopes",
}
GROUP_PHASE_1_COLUMNS = {
    "public_id",
    "course_id",
    "status",
    "color_key",
    "created_at",
    "updated_at",
    "version",
}
USER_PHASE_1_COLUMNS = {"public_id"}
NOW = "2026-07-27T08:00:00Z"
LATER = "2026-07-27T09:00:00Z"


def _read_migrations():
    return yoyo.read_migrations(str(MIGRATIONS_ROOT))


def _apply_migrations(database_path: Path, migration_ids: Collection[str]) -> None:
    migrations = _read_migrations().filter(
        lambda migration: migration.id in migration_ids
    )
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))


def _rollback_migrations(database_path: Path, migration_ids: Collection[str]) -> None:
    migrations = _read_migrations().filter(
        lambda migration: migration.id in migration_ids
    )
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            backend.rollback_migrations(backend.to_rollback(migrations))


def _product_schema(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE '_yoyo_%' "
        "ORDER BY type, name"
    ).fetchall()


def _product_table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE '_yoyo_%'"
        )
    }


def _table_counts(
    connection: sqlite3.Connection, table_names: Collection[str]
) -> dict[str, int]:
    return {
        table_name: connection.execute(
            f'SELECT count(*) FROM "{table_name}"'
        ).fetchone()[0]
        for table_name in table_names
    }


def _applied_migration_ids(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT migration_id FROM _yoyo_migration ORDER BY migration_id"
        )
    }


def _index_flags(
    connection: sqlite3.Connection, table_name: str
) -> dict[str, tuple[bool, bool]]:
    return {
        row[1]: (bool(row[2]), bool(row[4]))
        for row in connection.execute(f'PRAGMA index_list("{table_name}")')
    }


def _insert_season(connection: sqlite3.Connection, *, suffix: str) -> int:
    return connection.execute(
        "INSERT INTO seasons "
        "(public_id, code, title, starts_on, ends_on, session_expires_on, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?) RETURNING id",
        (
            f"season-{suffix}",
            f"season-code-{suffix}",
            f"Season {suffix}",
            "2026-09-01",
            "2027-05-31",
            "2027-08-10",
            NOW,
            NOW,
        ),
    ).fetchone()[0]


def _insert_course(
    connection: sqlite3.Connection,
    *,
    season_id: int,
    suffix: str,
    actor_user_id: int,
) -> int:
    return connection.execute(
        "INSERT INTO courses "
        "(public_id, season_id, code, name, subject_code, status, sort_order, "
        "accent_key, created_at, updated_at, created_by, updated_by) "
        "VALUES (?, ?, ?, ?, 'math', 'active', 10, 'blue', ?, ?, ?, ?) "
        "RETURNING id",
        (
            f"course-{suffix}",
            season_id,
            f"course-code-{suffix}",
            f"Course {suffix}",
            NOW,
            NOW,
            actor_user_id,
            actor_user_id,
        ),
    ).fetchone()[0]


def _insert_fixture_users(connection: sqlite3.Connection, *, count: int) -> list[int]:
    user_ids = [-(910_000 + index) for index in range(1, count + 1)]
    connection.executemany(
        "INSERT INTO users (id, type, name, surname) VALUES (?, 0, ?, ?)",
        [
            (user_id, f"Fixture {index}", f"User {index}")
            for index, user_id in enumerate(user_ids, start=1)
        ],
    )
    return user_ids


def test_phase1_dependencies_and_empty_database_apply(tmp_path):
    database_path = tmp_path / "empty.sqlite3"
    migrations = {migration.id: migration for migration in _read_migrations()}

    assert {
        dependency.id for dependency in migrations[AUTH_MIGRATION_ID].depends
    } == BASELINE_MIGRATION_IDS
    assert {
        dependency.id for dependency in migrations[COURSE_MIGRATION_ID].depends
    } == {AUTH_MIGRATION_ID}

    state = apply_schema_migrations(database_path)
    assert state.is_current
    assert PHASE_1_MIGRATION_IDS <= {migration_id for migration_id, _ in state.applied}

    with sqlite3.connect(database_path) as connection:
        assert PHASE_1_TABLES <= _product_table_names(connection)
        group_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(groups)")
        }
        assert GROUP_PHASE_1_COLUMNS <= group_columns
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        assert USER_PHASE_1_COLUMNS <= user_columns
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        # The merged legacy seed has pre-existing FK violations. Keep this gate
        # scoped to Phase 1 objects; the upgrade/rollback test below separately
        # proves that this increment does not change the legacy violation count.
        for table_name in sorted(PHASE_1_TABLES | {"groups"}):
            assert (
                connection.execute(
                    f'PRAGMA foreign_key_check("{table_name}")'
                ).fetchall()
                == []
            )


def test_phase1_upgrade_and_exact_rollback_to_0038(tmp_path):
    database_path = tmp_path / "upgrade.sqlite3"
    _apply_migrations(database_path, BASELINE_MIGRATION_IDS)

    with sqlite3.connect(database_path) as connection:
        baseline_schema = _product_schema(connection)
        baseline_tables = _product_table_names(connection)
        baseline_counts = _table_counts(connection, baseline_tables)
        baseline_foreign_key_violation_count = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        assert _applied_migration_ids(connection) == BASELINE_MIGRATION_IDS

    _apply_migrations(database_path, PHASE_1_MIGRATION_IDS)

    with sqlite3.connect(database_path) as connection:
        assert PHASE_1_TABLES <= _product_table_names(connection)
        assert _table_counts(connection, baseline_tables) == baseline_counts
        assert _applied_migration_ids(connection) == (
            BASELINE_MIGRATION_IDS | PHASE_1_MIGRATION_IDS
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback_migrations(database_path, PHASE_1_MIGRATION_IDS)

    with sqlite3.connect(database_path) as connection:
        assert _product_schema(connection) == baseline_schema
        assert _product_table_names(connection) == baseline_tables
        assert _table_counts(connection, baseline_tables) == baseline_counts
        assert _applied_migration_ids(connection) == BASELINE_MIGRATION_IDS
        assert len(connection.execute("PRAGMA foreign_key_check").fetchall()) == (
            baseline_foreign_key_violation_count
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_auth_schema_constraints_indexes_and_soft_revoke(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    apply_schema_migrations(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        user_ids = _insert_fixture_users(connection, count=2)

        student_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES ('account-student', 'student', 'Student', 'student', 1, "
            "'phase1-test', 'telegram_token', 'fixture-student-hash', ?, "
            "'active', ?, ?) RETURNING id",
            (user_ids[0], NOW, NOW),
        ).fetchone()[0]
        family_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "provisioning_source, display_name, credential_kind, "
            "credential_hash, status, created_at, updated_at) "
            "VALUES ('account-family', 'family', 'Family', 'family', "
            "'phase1-test', 'Parent', 'password', 'fixture-family-hash', "
            "'active', ?, ?) RETURNING id",
            (NOW, NOW),
        ).fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "provisioning_source, credential_kind, credential_hash, "
                "linked_user_id, status, created_at, updated_at) "
                "VALUES ('account-unversioned', 'student', 'Unversioned', "
                "'unversioned', 'phase1-test', 'telegram_token', "
                "'fixture-hash', ?, 'active', ?, ?)",
                (user_ids[1], NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_accounts "
                "(public_id, audience, username, username_normalized, "
                "provisioning_source, display_name, credential_kind, status, "
                "created_at, updated_at) VALUES ('account-no-credential', "
                "'family', 'No Credential', 'no-credential', 'phase1-test', "
                "'Parent', 'password', 'active', ?, ?)",
                (NOW, NOW),
            )

        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?)",
            (family_account_id, user_ids[0], NOW, NOW),
        )
        connection.execute(
            "UPDATE family_student_links SET revoked_at = ?, updated_at = ? "
            "WHERE family_account_id = ? AND student_user_id = ?",
            (LATER, LATER, family_account_id, user_ids[0]),
        )
        assert connection.execute(
            "SELECT count(*) FROM family_student_links "
            "WHERE family_account_id = ? AND revoked_at = ?",
            (family_account_id, LATER),
        ).fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO family_student_links "
                "(family_account_id, student_user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (student_account_id, user_ids[1], NOW, NOW),
            )

        session_id = connection.execute(
            "INSERT INTO auth_sessions "
            "(public_id, account_id, audience, refresh_secret_hash, "
            "credential_version, created_at, updated_at, last_seen_at, expires_at) "
            "VALUES ('session-student', ?, 'student', ?, 1, ?, ?, ?, ?) "
            "RETURNING id",
            (student_account_id, "a" * 64, NOW, NOW, NOW, LATER),
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_sessions "
                "(public_id, account_id, audience, refresh_secret_hash, "
                "credential_version, created_at, updated_at, last_seen_at, "
                "expires_at) VALUES ('session-duplicate', ?, 'student', ?, 1, "
                "?, ?, ?, ?)",
                (student_account_id, "a" * 64, NOW, NOW, NOW, LATER),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_sessions "
                "(public_id, account_id, audience, refresh_secret_hash, "
                "credential_version, created_at, updated_at, last_seen_at, "
                "expires_at) VALUES ('session-wrong-audience', ?, 'staff', ?, 1, "
                "?, ?, ?, ?)",
                (student_account_id, "b" * 64, NOW, NOW, NOW, LATER),
            )

        connection.execute(
            "INSERT INTO auth_refresh_consumed_secrets "
            "(session_id, refresh_secret_hash, consumed_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, "d" * 64, NOW, LATER),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_refresh_consumed_secrets "
                "(session_id, refresh_secret_hash, consumed_at, expires_at) "
                "VALUES (?, 'not-a-hmac', ?, ?)",
                (session_id, NOW, LATER),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_refresh_consumed_secrets "
                "(session_id, refresh_secret_hash, consumed_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, "e" * 64, LATER, NOW),
            )
        consumed_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(auth_refresh_consumed_secrets)"
        ).fetchall()
        assert any(
            row[2] == "auth_sessions" and row[6] == "CASCADE"
            for row in consumed_foreign_keys
        )
        assert _index_flags(connection, "auth_refresh_consumed_secrets")[
            "auth_refresh_consumed_secrets_expires_idx"
        ] == (False, False)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE auth_sessions SET version = 0 WHERE id = ?", (session_id,)
            )

        connection.execute(
            "UPDATE auth_sessions SET revoked_at = ?, revoke_reason = 'logout', "
            "updated_at = ?, version = version + 1 WHERE id = ?",
            (LATER, LATER, session_id),
        )
        assert connection.execute(
            "SELECT version, revoked_at FROM auth_sessions WHERE id = ?",
            (session_id,),
        ).fetchone() == (2, LATER)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO auth_throttle_buckets "
                "(audience, bucket_kind, bucket_key_hmac, window_started_at, "
                "created_at, updated_at) VALUES "
                "('student', 'normalized_login', 'raw-login', ?, ?, ?)",
                (NOW, NOW, NOW),
            )
        connection.execute(
            "INSERT INTO auth_throttle_buckets "
            "(audience, bucket_kind, bucket_key_hmac, window_started_at, "
            "created_at, updated_at) VALUES "
            "('student', 'normalized_login', ?, ?, ?, ?)",
            ("c" * 64, NOW, NOW, NOW),
        )

        throttle_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(auth_throttle_buckets)")
        }
        assert "bucket_key_hmac" in throttle_columns
        assert throttle_columns.isdisjoint(
            {"username", "username_normalized", "account_id", "ip_prefix"}
        )
        assert _index_flags(connection, "auth_accounts")[
            "auth_accounts_linked_user_audience_uq"
        ] == (True, True)
        assert _index_flags(connection, "users")["users_public_id_uq"] == (
            True,
            True,
        )
        assert _index_flags(connection, "auth_throttle_buckets")[
            "auth_throttle_buckets_locked_idx"
        ] == (False, True)
        assert (
            connection.execute("PRAGMA foreign_key_check(auth_sessions)").fetchall()
            == []
        )


def test_course_access_constraints_indexes_and_course_ownership(tmp_path):
    database_path = tmp_path / "courses.sqlite3"
    apply_schema_migrations(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        user_ids = _insert_fixture_users(connection, count=3)
        group_ids = [
            row[0]
            for row in connection.execute(
                "SELECT group_id FROM groups ORDER BY group_id LIMIT 2"
            )
        ]
        assert len(group_ids) == 2
        assert connection.execute(
            "SELECT count(*) = count(distinct public_id) "
            "AND count(*) = count(public_id) FROM groups"
        ).fetchone() == (1,)

        season_id = _insert_season(connection, suffix="main")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO courses "
                "(public_id, season_id, code, name, subject_code, status, "
                "sort_order, accent_key, created_at, updated_at) VALUES "
                "('course-invalid', ?, 'invalid', 'Invalid', 'math', "
                "'published', 0, 'blue', ?, ?)",
                (season_id, NOW, NOW),
            )
        first_course_id = _insert_course(
            connection,
            season_id=season_id,
            suffix="first",
            actor_user_id=user_ids[0],
        )
        second_course_id = _insert_course(
            connection,
            season_id=season_id,
            suffix="second",
            actor_user_id=user_ids[0],
        )
        connection.execute(
            "UPDATE groups SET course_id = ?, color_key = 'blue', updated_at = ? "
            "WHERE group_id = ?",
            (first_course_id, NOW, group_ids[0]),
        )
        connection.execute(
            "UPDATE groups SET course_id = ?, color_key = 'green', updated_at = ? "
            "WHERE group_id = ?",
            (second_course_id, NOW, group_ids[1]),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE groups SET status = 'unknown' WHERE group_id = ?",
                (group_ids[0],),
            )

        enrollment_id = connection.execute(
            "INSERT INTO course_enrollments "
            "(public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) "
            "VALUES ('enrollment-first', ?, ?, ?, 'online', 'active', ?, ?) "
            "RETURNING id",
            (user_ids[0], first_course_id, group_ids[0], NOW, NOW),
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) "
                "VALUES ('enrollment-cross-course', ?, ?, ?, 'online', "
                "'active', ?, ?)",
                (user_ids[1], first_course_id, group_ids[1], NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE course_enrollments SET attendance_mode = 'in-person' "
                "WHERE id = ?",
                (enrollment_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE course_enrollments SET status = 'unknown' WHERE id = ?",
                (enrollment_id,),
            )

        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (enrollment_id, first_course_id, group_ids[0], NOW, NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_group_access "
                "(enrollment_id, course_id, group_id, valid_from, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (enrollment_id, first_course_id, group_ids[0], LATER, NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_group_access "
                "(enrollment_id, course_id, group_id, valid_from, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (enrollment_id, first_course_id, group_ids[1], LATER, NOW, NOW),
            )

        connection.execute(
            "UPDATE course_group_access SET valid_to = ?, revoked_by = ?, "
            "updated_at = ?, version = version + 1 "
            "WHERE enrollment_id = ? AND group_id = ? AND valid_from = ?",
            (LATER, user_ids[0], LATER, enrollment_id, group_ids[0], NOW),
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, ?, '2026-07-27T10:00:00Z', ?, ?)",
            (enrollment_id, first_course_id, group_ids[0], LATER, LATER),
        )
        assert connection.execute(
            "SELECT count(*) FROM course_group_access WHERE enrollment_id = ?",
            (enrollment_id,),
        ).fetchone() == (2,)

        connection.execute(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, "
            "updated_at) VALUES (?, ?, ?, 'teacher', ?, ?, ?)",
            (user_ids[2], first_course_id, group_ids[0], NOW, NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO staff_scopes "
                "(staff_user_id, course_id, group_id, role, valid_from, "
                "created_at, updated_at) VALUES (?, ?, ?, 'teacher', ?, ?, ?)",
                (user_ids[2], first_course_id, group_ids[1], NOW, NOW, NOW),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO staff_scopes "
                "(staff_user_id, course_id, role, valid_from, created_at, "
                "updated_at) VALUES (?, ?, 'owner', ?, ?, ?)",
                (user_ids[2], first_course_id, NOW, NOW, NOW),
            )

        connection.execute(
            "INSERT INTO course_enrollment_events "
            "(public_id, enrollment_id, course_id, event_type, new_group_id, "
            "new_attendance_mode, new_status, source, request_id, occurred_at, "
            "created_at) VALUES ('event-created', ?, ?, 'created', ?, 'online', "
            "'active', 'import', 'request-created', ?, ?)",
            (enrollment_id, first_course_id, group_ids[0], NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO course_enrollment_events "
                "(public_id, enrollment_id, course_id, event_type, "
                "previous_group_id, new_group_id, source, request_id, "
                "occurred_at, created_at) VALUES ('event-cross-course', ?, ?, "
                "'active_group_changed', ?, ?, 'staff', 'request-cross', ?, ?)",
                (
                    enrollment_id,
                    first_course_id,
                    group_ids[0],
                    group_ids[1],
                    LATER,
                    LATER,
                ),
            )

        assert _index_flags(connection, "groups")["groups_course_group_uq"] == (
            True,
            False,
        )
        assert _index_flags(connection, "course_group_access")[
            "course_group_access_one_active_uq"
        ] == (True, True)
        assert _index_flags(connection, "staff_scopes")[
            "staff_scopes_one_active_group_role_uq"
        ] == (True, True)
        for table_name in (
            "groups",
            "course_enrollments",
            "course_group_access",
            "course_enrollment_events",
            "staff_scopes",
        ):
            assert (
                connection.execute(
                    f'PRAGMA foreign_key_check("{table_name}")'
                ).fetchall()
                == []
            )

"""Synthetic legacy-domain database for characterization tests only."""

from __future__ import annotations

import db_methods as db
import pytest


@pytest.fixture()
def legacy_domain_db(tmp_path):
    """Open a fresh migrated SQLite without importing any historical user rows."""

    db.sql.disconnect()
    database_path = tmp_path / "legacy-domain.sqlite3"
    db.sql.setup(str(database_path))
    with db.sql.conn as connection:
        # Migration 0038 carries historical credential-shaped rows. They are
        # irrelevant to domain characterization and must never become fixtures.
        connection.execute("DELETE FROM kv_logins")
        for group_id, sort_order in (("alpha", 10), ("beta", 20), ("gamma", 30)):
            connection.execute(
                """
                INSERT INTO groups (
                    group_id, short_code, public_name, sort_order, is_active,
                    is_default, allow_self_switch, is_system, score_weight
                ) VALUES (?, ?, ?, ?, 1, 0, 1, 0, 1.0)
                """,
                (group_id, group_id[0], group_id.title(), sort_order),
            )
        connection.executemany(
            """
            INSERT INTO users (
                id, chat_id, type, group_id, name, surname, token, online,
                allowed_groups
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, 1, ';alpha;beta;gamma;')
            """,
            (
                (1, 1, "alpha", "Student", "Synthetic", "student-synthetic"),
                (10, 2, "alpha", "Teacher", "One", "teacher-one"),
                (11, 2, "beta", "Teacher", "Two", "teacher-two"),
            ),
        )
        assert (
            connection.execute("SELECT COUNT(*) AS count FROM kv_logins").fetchone()[
                "count"
            ]
            == 0
        )
    try:
        yield db
    finally:
        db.sql.disconnect()

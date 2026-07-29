"""Phase-7 proof for explicit classroom-assignment announcements."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from pathlib import Path

import pytest
import yoyo

from db_methods.pwa.classroom_delivery import (
    claim_next_telegram_recipient,
    finish_telegram_batch,
    finish_telegram_recipient,
)
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from models.pwa.classroom_delivery import (
    ClassroomDeliveryConflict,
    InvalidClassroomDelivery,
    create_classroom_delivery_batch,
    preview_classroom_delivery,
    read_classroom_delivery_batch,
    read_latest_classroom_delivery_batch,
)
from models.pwa.classroom_public import read_student_classroom_assignments
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _insert_parents,
)


MIGRATION_ID = "0061.pwa_classroom_assignment_delivery"


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


def _objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE name LIKE 'classroom_assignment_delivery%' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_delivery_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "phase7-delivery-schema.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0060.pwa_classroom_import_receipts"
    }
    _apply(database_path, {item.id for item in migrations.values()} - {MIGRATION_ID})
    assert _objects(database_path) == set()

    expected = {
        "classroom_assignment_delivery_batches",
        "classroom_assignment_delivery_batches_plan_idx",
        "classroom_assignment_delivery_recipients",
        "classroom_assignment_delivery_recipients_student_idx",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected


def _seed_delivery(connection: sqlite3.Connection) -> None:
    _insert_parents(connection)
    connection.execute("UPDATE users SET chat_id = 179179 WHERE id = 1")
    connection.execute(
        "INSERT INTO auth_accounts "
        "(public_id, audience, username, username_normalized, "
        "username_algorithm_version, provisioning_source, credential_kind, "
        "credential_hash, linked_user_id, status, created_at, updated_at) "
        "VALUES ('student-delivery-account', 'student', 'student-delivery', "
        "'student-delivery', 1, 'synthetic-test', 'telegram_token', 'hash', 1, "
        "'active', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "UPDATE classroom_assignment_plans SET state = 'confirmed', "
        "confirmed_by_user_id = 2, confirmed_at = ?, updated_at = ?, version = 2",
        (NOW, NOW),
    )


def test_preview_and_batch_keep_private_destination_server_side(tmp_path):
    database_path = tmp_path / "phase7-delivery.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_delivery(connection)

        preview = preview_classroom_delivery(
            connection, plan_public_id="plan-assignment"
        )
        assert (preview["recipient_count"], preview["changed_count"]) == (1, 1)
        assert preview["telegram_unavailable_count"] == 0
        assert preview["recipients"][0]["telegram_available"] is True
        assert "telegram_chat_id" not in preview["recipients"][0]

        created = create_classroom_delivery_batch(
            connection,
            public_id="delivery-first",
            plan_public_id="plan-assignment",
            expected_plan_version=2,
            expected_snapshot_hash=str(preview["snapshot_hash"]),
            actor_user_id=2,
            pwa_selected=True,
            telegram_selected=True,
            idempotency_key="delivery-key-1",
            now="2026-07-29T13:02:00Z",
        )
        assert created["batch"]["state"] == "queued"
        assert created["recipients"][0]["pwa_state"] == "sent"
        assert created["recipients"][0]["telegram_state"] == "queued"
        assert "telegram_chat_id" not in created["recipients"][0]

        public = read_student_classroom_assignments(connection, 1)[0]
        assert public["announced_at"] == "2026-07-29T13:02:00Z"

        repeated = create_classroom_delivery_batch(
            connection,
            public_id="ignored-on-retry",
            plan_public_id="plan-assignment",
            expected_plan_version=2,
            expected_snapshot_hash=str(preview["snapshot_hash"]),
            actor_user_id=2,
            pwa_selected=True,
            telegram_selected=True,
            idempotency_key="delivery-key-1",
            now="2026-07-29T13:03:00Z",
        )
        assert repeated["batch"]["public_id"] == "delivery-first"
        assert (
            read_latest_classroom_delivery_batch(connection, "plan-assignment")[
                "batch"
            ]["public_id"]
            == "delivery-first"
        )

        next_preview = preview_classroom_delivery(
            connection, plan_public_id="plan-assignment"
        )
        assert next_preview["changed_count"] == 0


def test_latest_delivery_is_empty_before_first_send(tmp_path):
    database_path = tmp_path / "phase7-delivery-empty.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_delivery(connection)
        assert (
            read_latest_classroom_delivery_batch(connection, "plan-assignment") is None
        )


def test_telegram_recipient_is_claimed_once_and_failure_finishes_batch(tmp_path):
    database_path = tmp_path / "phase7-delivery-claim.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_delivery(connection)
        preview = preview_classroom_delivery(
            connection, plan_public_id="plan-assignment"
        )
        create_classroom_delivery_batch(
            connection,
            public_id="delivery-claim",
            plan_public_id="plan-assignment",
            expected_plan_version=2,
            expected_snapshot_hash=str(preview["snapshot_hash"]),
            actor_user_id=2,
            pwa_selected=False,
            telegram_selected=True,
            idempotency_key="delivery-claim-key",
            now=NOW,
        )

        claimed = claim_next_telegram_recipient(connection, "delivery-claim")
        assert claimed is not None
        assert claim_next_telegram_recipient(connection, "delivery-claim") is None
        assert finish_telegram_recipient(
            connection,
            batch_id=int(claimed["batch_id"]),
            course_enrollment_id=int(claimed["course_enrollment_id"]),
            state="failed",
            error_code="telegram_forbidden",
            sent_at=None,
        )
        finish_telegram_batch(connection, "delivery-claim", NOW)

        result = read_classroom_delivery_batch(connection, "delivery-claim")
        assert result["batch"]["state"] == "completed_with_errors"
        assert result["recipients"][0]["telegram_error_code"] == ("telegram_forbidden")


def test_delivery_rejects_stale_preview_and_unconfirmed_plan(tmp_path):
    database_path = tmp_path / "phase7-delivery-conflicts.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_delivery(connection)
        preview = preview_classroom_delivery(
            connection, plan_public_id="plan-assignment"
        )

        with pytest.raises(ClassroomDeliveryConflict, match="preview_changed"):
            create_classroom_delivery_batch(
                connection,
                public_id="delivery-conflict",
                plan_public_id="plan-assignment",
                expected_plan_version=2,
                expected_snapshot_hash="0" * 64,
                actor_user_id=2,
                pwa_selected=True,
                telegram_selected=False,
                idempotency_key="delivery-key-conflict",
                now=NOW,
            )

        connection.execute(
            "UPDATE classroom_assignment_plans SET state = 'superseded', "
            "superseded_at = ?, updated_at = ?",
            (NOW, NOW),
        )
        with pytest.raises(InvalidClassroomDelivery, match="plan_not_confirmed"):
            preview_classroom_delivery(
                connection,
                plan_public_id="plan-assignment",
                expected_version=int(preview["plan_version"]),
            )

"""Phase-8 proof for Student notifications after a Staff support reply."""

from __future__ import annotations

import json

from db_methods.pwa.support import AppendStaffSupportEntryCommand
from models.pwa.support_notifications import create_staff_reply_notifications
from pwa_tests.integration import test_support_thread_repository as support_repository


support_fixture = support_repository.support_fixture


def _seed_student_account(fixture: support_repository.SupportFixture) -> None:
    now = support_repository._timestamp(support_repository.NOW)
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES ('support-account-student', 'student', 'support-student', "
            "'support-student', 1, 'synthetic-test', 'telegram_token', 'hash', ?, "
            "'active', ?, ?)",
            (support_repository.STUDENT_ID, now, now),
        )
    )


async def test_staff_reply_creates_one_idempotent_student_event(support_fixture):
    fixture = support_fixture
    _seed_student_account(fixture)
    thread = await fixture.repository.create_student_thread(
        support_repository._create_problem_command()
    )

    # A Student-authored entry is not a notification source.
    assert (
        fixture.factory.run_write(
            lambda connection: create_staff_reply_notifications(
                connection,
                student_account_public_ids=("support-account-student",),
                thread_public_id=thread.thread_public_id,
            )
        )
        == 0
    )

    fixture.clock.value = support_repository.NOW
    command = AppendStaffSupportEntryCommand(
        staff_user_id=support_repository.TEACHER_ID,
        author_kind="teacher",
        thread_public_id=thread.thread_public_id,
        text="Посмотрите на перестановку двух случаев.",
        client_created_at=fixture.clock.value,
        idempotency_key="support-notification-teacher-reply",
        scope=support_repository.GROUP_A_SCOPE,
    )
    reply = await fixture.repository.append_staff_entry(command)
    assert reply.entries[-1].author_kind == "teacher"

    def record_notification(connection):
        return create_staff_reply_notifications(
            connection,
            student_account_public_ids=(
                "support-account-student",
                "support-account-student",
                "missing-account",
            ),
            thread_public_id=thread.thread_public_id,
        )

    assert fixture.factory.run_write(record_notification) == 1
    assert fixture.factory.run_write(record_notification) == 0

    row = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT category, dedupe_key, route, payload_json, occurred_at, "
            "deliver_after FROM notification_events"
        ).fetchone()
    )
    assert row["category"] == "thread_updated"
    assert row["dedupe_key"] == reply.entries[-1].entry_public_id
    assert row["route"] == f"/student/questions/{thread.thread_public_id}"
    assert json.loads(row["payload_json"]) == {
        "threadId": thread.thread_public_id,
        "entryId": reply.entries[-1].entry_public_id,
    }
    assert row["deliver_after"] == row["occurred_at"]

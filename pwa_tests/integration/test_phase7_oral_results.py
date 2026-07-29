"""Phase-7 proof for recording online oral results in the legacy ledger."""

from __future__ import annotations

import sqlite3

from pwa_tests.integration import test_content_http_api as content_support
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0071.pwa_oral_results_idempotency"
content_http = content_support.content_http


def test_oral_result_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "oral-results.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0070.pwa_oral_windows"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(zoom_conversation)")
        }
        assert "pwa_idempotency_key" in columns
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_schema "
                "WHERE name = 'zoom_conversation_pwa_idempotency_uq'"
            ).fetchone()[0]
            == 1
        )

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(zoom_conversation)")
        }
        assert "pwa_idempotency_key" not in columns
    _apply(database_path, {MIGRATION_ID})


def _result_payload(problem_id: str, **changes) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "studentId": "user-content-student",
        "idempotencyKey": "oral-round-41-student-1",
        "marks": [{"problemId": problem_id, "outcome": "accepted"}],
        "reactionId": 300,
    }
    payload.update(changes)
    return payload


async def test_teacher_records_oral_round_once_in_legacy_tables(content_http):
    fixture = content_http
    problem_id, _revision_id = await content_support._prepare_published_test_problem(
        fixture,
        problem_type=3,
    )
    path = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/oral-results"
    roster = await fixture.client.get(
        f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/oral-roster",
        headers=content_support._headers(),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert roster.status == 200, await roster.text()
    roster_body = await roster.json()
    assert roster_body["students"] == [
        {
            "studentId": "user-content-student",
            "displayName": "Тестова Ирина",
        }
    ]
    assert roster_body["problems"] == [
        {
            "problemId": problem_id,
            "displayNumber": "1",
            "title": "Письменная задача",
        }
    ]

    payload = _result_payload(problem_id)
    created = await fixture.client.post(
        path,
        json=payload,
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert created.status == 201, await created.text()
    assert (await created.json())["replayed"] is False

    replayed = await fixture.client.post(
        path,
        json=payload,
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert replayed.status == 200, await replayed.text()
    assert (await replayed.json())["replayed"] is True

    conflict = await fixture.client.post(
        path,
        json=_result_payload(
            problem_id,
            marks=[{"problemId": problem_id, "outcome": "rejected"}],
        ),
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert conflict.status == 409

    def ledger(connection):
        conversation = connection.execute(
            "SELECT id, student_id, teacher_id, lesson, group_id "
            "FROM zoom_conversation WHERE pwa_idempotency_key = ?",
            (payload["idempotencyKey"],),
        ).fetchone()
        results = connection.execute(
            "SELECT verdict, res_type, zoom_conversation_id FROM results "
            "WHERE zoom_conversation_id = ?",
            (conversation["id"],),
        ).fetchall()
        reactions = connection.execute(
            "SELECT reaction_id, reaction_type_id FROM reactions "
            "WHERE zoom_conversation_id = ?",
            (conversation["id"],),
        ).fetchall()
        return (
            dict(conversation),
            [
                (row["verdict"], row["res_type"], row["zoom_conversation_id"])
                for row in results
            ],
            [(row["reaction_id"], row["reaction_type_id"]) for row in reactions],
        )

    conversation, results, reactions = fixture.factory.run_read(ledger)
    assert conversation == {
        "id": conversation["id"],
        "student_id": content_support.STUDENT_USER_ID,
        "teacher_id": content_support.TEACHER_USER_ID,
        "lesson": 41,
        "group_id": "content-a",
    }
    assert results == [(18, 3, conversation["id"])]
    assert reactions == [(300, 300)]


async def test_invalid_or_in_person_oral_result_does_not_write(content_http):
    fixture = content_http
    problem_id, _revision_id = await content_support._prepare_published_test_problem(
        fixture,
        problem_type=3,
    )
    path = f"/staff/api/v1/group-lessons/{fixture.group_lesson_a}/oral-results"

    invalid_reaction = await fixture.client.post(
        path,
        json=_result_payload(problem_id, reactionId=100),
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert invalid_reaction.status == 422
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS value FROM zoom_conversation "
                "WHERE pwa_idempotency_key = 'oral-round-41-student-1'"
            ).fetchone()["value"]
        )
        == 0
    )

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_enrollments SET attendance_mode = 'in_person' "
            "WHERE public_id = 'enrollment-content-http'"
        )
    )
    unavailable = await fixture.client.post(
        path,
        json=_result_payload(
            problem_id,
            idempotencyKey="oral-round-in-person",
            reactionId=None,
        ),
        headers=content_support._headers(unsafe=True),
        cookies=content_support._cookie(fixture, "teacher"),
    )
    assert unavailable.status == 404
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS value FROM zoom_conversation "
                "WHERE pwa_idempotency_key = 'oral-round-in-person'"
            ).fetchone()["value"]
        )
        == 0
    )

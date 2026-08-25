"""Phase-10 logical synonym preview, merge and split HTTP flow."""

from __future__ import annotations

import json

import pytest

from apps import pwa_app
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    STUDENT_ID,
    _cookies,
    _headers,
    _seed_layout_scope,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _seed_synonym_problems(factory) -> tuple[str, str]:
    now = "2026-07-30T10:00:00Z"

    def write(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'c-1'"
        ).fetchone()["id"]
        course_lesson_id = connection.execute(
            "SELECT id FROM course_lessons "
            "WHERE public_id = 'cl-1'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "('synonym-continuing', 'п', 'Продолжающие', 2, 1, 0, 0, 0, 1.0, "
            "?, 'active', 'continuing', ?, ?)",
            (course_id, now, now),
        )
        continuing_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "(?, ?, 'synonym-continuing', "
            "'2026-10-01', 'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson_id, course_id, now, now),
        ).fetchone()["id"]
        beginner_lesson_id = connection.execute(
            "SELECT id FROM group_lessons "
            "WHERE public_id = 'gl-1'"
        ).fetchone()["id"]

        problem_ids: list[int] = []
        problem_public_ids: list[str] = []
        definitions = (
            (
                "layout-beginner",
                beginner_lesson_id,
                1,
                1,
                2,
            ),
            (
                "synonym-continuing",
                continuing_lesson_id,
                4,
                2,
                None,
            ),
        )
        for index, (
            group_id,
            group_lesson_id,
            problem_number,
            problem_type,
            answer_type,
        ) in enumerate(definitions, 1):
            problem_id = connection.execute(
                "INSERT INTO problems "
                "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                "ans_type, synonyms) VALUES (?, 41, ?, '', 'Расстановка ладей', "
                "'', ?, ?, '') RETURNING id, public_id",
                (
                    group_id,
                    problem_number,
                    problem_type,
                    answer_type,
                ),
            ).fetchone()
            problem_ids.append(int(problem_id["id"]))
            problem_public_ids.append(str(problem_id["public_id"]))
            source_id = connection.execute(
                "INSERT INTO content_sources "
                "(group_lesson_id, kind, logical_filename, source_encoding, "
                "created_by_user_id, created_at) VALUES (?, 'condition', ?, "
                "'utf-8', ?, ?) RETURNING id",
                (
                    group_lesson_id,
                    f"synonym-{index}.tex",
                    ADMIN_ID,
                    now,
                ),
            ).fetchone()["id"]
            revision_id = connection.execute(
                "INSERT INTO content_revisions "
                "(source_id, revision_number, source_sha256, latex_text, "
                "parser_version, status, canonical_json, diagnostics_json, "
                "provenance_json, created_by_user_id, created_at) VALUES "
                "(?, 1, ?, 'Задача', 'test', 'ready', '{}', '[]', '{}', ?, ?) "
                "RETURNING id",
                (
                    source_id,
                    str(index) * 64,
                    ADMIN_ID,
                    now,
                ),
            ).fetchone()["id"]
            connection.execute(
                "INSERT INTO content_problem_matches "
                "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
                "resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
                "VALUES (?, 1, '1', ?, 'auto_position', ?, ?, '[]', ?)",
                (revision_id, int(problem_id["id"]), ADMIN_ID, now, now),
            )
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, answer_type, "
                "answer_config_json, attempt_policy_json, config_version, created_at, "
                "created_by_user_id) VALUES (?, ?, 1, '1', ?, 'Расстановка ладей', "
                "'расстановка ладей', ?, ?, '{}', '{}', 1, ?, ?)",
                (
                    int(problem_id["id"]),
                    revision_id,
                    str(problem_number),
                    problem_type,
                    answer_type,
                    now,
                    ADMIN_ID,
                ),
            )
        result_id = connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, "
            "answer, res_type) VALUES (?, ?, 'layout-beginner', 41, ?, ?, 3, "
            "'Исходный ответ', 1) RETURNING id",
            (STUDENT_ID, problem_ids[0], ADMIN_ID, now),
        ).fetchone()["id"]
        assert result_id is not None
        return tuple(problem_public_ids)

    return factory.run_write(write)


@pytest.mark.asyncio
async def test_synonym_candidates_are_admin_only_and_do_not_require_matching_types(
    classroom_http,
):
    _seed_layout_scope(classroom_http.factory)
    first, second = _seed_synonym_problems(classroom_http.factory)

    teacher = await classroom_http.client.get(
        "/staff/api/v1/course-lessons/cl-1/synonym-candidates",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    response = await classroom_http.client.get(
        "/staff/api/v1/course-lessons/cl-1/synonym-candidates",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    body = await response.json()
    assert len(body["candidates"]) == 1
    assert body["synonymGroups"] == []
    assert [item["problemId"] for item in body["candidates"][0]["problems"]] == [
        first,
        second,
    ]
    assert {item["problemType"] for item in body["candidates"][0]["problems"]} == {
        1,
        2,
    }


@pytest.mark.asyncio
async def test_synonym_merge_and_split_preserve_original_problem_and_result_rows(
    classroom_http,
):
    _seed_layout_scope(classroom_http.factory)
    first, second = _seed_synonym_problems(classroom_http.factory)
    cookies = _cookies(classroom_http, "admin")
    headers = _headers(unsafe=True)

    preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/impact-preview",
        json={
            "schemaVersion": 1,
            "mode": "merge",
            "problemIds": [first, second],
            "synonymId": None,
        },
        headers=headers,
        cookies=cookies,
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = await preview_response.json()
    assert preview["addProblemIds"] == [first, second]
    assert preview["submissionCount"] == 0
    cursors_before_merge = dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"])

    merge_response = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/merge",
        json={
            "schemaVersion": 1,
            "problemIds": [first, second],
            "previewSha256": preview["previewSha256"],
        },
        headers=headers,
        cookies=cookies,
    )
    assert merge_response.status == 200, await merge_response.text()
    merged = await merge_response.json()
    synonym_id = merged["result"]["synonymId"]
    assert merged["result"] == {
        "synonymId": synonym_id,
        "status": "active",
        "version": 1,
        "changed": True,
    }
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        audience: cursor + 1 for audience, cursor in cursors_before_merge.items()
    }

    current_response = await classroom_http.client.get(
        "/staff/api/v1/course-lessons/cl-1/synonym-candidates",
        headers=_headers(),
        cookies=cookies,
    )
    current = await current_response.json()
    assert current["candidates"] == []
    assert current["synonymGroups"][0]["synonymId"] == synonym_id

    stale = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/merge",
        json={
            "schemaVersion": 1,
            "problemIds": [first, second],
            "previewSha256": preview["previewSha256"],
        },
        headers=headers,
        cookies=cookies,
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "problem_synonym_preview_changed"

    split_preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/impact-preview",
        json={
            "schemaVersion": 1,
            "mode": "split",
            "problemIds": [first],
            "synonymId": synonym_id,
        },
        headers=headers,
        cookies=cookies,
    )
    assert split_preview_response.status == 200
    split_preview = await split_preview_response.json()
    assert set(split_preview["removeProblemIds"]) == {first, second}

    split_response = await classroom_http.client.post(
        f"/staff/api/v1/problem-synonyms/{synonym_id}/split",
        json={
            "schemaVersion": 1,
            "problemIds": [first],
            "previewSha256": split_preview["previewSha256"],
            "reason": "Задачи были склеены по ошибке",
        },
        headers=headers,
        cookies=cookies,
    )
    assert split_response.status == 200, await split_response.text()
    assert (await split_response.json())["result"]["status"] == "split"

    def stored(connection):
        problems = connection.execute(
            "SELECT public_id FROM problems WHERE public_id IN (?, ?) ORDER BY public_id",
            (first, second),
        ).fetchall()
        result = connection.execute(
            "SELECT problem.public_id AS problem_public_id, result.answer "
            "FROM results AS result JOIN problems AS problem ON problem.id = result.problem_id "
            "WHERE result.answer = 'Исходный ответ'"
        ).fetchone()
        active_members = connection.execute(
            "SELECT count(*) AS value FROM problem_synonym_members "
            "WHERE removed_at IS NULL"
        ).fetchone()["value"]
        return problems, dict(result), active_members

    problems, result, active_members = classroom_http.factory.run_read(stored)
    assert [row["public_id"] for row in problems] == sorted((first, second))
    assert result["problem_public_id"] == first
    assert result["answer"] == "Исходный ответ"
    assert active_members == 0

    def audit_rows(connection):
        return connection.execute(
            "SELECT action, before_json, after_json FROM audit_events "
            "WHERE object_type = 'problem_synonym' ORDER BY id"
        ).fetchall()

    events = classroom_http.factory.run_read(audit_rows)
    assert [event["action"] for event in events] == [
        "problem_synonym.merged",
        "problem_synonym.split",
    ]
    assert events[0]["before_json"] is None
    assert json.loads(events[0]["after_json"]) == {
        "courseLessonId": "cl-1",
        "status": "active",
        "version": 1,
        "memberCount": 2,
        "addedCount": 2,
    }
    assert json.loads(events[1]["before_json"]) == {
        "status": "active",
        "version": 1,
        "memberCount": 2,
    }
    assert json.loads(events[1]["after_json"]) == {
        "courseLessonId": "cl-1",
        "status": "split",
        "version": 2,
        "memberCount": 0,
        "removedCount": 2,
        "reason": "Задачи были склеены по ошибке",
    }

    timeline = await classroom_http.client.get(
        "/staff/api/v1/audit?objectType=problem_synonym",
        headers=_headers(),
        cookies=cookies,
    )
    assert timeline.status == 200
    timeline_items = (await timeline.json())["items"]
    assert {item["action"] for item in timeline_items} == {
        "problem_synonym.merged",
        "problem_synonym.split",
    }
    assert all(item["objectType"] == "problem_synonym" for item in timeline_items)


@pytest.mark.asyncio
async def test_synonym_merge_rolls_back_when_audit_insert_fails(classroom_http):
    _seed_layout_scope(classroom_http.factory)
    first, second = _seed_synonym_problems(classroom_http.factory)
    cookies = _cookies(classroom_http, "admin")
    headers = _headers(unsafe=True)
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/impact-preview",
        json={
            "schemaVersion": 1,
            "mode": "merge",
            "problemIds": [first, second],
            "synonymId": None,
        },
        headers=headers,
        cookies=cookies,
    )
    preview = await preview_response.json()

    def install_failure(connection):
        connection.execute(
            "CREATE TRIGGER audit_problem_synonym_test_failure "
            "BEFORE INSERT ON audit_events "
            "WHEN new.object_type = 'problem_synonym' BEGIN "
            "SELECT raise(ABORT, 'synthetic audit failure'); END"
        )

    classroom_http.factory.run_write(install_failure)
    merge_response = await classroom_http.client.post(
        "/staff/api/v1/problem-synonyms/merge",
        json={
            "schemaVersion": 1,
            "problemIds": [first, second],
            "previewSha256": preview["previewSha256"],
        },
        headers=headers,
        cookies=cookies,
    )
    assert merge_response.status == 500

    def state(connection):
        groups = connection.execute(
            "SELECT count(*) AS count FROM problem_synonym_groups"
        ).fetchone()["count"]
        members = connection.execute(
            "SELECT count(*) AS count FROM problem_synonym_members"
        ).fetchone()["count"]
        audits = connection.execute(
            "SELECT count(*) AS count FROM audit_events "
            "WHERE object_type = 'problem_synonym'"
        ).fetchone()["count"]
        return groups, members, audits

    assert classroom_http.factory.run_read(state) == (0, 0, 0)

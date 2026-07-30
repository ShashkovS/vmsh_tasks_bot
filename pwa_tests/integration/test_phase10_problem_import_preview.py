"""Phase-10 dry-run for replacing the legacy problem workbook."""

from __future__ import annotations

from io import BytesIO

import pytest
from aiohttp import FormData
from openpyxl import Workbook

from models.pwa.problem_import import COLUMNS
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _workbook(*, lesson: int = 41, synonym_candidate: bool = False) -> bytes:
    workbook = Workbook()
    current = workbook.active
    current.title = "Задачи"
    old = workbook.create_sheet("Старые")
    for sheet in (current, old):
        sheet.append(COLUMNS)
        sheet.append(["Описание"] * len(COLUMNS))
    current.append(
        (
            "н",
            lesson,
            1,
            "",
            "Орехи",
            None,
            "Тест",
            "Натуральное",
            None,
            "Введите число",
            29,
            None,
            "Нет",
            "Да",
        )
    )
    if synonym_candidate:
        current.append(
            (
                "п",
                lesson,
                4,
                "",
                "Орехи",
                None,
                "Письменно",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )
    current.append(
        (
            "н",
            lesson,
            2,
            "",
            "Новая задача",
            None,
            "Письменно",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )
    current.append(
        (
            "нет",
            lesson,
            3,
            "",
            "Чужая группа",
            None,
            "Устно",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _seed_second_group(factory) -> None:
    def write(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "('layout-continuing', 'п', 'Продолжающие', 2, 1, 0, 0, 0, 1.0, "
            "'classroom-layout-group-continuing', ?, 'active', 'continuing', "
            "'2026-07-30T10:00:00Z', '2026-07-30T10:00:00Z')",
            (course_id,),
        )

    factory.run_write(write)


def _form(
    course_id: str = "classroom-layout-course",
    *,
    source_sha256: str | None = None,
    preview_sha256: str | None = None,
    lesson: int = 41,
    source: bytes | None = None,
) -> FormData:
    form = FormData(default_to_multipart=True)
    form.add_field("courseId", course_id)
    form.add_field(
        "workbook",
        source if source is not None else _workbook(lesson=lesson),
        filename="tasks.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if source_sha256 is not None:
        form.add_field("sourceSha256", source_sha256)
    if preview_sha256 is not None:
        form.add_field("previewSha256", preview_sha256)
    return form


def _seed_existing_problem(factory, *, title: str = "Орехи", lesson: int = 41) -> None:
    def write(connection):
        connection.execute(
            "INSERT INTO problems "
            "(public_id, group_id, lesson, prob, item, title, prob_text, prob_type, "
            "ans_type, ans_validation, validation_error, cor_ans, cor_ans_checker, "
            "wrong_ans, congrat, synonyms) VALUES "
            "(?, 'layout-beginner', ?, 1, '', ?, "
            "'', 1, 2, NULL, 'Введите число', '29', NULL, 'Нет', 'Да', '')",
            (f"problem-import-existing-{lesson}", lesson, title),
        )

    factory.run_write(write)


@pytest.mark.asyncio
async def test_problem_import_preview_is_admin_only(classroom_http):
    teacher = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403


@pytest.mark.asyncio
async def test_problem_import_preview_compares_real_sqlite_without_writing(
    classroom_http,
):
    lesson = 44
    _seed_existing_problem(classroom_http.factory, lesson=lesson)
    response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(lesson=lesson),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 200, await response.text()
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.json()
    assert body["summary"] == {
        "rows": 3,
        "create": 1,
        "update": 0,
        "unchanged": 1,
        "invalid": 1,
    }
    assert len(body["previewSha256"]) == 64
    assert body["synonymCandidates"] == []
    assert body["rows"][0]["problemId"] == f"problem-import-existing-{lesson}"
    assert body["rows"][2]["diagnostics"][0]["code"] == "group_unknown"

    def count(connection):
        return connection.execute(
            "SELECT count(*) AS value FROM problems WHERE lesson = ?", (lesson,)
        ).fetchone()["value"]

    assert classroom_http.factory.run_read(count) == 1


@pytest.mark.asyncio
async def test_problem_import_preview_reports_synonym_candidate_without_merging(
    classroom_http,
):
    _seed_second_group(classroom_http.factory)
    response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(source=_workbook(synonym_candidate=True)),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )

    assert response.status == 200, await response.text()
    body = await response.json()
    assert body["summary"]["rows"] == 4
    assert body["synonymCandidates"] == [
        {
            "lessonNumber": 41,
            "normalizedTitle": "орехи",
            "displayTitle": "Орехи",
            "hasGroupConflict": False,
            "members": [
                {
                    "sheet": "Задачи",
                    "row": 3,
                    "groupCode": "н",
                    "groupId": "classroom-layout-group",
                    "problemNumber": 1,
                    "item": "",
                    "problemId": None,
                    "problemType": 1,
                    "answerType": 2,
                },
                {
                    "sheet": "Задачи",
                    "row": 4,
                    "groupCode": "п",
                    "groupId": "classroom-layout-group-continuing",
                    "problemNumber": 4,
                    "item": "",
                    "problemId": None,
                    "problemType": 2,
                    "answerType": None,
                },
            ],
        }
    ]

    def count(connection):
        return connection.execute(
            "SELECT count(*) AS value FROM problem_synonym_groups"
        ).fetchone()["value"]

    assert classroom_http.factory.run_read(count) == 0


@pytest.mark.asyncio
async def test_problem_import_preview_rejects_unknown_course_and_invalid_xlsx(
    classroom_http,
):
    missing_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form("missing-course"),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert missing_response.status == 404

    invalid = FormData(default_to_multipart=True)
    invalid.add_field("courseId", "classroom-layout-course")
    invalid.add_field("workbook", b"not an xlsx", filename="tasks.xlsx")
    invalid_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=invalid,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert invalid_response.status == 422
    assert (await invalid_response.json())["error"][
        "code"
    ] == "problem_import_invalid_workbook"


@pytest.mark.asyncio
async def test_problem_import_apply_is_repeatable_and_rollback_restores_rows(
    classroom_http,
):
    lesson = 45
    source = _workbook(lesson=lesson)
    _seed_existing_problem(
        classroom_http.factory, title="Старое название", lesson=lesson
    )
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(lesson=lesson, source=source),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()
    assert preview["summary"] == {
        "rows": 3,
        "create": 1,
        "update": 1,
        "unchanged": 0,
        "invalid": 1,
    }

    async def apply():
        return await classroom_http.client.post(
            "/staff/api/v1/problem-imports/apply",
            data=_form(
                source_sha256=preview["source"]["sha256"],
                preview_sha256=preview["previewSha256"],
                lesson=lesson,
                source=source,
            ),
            headers=_headers(unsafe=True),
            cookies=_cookies(classroom_http, "admin"),
        )

    applied_response = await apply()
    assert applied_response.status == 200, await applied_response.text()
    applied = await applied_response.json()
    assert applied["state"] == "applied"
    assert applied["summary"] == {
        "rows": 3,
        "created": 1,
        "updated": 1,
        "unchanged": 0,
        "skippedInvalid": 1,
    }
    assert applied["replayed"] is False

    replay_response = await apply()
    assert replay_response.status == 200, await replay_response.text()
    assert (await replay_response.json())["replayed"] is True

    def current(connection):
        return connection.execute(
            "SELECT public_id, title FROM problems WHERE lesson = ? ORDER BY id",
            (lesson,),
        ).fetchall()

    assert [row["title"] for row in classroom_http.factory.run_read(current)] == [
        "Орехи",
        "Новая задача",
    ]

    rollback_response = await classroom_http.client.post(
        f"/staff/api/v1/problem-imports/{applied['importId']}/rollback",
        json={"expectedVersion": applied["version"]},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert rollback_response.status == 200, await rollback_response.text()
    rolled_back = await rollback_response.json()
    assert rolled_back["state"] == "rolled_back"
    assert rolled_back["version"] == 2
    assert rolled_back["replayed"] is False
    assert [row["title"] for row in classroom_http.factory.run_read(current)] == [
        "Старое название"
    ]

    replay_rollback = await classroom_http.client.post(
        f"/staff/api/v1/problem-imports/{applied['importId']}/rollback",
        json={"expectedVersion": applied["version"]},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert replay_rollback.status == 200
    assert (await replay_rollback.json())["replayed"] is True


@pytest.mark.asyncio
async def test_problem_import_apply_rejects_changed_preview_and_teacher(
    classroom_http,
):
    lesson = 46
    source = _workbook(lesson=lesson)
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(lesson=lesson, source=source),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()

    teacher = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/apply",
        data=_form(
            source_sha256=preview["source"]["sha256"],
            preview_sha256=preview["previewSha256"],
            lesson=lesson,
            source=source,
        ),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    _seed_existing_problem(classroom_http.factory, lesson=lesson)
    stale = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/apply",
        data=_form(
            source_sha256=preview["source"]["sha256"],
            preview_sha256=preview["previewSha256"],
            lesson=lesson,
            source=source,
        ),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "problem_preview_changed"


@pytest.mark.asyncio
async def test_problem_import_rollback_is_atomic_after_a_later_edit(classroom_http):
    lesson = 47
    source = _workbook(lesson=lesson)
    _seed_existing_problem(
        classroom_http.factory, title="Старое название", lesson=lesson
    )
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(lesson=lesson, source=source),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()
    applied_response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/apply",
        data=_form(
            source_sha256=preview["source"]["sha256"],
            preview_sha256=preview["previewSha256"],
            lesson=lesson,
            source=source,
        ),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert applied_response.status == 200, await applied_response.text()
    applied = await applied_response.json()

    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE problems SET title = 'Поздняя правка' WHERE public_id = ?",
            (f"problem-import-existing-{lesson}",),
        )
    )
    rollback = await classroom_http.client.post(
        f"/staff/api/v1/problem-imports/{applied['importId']}/rollback",
        json={"expectedVersion": applied["version"]},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert rollback.status == 409
    assert (await rollback.json())["error"]["code"] == "problem_import_result_changed"

    def rows(connection):
        return connection.execute(
            "SELECT title FROM problems WHERE lesson = ? ORDER BY id",
            (lesson,),
        ).fetchall(), connection.execute(
            "SELECT state FROM problem_import_receipts WHERE public_id = ?",
            (applied["importId"],),
        ).fetchone()

    problems, receipt = classroom_http.factory.run_read(rows)
    assert [row["title"] for row in problems] == ["Поздняя правка", "Новая задача"]
    assert receipt["state"] == "applied"

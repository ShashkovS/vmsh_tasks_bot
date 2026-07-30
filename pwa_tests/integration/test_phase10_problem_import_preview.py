"""Phase-10 dry-run for replacing the legacy problem workbook."""

from __future__ import annotations

from io import BytesIO

import pytest
from aiohttp import FormData
from openpyxl import Workbook

from models.pwa.problem_import import COLUMNS
from pwa_tests.integration.test_classroom_catalog_http_api import _cookies, _headers


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _workbook() -> bytes:
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
            41,
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
    current.append(
        (
            "н",
            41,
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
            41,
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


def _form(course_id: str = "classroom-layout-course") -> FormData:
    form = FormData(default_to_multipart=True)
    form.add_field("courseId", course_id)
    form.add_field(
        "workbook",
        _workbook(),
        filename="tasks.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    return form


def _seed_existing_problem(factory) -> None:
    def write(connection):
        connection.execute(
            "INSERT INTO problems "
            "(public_id, group_id, lesson, prob, item, title, prob_text, prob_type, "
            "ans_type, ans_validation, validation_error, cor_ans, cor_ans_checker, "
            "wrong_ans, congrat, synonyms) VALUES "
            "('problem-import-existing', 'layout-beginner', 41, 1, '', 'Орехи', "
            "'', 1, 2, NULL, 'Введите число', '29', NULL, 'Нет', 'Да', '')"
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
    _seed_existing_problem(classroom_http.factory)
    response = await classroom_http.client.post(
        "/staff/api/v1/problem-imports/preview",
        data=_form(),
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
    assert body["rows"][0]["problemId"] == "problem-import-existing"
    assert body["rows"][2]["diagnostics"][0]["code"] == "group_unknown"

    def count(connection):
        return connection.execute("SELECT count(*) AS value FROM problems").fetchone()[
            "value"
        ]

    assert classroom_http.factory.run_read(count) == 1


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

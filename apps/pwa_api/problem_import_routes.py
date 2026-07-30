"""Admin-only dry-run for the legacy «Задачи»/«Старые» workbook."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections import Counter

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.problem_imports import (
    find_course,
    list_course_groups,
    list_course_problems,
)
from helpers.pwa.app_keys import PWA_DATABASE
from models.pwa.auth import AuthAudience
from models.pwa.problem_import import compare_problem_rows, parse_problem_workbook


problem_import_routes = web.RouteTableDef()
_FIELDS = {"courseId", "workbook"}
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_REQUEST_LIMIT = 12 * 1024 * 1024
_WORKBOOK_LIMIT = 10 * 1024 * 1024
_MESSAGES = {
    "invalid_header": "В листе изменились названия или порядок столбцов.",
    "cell_too_long": "Ячейка слишком большая.",
    "group_required": "Не указана группа.",
    "group_unknown": "Такой группы нет в выбранном курсе.",
    "lesson_invalid": "Номер занятия должен быть целым неотрицательным числом.",
    "problem_number_invalid": "Номер задачи должен быть положительным целым числом.",
    "title_required": "У задачи нет названия.",
    "problem_type_invalid": "Неизвестный тип задачи.",
    "answer_type_invalid": "Для тестовой задачи нужен известный тип ответа.",
    "answer_validation_invalid": "Регулярное выражение валидации не компилируется.",
    "duplicate_problem": "Эта группа, занятие, задача и пункт встречаются несколько раз.",
}


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="problem_import_unavailable",
            message="Импорт задач временно недоступен",
        )
    return state.factory


def _require_admin(request: web.Request) -> None:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Импортировать задачи может только администратор",
        )


async def _part_bytes(part, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await part.read_chunk(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise PwaApiError(
                status=413,
                code="payload_too_large",
                message="Файл слишком большой",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _multipart(request: web.Request) -> tuple[str, str, bytes]:
    if request.content_length is not None and request.content_length > _REQUEST_LIMIT:
        raise PwaApiError(
            status=413, code="payload_too_large", message="Файл слишком большой"
        )
    if request.content_type != "multipart/form-data":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Загрузка должна использовать multipart/form-data",
        )
    try:
        reader = await request.multipart()
    except (AssertionError, ValueError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Не удалось разобрать форму загрузки",
        ) from error
    values: dict[str, bytes] = {}
    filename: str | None = None
    while part := await reader.next():
        if part.name not in _FIELDS or part.name in values:
            raise PwaApiError(
                status=422,
                code="validation_error",
                message="Форма содержит неизвестное или повторное поле",
            )
        if part.name == "workbook":
            filename = part.filename
            if not filename or not filename.casefold().endswith(".xlsx"):
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Выберите файл XLSX",
                )
            limit = _WORKBOOK_LIMIT
        else:
            if part.filename is not None:
                raise PwaApiError(
                    status=422,
                    code="validation_error",
                    message="Идентификатор курса должен быть текстом",
                )
            limit = 256
        values[part.name] = await _part_bytes(part, limit=limit)
    if set(values) != _FIELDS or filename is None or not values["workbook"]:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Выберите курс и XLSX-файл",
        )
    try:
        course_id = values["courseId"].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте выбранный курс"
        ) from error
    if _PUBLIC_ID.fullmatch(course_id) is None:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте выбранный курс"
        )
    return course_id, filename, values["workbook"]


def _diagnostics(items: object) -> list[dict[str, object]]:
    assert isinstance(items, list)
    return [
        {
            "sheet": item["sheet"],
            "row": item["row"],
            "field": item["field"],
            "code": item["code"],
            "message": _MESSAGES.get(str(item["code"]), "Проверьте значение ячейки."),
        }
        for item in items
    ]


def _row_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "sheet": row["sheet"],
        "row": row["row"],
        "groupCode": row["group_code"],
        "groupId": row["group_public_id"],
        "lessonNumber": row["lesson"],
        "problemNumber": row["problem"],
        "item": row["item"],
        "title": row["title"],
        "problemText": row["problem_text"],
        "problemType": row["problem_type"],
        "answerType": row["answer_type"],
        "answerValidation": row["answer_validation"],
        "validationError": row["validation_error"],
        "correctAnswer": row["correct_answer"],
        "correctAnswerChecker": row["correct_answer_checker"],
        "wrongAnswer": row["wrong_answer"],
        "congratulation": row["congratulation"],
        "action": row["action"],
        "problemId": row["problem_public_id"],
        "diagnostics": _diagnostics(row["diagnostics"]),
    }


@problem_import_routes.post("/staff/api/v1/problem-imports/preview")
async def preview_problem_import(request: web.Request) -> web.Response:
    _require_admin(request)
    if request.query:
        raise PwaApiError(
            status=422, code="validation_error", message="Этот запрос без параметров"
        )
    course_public_id, filename, source = await _multipart(request)

    def read(connection):
        course = find_course(connection, public_id=course_public_id)
        if course is None:
            return None
        course_id = int(course["id"])
        return (
            course,
            list_course_groups(connection, course_id=course_id),
            list_course_problems(connection, course_id=course_id),
        )

    database = await _factory(request).run_read_async(read)
    if database is None:
        raise PwaApiError(status=404, code="course_not_found", message="Курс не найден")
    course, groups, current = database
    try:
        parsed, _ = await asyncio.to_thread(parse_problem_workbook, source)
    except ValueError as error:
        code = str(error)
        messages = {
            "invalid_workbook": "Не удалось прочитать XLSX-файл",
            "missing_problem_sheets": "В файле нет листов «Задачи» или «Старые»",
            "too_many_rows": "В файле слишком много строк",
        }
        raise PwaApiError(
            status=422,
            code=f"problem_import_{code}",
            message=messages.get(code, "Не удалось проверить XLSX-файл"),
        ) from error
    compared = compare_problem_rows(parsed, groups, current)
    counts = Counter(str(row["action"]) for row in compared)
    return web.json_response(
        {
            "schemaVersion": 1,
            "course": {
                "courseId": course["public_id"],
                "code": course["code"],
                "name": course["name"],
            },
            "source": {
                "filename": filename,
                "sha256": hashlib.sha256(source).hexdigest(),
            },
            "summary": {
                "rows": len(compared),
                "create": counts["create"],
                "update": counts["update"],
                "unchanged": counts["unchanged"],
                "invalid": counts["invalid"],
            },
            "rows": [_row_payload(row) for row in compared],
            "requestId": request["request_id"],
        },
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["problem_import_routes"]

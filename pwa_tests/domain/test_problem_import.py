from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from models.pwa.problem_import import (
    COLUMNS,
    compare_problem_rows,
    parse_problem_workbook,
    problem_import_preview_hash,
)


def _workbook(*, current_rows=(), old_rows=()) -> bytes:
    workbook = Workbook()
    current = workbook.active
    current.title = "Задачи"
    old = workbook.create_sheet("Старые")
    for sheet, rows in ((current, current_rows), (old, old_rows)):
        sheet.append(COLUMNS)
        sheet.append(["Описание"] * len(COLUMNS))
        for row in rows:
            sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _row(
    *,
    group="н",
    lesson=41,
    problem=1,
    item="",
    title="Орехи",
    kind="Тест",
    answer="Натуральное",
):
    return (
        group,
        lesson,
        problem,
        item,
        title,
        None,
        kind,
        answer,
        None,
        "Введите число",
        29,
        None,
        "Нет",
        "Да",
    )


def test_parser_preserves_legacy_fields_and_ignores_answer_type_for_written():
    rows, diagnostics = parse_problem_workbook(
        _workbook(
            current_rows=(
                _row(),
                _row(
                    problem=2, title="Доказательство", kind="Письменно", answer="Целое"
                ),
            )
        )
    )

    assert diagnostics == []
    assert rows[0]["correct_answer"] == "29"
    assert rows[0]["problem_type"] == 1
    assert rows[0]["answer_type"] == 2
    assert rows[1]["problem_type"] == 2
    assert rows[1]["answer_type"] is None


def test_parser_reports_duplicate_identity_and_invalid_custom_regex():
    invalid = list(_row())
    invalid[8] = "["
    rows, diagnostics = parse_problem_workbook(
        _workbook(current_rows=(invalid,), old_rows=(_row(),))
    )

    assert len(rows) == 2
    assert {item["code"] for item in diagnostics} == {
        "answer_validation_invalid",
        "duplicate_problem",
    }
    assert all(row["diagnostics"] for row in rows)


def test_comparison_marks_create_update_unchanged_and_unknown_group():
    rows, _ = parse_problem_workbook(
        _workbook(
            current_rows=(
                _row(problem=1),
                _row(problem=2, title="Новое название"),
                _row(group="чужая", problem=3),
            )
        )
    )
    groups = [
        {"group_id": "beginner", "public_id": "group-beginner", "short_code": "н"}
    ]
    current = [
        {
            "group_id": "beginner",
            "lesson": 41,
            "prob": 1,
            "item": "",
            "public_id": "problem-one",
            "title": "Орехи",
            "prob_text": "",
            "prob_type": 1,
            "ans_type": 2,
            "ans_validation": "",
            "validation_error": "Введите число",
            "cor_ans": "29",
            "cor_ans_checker": "",
            "wrong_ans": "Нет",
            "congrat": "Да",
        },
        {
            "group_id": "beginner",
            "lesson": 41,
            "prob": 2,
            "item": "",
            "public_id": "problem-two",
            "title": "Старое название",
            "prob_text": "",
            "prob_type": 1,
            "ans_type": 2,
            "ans_validation": None,
            "validation_error": "Введите число",
            "cor_ans": "29",
            "cor_ans_checker": None,
            "wrong_ans": "Нет",
            "congrat": "Да",
        },
    ]

    compared = compare_problem_rows(rows, groups, current)
    assert [row["action"] for row in compared] == ["unchanged", "update", "invalid"]
    assert compared[0]["problem_public_id"] == "problem-one"
    assert compared[2]["diagnostics"][-1]["code"] == "group_unknown"

    first = problem_import_preview_hash("course-math", "a" * 64, compared)
    assert first == problem_import_preview_hash("course-math", "a" * 64, compared)
    assert first != problem_import_preview_hash("course-math", "b" * 64, compared)


def test_reference_workbook_remains_a_clean_characterization_input():
    source = Path(
        "_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx"
    )
    rows, diagnostics = parse_problem_workbook(source.read_bytes())

    assert diagnostics == []
    assert sum(row["sheet"] == "Задачи" for row in rows) == 816
    assert sum(row["sheet"] == "Старые" for row in rows) == 997

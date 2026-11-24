"""Russian Staff clipboard protocol (vmshpwa/apps/staff/src/problem-metadata-columns.ts)."""

import csv
import io

COLUMNS = {
    "displayNumber": "Номер",
    "title": "Название",
    "problemType": "Тип задачи",
    "answerType": "Тип ответа",
    "correctAnswer": "Правильный ответ",
    "answerValidation": "Своя валидация",
    "validationError": "Ошибка формата",
    "correctAnswerChecker": "Проверяльщик",
    "wrongAnswer": "Неверный ответ",
    "congratulation": "Верный ответ",
}
TYPES = {
    "problemType": {1: "Тестовая", 2: "Письменная", 3: "Устная"},
    "answerType": {
        1: "Цифра",
        2: "Натуральное число",
        3: "Целое число",
        4: "Отношение",
        5: "Десятичная дробь",
        6: "Обыкновенная или десятичная дробь",
        7: "Последовательность целых",
        8: "Два целых",
        9: "Три целых",
        10: "Четыре целых",
        11: "Множество целых",
        12: "Многочлен",
        13: "Число с точностью",
        14: "Время",
        15: "Дата",
        16: "День недели",
        17: "Последовательность дробей",
        18: "Мультимножество",
        19: "Смешанная дробь",
        20: "Символьное выражение",
        21: "Эквивалентное выражение",
        98: "Выбор одного варианта",
        99: "Строка",
    },
}


def encode(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t")
    writer.writerow(COLUMNS.values())
    for row in rows:
        writer.writerow([TYPES.get(key, {}).get(row[key], row[key]) for key in COLUMNS])
    return output.getvalue().encode("utf-8")


def decode(data, rows):
    reader = csv.reader(
        io.StringIO(data.decode("utf-8-sig"), newline=""), delimiter="\t", strict=True
    )
    if next(reader, None) != list(COLUMNS.values()):
        raise ValueError("wrong_tsv_headers")
    index = {str(row["displayNumber"]): row for row in rows}
    if len(index) != len(rows):
        raise ValueError("ambiguous_display_numbers_use_row_ids")
    patches = {}
    errors = []
    for number, values in enumerate(reader, 2):
        if len(values) != len(COLUMNS) or values[0] not in index:
            errors.append({"row": number, "error": "invalid_columns_or_number"})
            continue
        row = index[values[0]]
        if row["problemId"] in patches:
            errors.append({"row": number, "error": "duplicate_row"})
            continue
        patch = {}
        for key, value in zip(COLUMNS, values):
            previous = row[key]
            if (
                str(
                    TYPES.get(key, {}).get(previous, previous)
                    if previous is not None
                    else ""
                )
                == value
            ):
                continue
            if key in TYPES:
                inverse = {label: code for code, label in TYPES[key].items()}
                if value in inverse:
                    value = inverse[value]
                elif key == "answerType" and not value:
                    value = None
                else:
                    errors.append(
                        {"row": number, "field": key, "error": "unknown_type"}
                    )
                    continue
            patch[key] = value
        patches[row["problemId"]] = patch
    if set(patches) != {r["problemId"] for r in rows}:
        errors.append({"error": "missing_rows"})
    return patches, errors

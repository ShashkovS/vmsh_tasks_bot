from __future__ import annotations

"""VMSh LaTeX -> structured JSON and independent checker generation.

Runtime dependencies::

    python >= 3.11
    pydantic >= 2.8, < 3
    openrouter >= 1.0, < 2

The two public API functions are asynchronous and never stream:

    await generate_lesson_json(...)
    await generate_python_checker(...)

The first function only marks rows that need a custom checker.  It never
creates checker source code.  The second function is intentionally independent:
it receives only one task's LaTeX and produces one trusted checker snippet.
"""

import ast
import asyncio
import hashlib
import json
import os
import re
import secrets
import symtable
from ast import literal_eval
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


DEFAULT_MODEL = "openai/gpt-5.6-luna"
LESSON_SCHEMA_NAME = "vmsh_lesson_markup"
CHECKER_SCHEMA_NAME = "vmsh_python_checker"
FACT_REVIEW_SCHEMA_NAME = "vmsh_lesson_fact_review"
PUNCTS = "абвгдежзиклмнопрстуфхцчшщъыьэюя"

ANSWER_TYPES = (
    "Цифра",
    "Натуральное",
    "Целое",
    "Отношение",
    "Действительное",
    "Дробь",
    "СмешДробь",
    "ПоследЦелых",
    "ДваЦелых",
    "ТриЦелых",
    "ЧетыреЦелых",
    "МножЦелых",
    "Выбор",
    "Строка",
    "Многочлен",
    "ЧислоТочность",
    "Время",
    "Дата",
    "ДеньНедели",
    "ПоследДробей",
    "МультиМнож",
    "Символьное",
    "Эквивалентно",
)

LessonGroup: TypeAlias = Literal["н", "п", "э"]
ProblemType: TypeAlias = Literal["Тест", "Письменно", "Письменно<-Устно"]
AnswerType: TypeAlias = Literal[
    "",
    "Цифра",
    "Натуральное",
    "Целое",
    "Отношение",
    "Действительное",
    "Дробь",
    "СмешДробь",
    "ПоследЦелых",
    "ДваЦелых",
    "ТриЦелых",
    "ЧетыреЦелых",
    "МножЦелых",
    "Выбор",
    "Строка",
    "Многочлен",
    "ЧислоТочность",
    "Время",
    "Дата",
    "ДеньНедели",
    "ПоследДробей",
    "МультиМнож",
    "Символьное",
    "Эквивалентно",
]
ValidationMode: TypeAlias = Literal["none", "builtin", "regex", "choices"]
AnswerSource: TypeAlias = Literal[
    "not_applicable",
    "embedded_metadata",
    "explicit_answer",
    "solution",
    "derived",
    "image_missing",
    "unresolved",
]
RowStatus: TypeAlias = Literal["ready", "needs_checker", "needs_image", "needs_review"]
ImageRequirement: TypeAlias = Literal["title", "answer", "answer_format"]
CheckerStatus: TypeAlias = Literal["ready", "needs_image", "needs_review"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnswerValidation(ContractModel):
    mode: ValidationMode = Field(
        description=(
            "Способ предварительной проверки допустимого формата ответа; "
            "это не проверка правильного ответа."
        )
    )
    regex: str = Field(description="Регулярное выражение без /.../; иначе пустая строка.")
    choices: list[str] = Field(
        description=(
            "Для типа Выбор — полный список всех вариантов, которые ученик может "
            "выбрать, включая неверные; никогда не только correct_answers. "
            "Для остальных типов пустой список."
        )
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> "AnswerValidation":
        if len(self.choices) != len(dict.fromkeys(self.choices)):
            raise ValueError("validation.choices contains duplicates")
        if self.mode == "regex" and not self.regex:
            raise ValueError("regex mode requires a non-empty regex")
        if self.mode != "regex" and self.regex:
            raise ValueError("regex must be empty unless mode=regex")
        if self.mode == "choices" and not self.choices:
            raise ValueError("choices mode requires choices")
        if self.mode != "choices" and self.choices:
            raise ValueError("choices must be empty unless mode=choices")
        return self


class ImageDependency(ContractModel):
    required_for: list[ImageRequirement] = Field(
        description="Какие поля невозможно определить без отсутствующего внешнего рисунка."
    )
    references: list[str] = Field(description="Имена отсутствующих внешних файлов рисунков.")

    @model_validator(mode="after")
    def validate_unique(self) -> "ImageDependency":
        if len(self.required_for) != len(dict.fromkeys(self.required_for)):
            raise ValueError("image_dependency.required_for contains duplicates")
        if len(self.references) != len(dict.fromkeys(self.references)):
            raise ValueError("image_dependency.references contains duplicates")
        return self


class LessonRow(ContractModel):
    row_id: str = Field(description="Идентификатор вида 34н.5 или 34н.5а.")
    prob: int = Field(description="Номер задачи в занятии.")
    item: str = Field(description="Буква подпункта или пустая строка.")
    source_title: str = Field(description="Название из btitle; иначе пустая строка.")
    title: str = Field(description="Короткое уникальное название, обычно 2–3 слова.")
    prob_text: str = Field(description="Явная замена текста задачи; обычно пустая строка.")
    prob_type: ProblemType = Field(description="Тип строки, установленный структурным парсером.")
    ans_type: AnswerType = Field(
        description=(
            "Штатный тип ответа; пусто у нетестовых строк. Используй Выбор для "
            "закрытого списка вариантов из условия, а не Строка с regex."
        )
    )
    validation: AnswerValidation
    input_prompt: str = Field(description="Однозначное приглашение к вводу и описание формата.")
    correct_answers: list[str] = Field(
        description=(
            "Только смыслово различные правильные ответы. Для Выбор это подмножество "
            "validation.choices, а не источник списка choices."
        )
    )
    needs_checker: bool = Field(description="Нужен ли отдельный нестандартный Python-чекер.")
    checker_reason: str = Field(description="Короткая причина необходимости чекера; иначе пусто.")
    wrong_ans: str = Field(description="Короткое сообщение о неверном ответе без подсказки.")
    congrat: str = Field(description="Короткое приятное контекстное поздравление.")
    answer_source: AnswerSource = Field(description="На каком фрагменте LaTeX основан ответ.")
    status: RowStatus
    image_dependency: ImageDependency
    notes: list[str] = Field(description="Короткие редакционные замечания; обычно пустой список.")

    @model_validator(mode="after")
    def validate_local_invariants(self) -> "LessonRow":
        if len(self.correct_answers) != len(dict.fromkeys(self.correct_answers)):
            raise ValueError("correct_answers contains duplicates")
        if len(self.notes) != len(dict.fromkeys(self.notes)):
            raise ValueError("notes contains duplicates")
        if any(";" in value for value in self.correct_answers):
            raise ValueError("one correct_answers element must not contain semicolon")
        if self.needs_checker and not self.checker_reason:
            raise ValueError("needs_checker=true requires checker_reason")
        if not self.needs_checker and self.checker_reason:
            raise ValueError("checker_reason must be empty when needs_checker=false")
        return self


class LessonMarkup(ContractModel):
    schema_version: Literal["vmsh-lesson-json-v3"]
    lesson_number: int
    lesson_group: LessonGroup
    rows: list[LessonRow]
    warnings: list[str]

    @model_validator(mode="after")
    def validate_unique_rows(self) -> "LessonMarkup":
        row_ids = [row.row_id for row in self.rows]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("duplicate row_id")
        if len(self.warnings) != len(dict.fromkeys(self.warnings)):
            raise ValueError("duplicate warnings")
        return self


FactVerdict: TypeAlias = Literal["confirmed", "corrected", "needs_review"]


class FactualRowReview(ContractModel):
    row_id: str = Field(description="Идентификатор проверяемой строки.")
    verdict: FactVerdict = Field(description="Результат независимой фактологической проверки.")
    ans_type: AnswerType
    validation: AnswerValidation
    correct_answers: list[str]
    needs_checker: bool
    checker_reason: str
    answer_source: AnswerSource
    status: RowStatus
    image_dependency: ImageDependency
    reason: str = Field(description="Краткое основание исправления или needs_review; иначе пустая строка.")

    @model_validator(mode="after")
    def validate_review_consistency(self) -> "FactualRowReview":
        if len(self.correct_answers) != len(dict.fromkeys(self.correct_answers)):
            raise ValueError("correct_answers contains duplicates")
        if any(";" in value for value in self.correct_answers):
            raise ValueError("one correct_answers element must not contain semicolon")
        if self.needs_checker and not self.checker_reason:
            raise ValueError("needs_checker=true requires checker_reason")
        if not self.needs_checker and self.checker_reason:
            raise ValueError("checker_reason must be empty when needs_checker=false")
        if self.verdict == "confirmed" and self.reason:
            raise ValueError("confirmed verdict requires an empty reason")
        if self.verdict != "confirmed" and not self.reason.strip():
            raise ValueError("corrected/needs_review verdict requires a reason")
        if self.verdict == "needs_review" and self.status != "needs_review":
            raise ValueError("needs_review verdict requires status=needs_review")
        return self


class LessonFactReview(ContractModel):
    schema_version: Literal["vmsh-lesson-fact-review-v1"]
    rows: list[FactualRowReview]
    warnings: list[str]

    @model_validator(mode="after")
    def validate_unique_rows(self) -> "LessonFactReview":
        row_ids = [row.row_id for row in self.rows]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("duplicate row_id in fact review")
        if len(self.warnings) != len(dict.fromkeys(self.warnings)):
            raise ValueError("duplicate fact-review warnings")
        return self


class CheckerTest(ContractModel):
    student_answer: str
    should_pass: bool
    purpose: str


class PythonChecker(ContractModel):
    schema_version: Literal["vmsh-python-checker-v3"]
    function_name: str
    python_code: str
    tests: list[CheckerTest]
    status: CheckerStatus
    placeholder: str
    notes: list[str]

    @model_validator(mode="after")
    def validate_unique_tests(self) -> "PythonChecker":
        keys = [(test.student_answer, test.should_pass) for test in self.tests]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate checker tests")
        if len(self.notes) != len(dict.fromkeys(self.notes)):
            raise ValueError("duplicate notes")
        return self


# ---------------------------------------------------------------------------
# Strict remote JSON schema built from Pydantic 2
# ---------------------------------------------------------------------------

SchemaModel = TypeVar("SchemaModel", bound=BaseModel)

_ALLOWED_REMOTE_SCHEMA_KEYS = {
    "type",
    "description",
    "enum",
    "properties",
    "required",
    "additionalProperties",
    "items",
}


def _resolve_json_pointer(root: Mapping[str, Any], pointer: str) -> Any:
    if not pointer.startswith("#/"):
        raise ValueError(f"unsupported external JSON-schema ref: {pointer}")
    value: Any = root
    for part in pointer[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[part]
    return value


def _inline_schema_refs(node: Any, root: Mapping[str, Any], stack: tuple[str, ...] = ()) -> Any:
    if isinstance(node, list):
        return [_inline_schema_refs(item, root, stack) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        pointer = str(node["$ref"])
        if pointer in stack:
            raise ValueError(f"recursive schema is not supported: {pointer}")
        resolved = _inline_schema_refs(_resolve_json_pointer(root, pointer), root, stack + (pointer,))
        extras = {key: value for key, value in node.items() if key != "$ref"}
        if extras:
            if not isinstance(resolved, dict):
                raise ValueError("cannot merge JSON-schema ref extras")
            resolved = {**resolved, **_inline_schema_refs(extras, root, stack)}
        return resolved
    return {key: _inline_schema_refs(value, root, stack) for key, value in node.items()}


def _sanitize_remote_schema(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize_remote_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    if "const" in node:
        out["enum"] = [node["const"]]

    for key, value in node.items():
        if key in {"$defs", "definitions", "$schema", "$id", "$ref", "const", "title"}:
            continue
        if key not in _ALLOWED_REMOTE_SCHEMA_KEYS:
            continue
        if key == "properties":
            if not isinstance(value, dict):
                raise ValueError("object properties must be a mapping")
            out[key] = {name: _sanitize_remote_schema(schema) for name, schema in value.items()}
        elif key == "required":
            # Rebuilt below from the sanitized property order.
            continue
        else:
            out[key] = _sanitize_remote_schema(value)

    if out.get("type") == "object" or "properties" in out:
        props = out.get("properties", {})
        if not isinstance(props, dict):
            raise ValueError("object properties must be a mapping")
        out["type"] = "object"
        out["properties"] = props
        out["required"] = list(props)
        out["additionalProperties"] = False

    return out


def openrouter_schema(model: type[SchemaModel]) -> dict[str, Any]:
    """Return a deliberately small OpenAI/OpenRouter strict-schema subset.

    Local Pydantic validation remains richer.  In particular, uniqueness,
    lengths, regexes and cross-field conditions are intentionally not emitted
    to the provider, avoiding unsupported keywords such as ``uniqueItems``.
    """

    raw = model.model_json_schema()
    inlined = _inline_schema_refs(raw, raw)
    sanitized = _sanitize_remote_schema(inlined)
    validate_openrouter_schema(sanitized)
    return sanitized


def validate_openrouter_schema(schema: Mapping[str, Any]) -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
            return
        if not isinstance(node, dict):
            return
        unknown = set(node) - _ALLOWED_REMOTE_SCHEMA_KEYS
        if unknown:
            raise ValueError(f"unsupported schema keys at {path}: {sorted(unknown)}")
        if node.get("type") == "object":
            props = node.get("properties")
            if not isinstance(props, dict):
                raise ValueError(f"object without properties at {path}")
            if node.get("additionalProperties") is not False:
                raise ValueError(f"additionalProperties must be false at {path}")
            if node.get("required") != list(props):
                raise ValueError(f"required must contain every property at {path}")
        for key, value in node.items():
            if key == "properties":
                for property_name, property_schema in value.items():
                    walk(property_schema, f"{path}.properties.{property_name}")
            elif key not in {"required", "enum"}:
                walk(value, f"{path}.{key}")

    walk(dict(schema), "$")


LESSON_REMOTE_SCHEMA = openrouter_schema(LessonMarkup)
FACT_REVIEW_REMOTE_SCHEMA = openrouter_schema(LessonFactReview)
CHECKER_REMOTE_SCHEMA = openrouter_schema(PythonChecker)


# ---------------------------------------------------------------------------
# TeX preprocessing and structural parsing
# ---------------------------------------------------------------------------


def decode_tex_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("cp1251", errors="replace")


def read_tex_file(path: str | Path) -> str:
    return decode_tex_bytes(Path(path).read_bytes())


def _comment_start(line: str) -> int | None:
    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        pos = index - 1
        while pos >= 0 and line[pos] == "\\":
            backslashes += 1
            pos -= 1
        if backslashes % 2 == 0:
            return index
    return None


def strip_tex_comments(source: str) -> str:
    result: list[str] = []
    for line in source.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        start = _comment_start(line)
        result.append(line if start is None else line[:start])
    return "\n".join(result)


def clean_latex_document(source: str) -> str:
    source = strip_tex_comments(source)
    begin = re.search(r"\\begin\s*\{document\}", source)
    if begin:
        source = source[begin.start() :]
    end = re.search(r"\\end\s*\{document\}", source)
    if end:
        source = source[: end.end()]
    source = "\n".join(line.rstrip() for line in source.splitlines())
    source = re.sub(r"\n[ \t]+\n", "\n\n", source)
    source = re.sub(r"\n{3,}", "\n\n", source)
    return source.strip() + "\n"


def _mask_span(text: str, start: int, end: int) -> str:
    return text[:start] + "".join("\n" if char == "\n" else " " for char in text[start:end]) + text[end:]


def _mask_structure_ignored(text: str) -> str:
    ranges: list[tuple[int, int]] = []
    for name in ("ответ", "решение", "указание"):
        pattern = re.compile(rf"\\{name}\b.*?\\к{name}\b", flags=re.DOTALL | re.IGNORECASE)
        ranges.extend((match.start(), match.end()) for match in pattern.finditer(text))
    for env in ("tikzpicture", "verbatim", "Verbatim", "lstlisting", "minted"):
        pattern = re.compile(
            rf"\\begin\s*\{{{re.escape(env)}\}}.*?\\end\s*\{{{re.escape(env)}\}}",
            flags=re.DOTALL,
        )
        ranges.extend((match.start(), match.end()) for match in pattern.finditer(text))
    for start, end in sorted(ranges, reverse=True):
        text = _mask_span(text, start, end)
    return text


def _map_section(raw: str) -> ProblemType | None:
    lowered = re.sub(r"[^а-яёa-z]", "", raw.lower())
    if "тест" in lowered:
        return "Тест"
    if "письм" in lowered:
        return "Письменно"
    if "устн" in lowered or "доп" in lowered:
        return "Письменно<-Устно"
    return None


def _strip_simple_tex(text: str) -> str:
    text = re.sub(r"\\(?:btitle|bptype|batype|baval|bvalerr|bans|bchecker|bwrong|bcongrat)\s*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\tags\s*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Zа-яА-ЯёЁ@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("$", " ").replace("{", " ").replace("}", " ")
    text = text.replace("---", "—").replace("--", "–")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_puncts(text: str) -> list[str]:
    matches = list(re.finditer(r"\\(?P<cmd>[а-яё]{0,2}пункт)\b", text, flags=re.IGNORECASE))
    matches = [match for match in matches if match.group("cmd").lower() != "кпункт"]
    if not matches:
        return [text.strip()]
    parts: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        parts.append(text[match.end() : end].strip())
    return parts


def _extract_named_block(text: str, name: str) -> str:
    match = re.search(rf"\\{name}\b(.*?)\\к{name}\b", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_bot_metadata(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("btitle", "bptype", "batype", "baval", "bvalerr", "bans", "bchecker", "bwrong", "bcongrat"):
        match = re.search(rf"\\{name}\s*\{{([^{{}}]*)\}}", text, flags=re.DOTALL)
        if match:
            result[name] = match.group(1).strip()
    return result


def _external_image_refs(text: str) -> list[str]:
    refs: list[str] = []
    patterns = (
        r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}",
        r"\\(?:right|left)picture\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{([^{}]+)\}",
    )
    for pattern in patterns:
        refs.extend(match.group(1).strip() for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(ref for ref in refs if ref))


@dataclass(slots=True)
class ParsedTask:
    prob: int
    prob_type: ProblemType
    statement: str
    answer: str
    solution: str
    hint: str
    statement_parts: list[str]
    answer_parts: list[str]
    metadata: dict[str, str]
    external_images: list[str]
    has_inline_tikz: bool


@dataclass(slots=True)
class ExpectedRow:
    row_id: str
    prob: int
    item: str
    prob_type: ProblemType
    task_index: int
    item_index: int


@dataclass(slots=True)
class ParsedLesson:
    lesson_number: int
    lesson_group: LessonGroup
    tasks: list[ParsedTask]
    rows: list[ExpectedRow]
    trace: str
    warnings: list[str] = field(default_factory=list)

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "lesson_number": self.lesson_number,
            "lesson_group": self.lesson_group,
            "expected_rows": [
                {
                    "row_id": row.row_id,
                    "prob": row.prob,
                    "item": row.item,
                    "prob_type": row.prob_type,
                }
                for row in self.rows
            ],
            "parser_trace": self.trace,
            "parser_warnings": self.warnings,
            "tasks": [
                {
                    "prob": task.prob,
                    "prob_type": task.prob_type,
                    "statement_parts": task.statement_parts,
                    "answer_parts": task.answer_parts,
                    "explicit_answer_latex": task.answer,
                    "solution_latex": task.solution,
                    "hint_latex": task.hint,
                    "embedded_bot_metadata": task.metadata,
                    "external_image_references": task.external_images,
                    "inline_tikz_available": task.has_inline_tikz,
                }
                for task in self.tasks
            ],
        }


_STRUCTURE_TOKEN = re.compile(
    r"\\раздел\s*\{(?P<section>[^{}]*)\}|\\(?P<cmd>[а-яё]{0,2}задача)\b",
    flags=re.IGNORECASE,
)


def parse_lesson_structure(cleaned_latex: str, lesson_number: int, lesson_group: LessonGroup) -> ParsedLesson:
    masked = _mask_structure_ignored(cleaned_latex)
    current_type: ProblemType | None = None
    current_start: re.Match[str] | None = None
    current_prob_type: ProblemType | None = None
    task_spans: list[tuple[int, int, int, ProblemType]] = []
    task_num = 0
    trace: list[str] = []
    warnings: list[str] = []

    for match in _STRUCTURE_TOKEN.finditer(masked):
        section = match.group("section")
        if section is not None:
            mapped = _map_section(section)
            if mapped is None:
                warnings.append(f"Неизвестный раздел: {section.strip()}")
                trace.append("?")
            else:
                current_type = mapped
                trace.append({"Тест": "T", "Письменно": "W", "Письменно<-Устно": "O"}[mapped])
            continue

        command = (match.group("cmd") or "").lower()
        if command == "кзадача":
            trace.append("к")
            if current_start is None:
                warnings.append("Найдено \\кзадача без открытой задачи")
                continue
            task_spans.append((current_start.start(), match.end(), task_num, current_prob_type or "Письменно"))
            current_start = None
            current_prob_type = None
            continue

        trace.append("з")
        if current_start is not None:
            warnings.append(f"Задача {task_num} не закрыта перед следующей")
        task_num += 1
        current_start = match
        current_prob_type = current_type or "Письменно"
        if current_type is None:
            warnings.append(f"Для задачи {task_num} не найден раздел; использовано Письменно")

    if current_start is not None:
        warnings.append(f"Задача {task_num} не закрыта \\кзадача")

    tasks: list[ParsedTask] = []
    rows: list[ExpectedRow] = []
    for index, (start, close_end, prob, prob_type) in enumerate(task_spans):
        start_match = _STRUCTURE_TOKEN.search(masked, start)
        if start_match is None:
            raise RuntimeError("internal parser error")
        close_match = re.search(r"\\кзадача\b", masked[start_match.end() : close_end], flags=re.IGNORECASE)
        if close_match is None:
            raise RuntimeError("internal parser error: missing close")
        close_start = start_match.end() + close_match.start()
        statement = cleaned_latex[start_match.end() : close_start].strip()

        next_start = task_spans[index + 1][0] if index + 1 < len(task_spans) else len(cleaned_latex)
        section_after = re.search(r"\\раздел\s*\{", masked[close_end:next_start], flags=re.IGNORECASE)
        tail_end = close_end + section_after.start() if section_after else next_start
        tail = cleaned_latex[close_end:tail_end]

        answer = _extract_named_block(tail, "ответ")
        solution = _extract_named_block(tail, "решение")
        hint = _extract_named_block(tail, "указание")
        statement_parts = _split_puncts(statement)
        answer_parts = _split_puncts(answer) if answer else []
        if len(statement_parts) > len(PUNCTS):
            raise ValueError(f"too many subitems in task {prob}")

        previous_boundary = task_spans[index - 1][1] if index > 0 else 0
        visual_context = cleaned_latex[max(previous_boundary, start - 2500) : close_end]
        metadata = _extract_bot_metadata(statement)
        task = ParsedTask(
            prob=prob,
            prob_type=prob_type,
            statement=statement,
            answer=answer,
            solution=solution,
            hint=hint,
            statement_parts=statement_parts,
            answer_parts=answer_parts,
            metadata=metadata,
            external_images=_external_image_refs(visual_context),
            has_inline_tikz="\\begin{tikzpicture}" in visual_context,
        )
        task_index = len(tasks)
        tasks.append(task)

        if len(statement_parts) > 1:
            trace.extend("п" for _ in statement_parts)
            for item_index, _ in enumerate(statement_parts):
                item = PUNCTS[item_index]
                rows.append(
                    ExpectedRow(
                        row_id=f"{lesson_number}{lesson_group}.{prob}{item}",
                        prob=prob,
                        item=item,
                        prob_type=prob_type,
                        task_index=task_index,
                        item_index=item_index,
                    )
                )
        else:
            rows.append(
                ExpectedRow(
                    row_id=f"{lesson_number}{lesson_group}.{prob}",
                    prob=prob,
                    item="",
                    prob_type=prob_type,
                    task_index=task_index,
                    item_index=0,
                )
            )

    if not rows:
        raise ValueError("LaTeX parser found no active tasks")
    return ParsedLesson(lesson_number, lesson_group, tasks, rows, "".join(trace), warnings)


def infer_lesson_identity(source: str, path: str | Path | None = None) -> tuple[int, LessonGroup]:
    match = re.search(r"\\НомерЛистка\s*\{\s*(\d+)\s*([нпэ])\s*\}", source, flags=re.IGNORECASE)
    if match:
        return int(match.group(1)), match.group(2).lower()  # type: ignore[return-value]
    if path is not None:
        match = re.search(r"(?:usl[-_])?(\d+)[-_]?([npexнпэх])", Path(path).stem, flags=re.IGNORECASE)
        if match:
            group_map = {
                "n": "н",
                "p": "п",
                "e": "э",
                "x": "э",
                "н": "н",
                "п": "п",
                "э": "э",
                "х": "э",
            }
            return int(match.group(1)), group_map[match.group(2).lower()]  # type: ignore[return-value]
    raise ValueError("cannot infer lesson number/group; pass them explicitly")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_LESSON_EXAMPLES = r"""
ПРИМЕР 1 — тестовая задача без подпунктов.
LaTeX:
\задача
Сколько всего человек в ряду, если Петя седьмой слева и одиннадцатый справа?
\кзадача
\ответ 17 человек. \кответ

Строка JSON:
{
  "row_id": "12н.3",
  "prob": 3,
  "item": "",
  "source_title": "",
  "title": "Люди в ряду",
  "prob_text": "",
  "prob_type": "Тест",
  "ans_type": "Натуральное",
  "validation": {"mode": "builtin", "regex": "", "choices": []},
  "input_prompt": "Введите общее число людей в ряду.",
  "correct_answers": ["17"],
  "needs_checker": false,
  "checker_reason": "",
  "wrong_ans": "Нет, в ряду другое число людей",
  "congrat": "Да, все в ряду посчитаны!",
  "answer_source": "explicit_answer",
  "status": "ready",
  "image_dependency": {"required_for": [], "references": []},
  "notes": []
}

ПРИМЕР 2 — одна тестовая задача с двумя подпунктами. Родительской строки 12н.4 нет.
LaTeX:
\задача
На карточках записаны числа от 1 до 20.
\пункт Введите наименьшее и наибольшее чётные числа.
\пункт Выпишите все числа, делящиеся на 3, в возрастающем порядке.
\кзадача
\ответ
\пункт 2, 20.
\пункт 3, 6, 9, 12, 15, 18.
\кответ

Две строки JSON:
{
  "row_id": "12н.4а",
  "prob": 4,
  "item": "а",
  "source_title": "",
  "title": "Карточки — границы",
  "prob_text": "",
  "prob_type": "Тест",
  "ans_type": "ДваЦелых",
  "validation": {"mode": "builtin", "regex": "", "choices": []},
  "input_prompt": "Введите сначала наименьшее, затем наибольшее число, через запятую. Например: 4, 16",
  "correct_answers": ["2, 20"],
  "needs_checker": false,
  "checker_reason": "",
  "wrong_ans": "Нет, одна из границ выбрана неверно",
  "congrat": "Обе границы найдены!",
  "answer_source": "explicit_answer",
  "status": "ready",
  "image_dependency": {"required_for": [], "references": []},
  "notes": []
}
{
  "row_id": "12н.4б",
  "prob": 4,
  "item": "б",
  "source_title": "",
  "title": "Карточки — кратные",
  "prob_text": "",
  "prob_type": "Тест",
  "ans_type": "ПоследЦелых",
  "validation": {"mode": "builtin", "regex": "", "choices": []},
  "input_prompt": "Введите все подходящие числа в возрастающем порядке через запятую. Например: 3, 8, 14",
  "correct_answers": ["3, 6, 9, 12, 15, 18"],
  "needs_checker": false,
  "checker_reason": "",
  "wrong_ans": "Нет, последовательность пока не подходит",
  "congrat": "Все кратные найдены!",
  "answer_source": "explicit_answer",
  "status": "ready",
  "image_dependency": {"required_for": [], "references": []},
  "notes": []
}

ПРИМЕР 3 — письменная задача.
LaTeX:
\задача
Разрежьте клетчатую фигуру на две одинаковые части.
\кзадача

Строка JSON:
{
  "row_id": "12н.5",
  "prob": 5,
  "item": "",
  "source_title": "",
  "title": "Разрезание фигуры",
  "prob_text": "",
  "prob_type": "Письменно",
  "ans_type": "",
  "validation": {"mode": "none", "regex": "", "choices": []},
  "input_prompt": "",
  "correct_answers": [],
  "needs_checker": false,
  "checker_reason": "",
  "wrong_ans": "",
  "congrat": "",
  "answer_source": "not_applicable",
  "status": "ready",
  "image_dependency": {"required_for": [], "references": []},
  "notes": []
}
"""

LESSON_SYSTEM_PROMPT = rf"""
Ты размечаешь русские математические листки ВМШ для учебного бота. Верни только объект,
строго соответствующий переданной JSON Schema. Никакого Markdown и пояснений вне JSON.

СТРУКТУРА
1. Машинный структурный парсер является источником истины для row_id, prob, item,
   количества и порядка строк, а также prob_type. Не создавай и не удаляй строки.
2. Если у задачи есть подпункты в условии, создай строки только для подпунктов; родительской
   строки нет. Подпункты в ответе, решении и указании не создают структуру.
3. prob_text почти всегда "". Не копируй туда исходное условие.

ИСТОЧНИКИ ФАКТОВ — по убыванию приоритета
1. Встроенные bot-метаданные btitle/bptype/batype/baval/bvalerr/bans/bchecker/bwrong/bcongrat.
2. Явный блок \ответ ... \кответ.
3. Блок \решение ... \крешение и \указание ... \куказание.
4. Самостоятельное решение задачи.
Проверяй ответ независимо. При настоящем конфликте, который нельзя разрешить из LaTeX,
ставь status="needs_review" и кратко объясняй в notes. Не выдумывай факты.

НАЗВАНИЯ
- Уникальны внутри занятия и не совпадают с переданными existing_titles.
- Обычно 2–3 смысловых слова, максимум 40 знаков.
- Не используй «Задача 5», «Пункт а» и номер занятия.
- У подпунктов общий узнаваемый корень и различающие окончания.
- btitle, если есть, сохраняй точно.

ТИПЫ ОТВЕТА И ШТАТНЫЕ ЧЕКЕРЫ
Разрешены: {", ".join(ANSWER_TYPES)}.
- ДваЦелых/ТриЦелых/ЧетыреЦелых и ПоследЦелых сравнивают последовательность: порядок важен.
- МножЦелых сравнивает множество: порядок и повторы не важны.
- МультиМнож сравнивает мультимножество: порядок не важен, повторы важны.
- ПоследДробей сравнивает последовательность дробей.
- Выбор: validation.mode="choices", choices содержит все варианты, correct_answers — правильные.
  choices — это полный допустимый домен ответа ученика, поэтому обязательно включи и неверные
  варианты из условия. Никогда не строй choices только из correct_answers и не раскрывай
  правильный вариант в input_prompt. Например, для «У кого сумма больше: у Пети или у Васи?»
  используй Выбор с choices=["Петя", "Вася"] (или теми же формами из условия), а в
  correct_answers оставь только верный вариант. input_prompt должен перечислять все варианты;
  локальная нормализация добавит их, если модель пропустит.
- Строка всегда требует validation.mode="regex" и осмысленную регулярку. Для одного точного
  слова используй регистронезависимую регулярку, например (?i:бам). Выбор используй только
  когда ученику действительно предъявляется закрытый список вариантов; не превращай такой
  список в Строку и regex по одному правильному ответу.
- Символьное требует строгого равенства выражений; Эквивалентно допускает алгебраически
  эквивалентную запись.
- Для остальных штатных типов validation.mode="builtin".

ПРИГЛАШЕНИЕ К ВВОДУ
Однозначно укажи, что вводить и в каком порядке. Для любого нетривиального формата дай
пример, который показывает только формат и не является правильным ответом к текущей задаче.
Не добавляй единицы измерения в correct_answers, если чекер ожидает число.

ПРАВИЛЬНЫЕ ОТВЕТЫ
- Каждый смысловой вариант — отдельный элемент correct_answers; внутри элемента нет «;».
- Если вариантов не более 24, перечисли все. Не дублируй различия только в пробелах,
  разделителях, регистре или эквивалентной записи дроби.
- Явный bans является уже существующим контрактом: удали только форматные дубли. Число
  исходных записей может быть больше 24, если после нормализации смысловых вариантов не более 24.
  Если смысловых вариантов осталось больше 24, используй needs_checker=true.
- Не добавляй обратный порядок двух чисел, если приглашение фиксирует, какое число первое.
- Если вариантов много или корректность конструктивного ответа задаётся условиями,
  correct_answers=[], needs_checker=true, status="needs_checker" и короткий checker_reason.
- Никогда не пиши код чекера в этом проходе.

КАРТИНКИ
Ты получаешь только LaTeX. Inline TikZ является доступной частью LaTeX. Внешний файл рисунка
недоступен. Если без него действительно нельзя определить поле и нет b-метаданных, ответа или
решения, используй дословные заглушки:
- [НУЖНА КАРТИНКА ДЛЯ НАЗВАНИЯ: ROW_ID]
- [НУЖНА КАРТИНКА ДЛЯ ОТВЕТА: ROW_ID]
- [НУЖНА КАРТИНКА ДЛЯ ФОРМАТА ОТВЕТА: ROW_ID]
Укажи соответствующие required_for/references и status="needs_image". Не ставь заглушку,
если рисунок нужен ученику, но название и ответ достоверно следуют из текста/ответа/решения.

СООБЩЕНИЯ
wrong_ans — короткое, понятное, не подсказывает решение. congrat — короткое, приятное и
по возможности связано с сюжетом. Для письменных и устных строк все ответные поля пусты.

{_LESSON_EXAMPLES}
""".strip()

FACT_REVIEW_SYSTEM_PROMPT = r"""
Ты независимо проверяешь только фактологические поля разметки математического листка ВМШ.
Верни только JSON по переданной схеме. Не переписывай названия, приглашения, сообщения об
ошибке и поздравления: их в этой схеме нет.

Для каждой строки из EXPECTED_ROWS верни ровно одну строку в том же порядке. Проверяй:
- ans_type и validation;
- полный набор correct_answers и их порядок, если порядок математически значим;
- необходимость нестандартного чекера;
- answer_source, status и зависимость от отсутствующей внешней картинки.

Приоритет источников:
1. embedded_bot_metadata;
2. explicit_answer_latex;
3. solution_latex и hint_latex;
4. самостоятельное решение.
Проверяй явный ответ по условию и решению, а не копируй его вслепую.
validation описывает весь допустимый формат ответа, а не только правильный ответ. Для ans_type
"Выбор" choices должен содержать все предложенные ученику варианты, включая неверные, а
correct_answers — только правильные из них. Если draft сузил choices до correct_answers или
заменил закрытый выбор Строкой/regex, исправь это.

verdict="confirmed": скопируй все фактологические поля DRAFT_FACTS дословно и reason="".
verdict="corrected": измени только доказуемо неверные фактологические поля и кратко объясни reason.
verdict="needs_review": используй только при настоящей неразрешимой неоднозначности; status должен
быть "needs_review", reason — конкретным. Не меняй корректные поля ради стилистического разнообразия.

Для письменных и устных строк: ans_type="", validation.mode="none", correct_answers=[],
needs_checker=false, answer_source="not_applicable", status="ready".
Никогда не генерируй Python-код чекера.
""".strip()


CHECKER_SYSTEM_PROMPT = r"""
Ты создаёшь один простой доверенный Python-чекер для одной математической задачи.
Верни только JSON по схеме. Никакого Markdown вне JSON.

Чекер полностью независим от разметки занятия и получает только LaTeX этой задачи.
Если без отсутствующего внешнего рисунка нельзя понять условие, верни status="needs_image",
python_code="", tests=[] и явную placeholder. Если само условие неоднозначно — needs_review.

Для status="ready":
- python_code содержит ровно один верхнеуровневый def с указанным точным function_name;
- функция принимает ровно один аргумент ans;
- возвращает только (bool, str) или (bool, None);
- код прямолинейный: разобрать ответ, проверить формат, проверить условия, вернуть первое
  понятное сообщение; без фреймворков, универсальных движков и архитектурных абстракций;
- 6–16 тестов, включая корректные ответы, неверный формат и содержательно неверные ответы.
- В самом начале отклоняй чрезмерно длинный ans (обычно len(ans) > 1000) до int, float,
  literal_eval и любых циклов: smoke-тест включает строку из 6001 цифры.

В окружении доступны ТОЛЬКО:
re, bool, float, int, list, range, set, str, tuple, abs, all, any, bin, enumerate, format,
len, max, min, round, sorted, sum, map, literal_eval. __builtins__ равен None.
Литералы списков/словарей/множеств и их обычные методы доступны.

Запрещены import, class, async, декораторы, аннотации, значения аргументов по умолчанию,
верхнеуровневые константы и тестовый код, print, input, assert, eval, exec, compile, open,
__import__, globals, locals, getattr, setattr, файловые/сетевые операции, рекурсия,
безусловный while True и обращения к именам с двойным подчёркиванием.
Не рассчитывай на dict(), zip(), pow(), ord(), chr(), isinstance(), Exception, ValueError,
Fraction, Counter, math или itertools: их нет в globals.

Стиль хорошего чекера:

def check_example(ans):
    nums = re.findall(r'-?\d+', ans)
    if len(nums) != 3:
        return False, 'Введите ровно три целых числа'
    nums = list(map(int, nums))
    if len(set(nums)) != 3:
        return False, 'Числа должны быть различными'
    if sum(nums) != 100:
        return False, 'Сумма должна быть равна 100'
    return True, 'Отлично!'
""".strip()


# ---------------------------------------------------------------------------
# Source-aware canonicalization and semantic validation
# ---------------------------------------------------------------------------


def _canonical_ints(value: str) -> str:
    return ", ".join(re.findall(r"[-+]?\d+", value))


def _canonical_answer(value: str, ans_type: str) -> str:
    value = value.strip()
    if ans_type in {"ПоследЦелых", "ДваЦелых", "ТриЦелых", "ЧетыреЦелых", "МножЦелых"}:
        return _canonical_ints(value)
    if ans_type in {"Цифра", "Натуральное", "Целое"}:
        match = re.search(r"[-+]?\d+", value)
        return match.group(0) if match else value
    return re.sub(r"\s+", " ", value).strip()


def _metadata_answers(raw: str, ans_type: str) -> list[str]:
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    if ans_type in {"ПоследЦелых", "ДваЦелых", "ТриЦелых", "ЧетыреЦелых", "МножЦелых"}:
        tokenized = [re.findall(r"[-+]?\d+", part) for part in parts]
        separated = [
            tokens
            for part, tokens in zip(parts, tokenized, strict=True)
            if len(tokens) > 1 and all(len(token.lstrip("+-")) == 1 for token in tokens)
        ]
        compact_length = 0
        if separated and len({len(tokens) for tokens in separated}) == 1:
            compact_length = len(separated[0])
        values: list[str] = []
        for part, tokens in zip(parts, tokenized, strict=True):
            compact = re.fullmatch(r"\d+", part)
            if compact_length and compact and len(part) == compact_length:
                tokens = list(part)
            if tokens:
                values.append(", ".join(tokens))
        return list(dict.fromkeys(values))
    values = [_canonical_answer(part, ans_type) for part in parts]
    return list(dict.fromkeys(value for value in values if value))


def _plain_answer_text(value: str) -> str:
    value = re.sub(r"^\s*(?:например|ответ)\s*[:,.-]?\s*", "", value, flags=re.IGNORECASE)
    value = _strip_simple_tex(value)
    value = value.strip(" .,:;!?")
    return value


def _task_part(task: ParsedTask, row: ExpectedRow) -> tuple[str, str]:
    statement = task.statement_parts[row.item_index] if row.item and row.item_index < len(task.statement_parts) else task.statement
    answer = task.answer
    if task.answer_parts:
        if row.item and row.item_index < len(task.answer_parts):
            answer = task.answer_parts[row.item_index]
        elif not row.item and len(task.answer_parts) == 1:
            answer = task.answer_parts[0]
    return statement, answer


def _answer_type_hint(task: ParsedTask, row: ExpectedRow) -> tuple[str, list[str]]:
    statement, answer = _task_part(task, row)
    statement_plain = _strip_simple_tex(statement)
    lowered = statement_plain.lower()
    if re.search(r"\bу\s+кого\b", lowered):
        preamble = task.statement.split(r"\пункт", maxsplit=1)[0]
        stop_words = {
            "Если",
            "Как",
            "Какая",
            "Какой",
            "Когда",
            "Кто",
            "На",
            "Несколько",
            "Сколько",
        }
        names = list(
            dict.fromkeys(
                name
                for name in re.findall(r"\b[А-ЯЁ][а-яё]{1,30}\b", _strip_simple_tex(preamble))
                if name not in stop_words
            )
        )
        if len(names) >= 2:
            return "Выбор", names
    count_words = {"два": "ДваЦелых", "две": "ДваЦелых", "три": "ТриЦелых", "четыре": "ЧетыреЦелых"}
    match = re.search(r"(?:введите|укажите|запишите)[^.!?]{0,80}\b(два|две|три|четыре)\b[^.!?]{0,40}\bчисл", lowered)
    if match:
        return count_words[match.group(1)], []

    plain_answer = _plain_answer_text(answer) if answer else ""
    list_match = re.search(
        r"\b([А-ЯЁа-яё][А-ЯЁа-яё-]{1,30})\s*,\s*([А-ЯЁа-яё][А-ЯЁа-яё-]{1,30})\s+и\s+([А-ЯЁа-яё][А-ЯЁа-яё-]{1,30})\b",
        statement_plain,
    )
    if list_match and plain_answer:
        choices = list(dict.fromkeys(list(list_match.groups())))
        if plain_answer in choices:
            return "Выбор", choices

    answer_numbers = re.findall(r"[-+]?\d+", answer) if answer else []
    if len(answer_numbers) == 1 and re.search(r"\bсколько\b", lowered):
        return ("Целое" if answer_numbers[0].startswith("-") else "Натуральное"), []
    return "", []


def _choice_answer_key(value: str) -> str:
    """Compare a named choice with a natural answer such as ``У Васи``."""

    normalized = _plain_answer_text(value).casefold().replace("ё", "е")
    normalized = re.sub(r"^(?:у|за|от|для)\s+", "", normalized)
    normalized = re.sub(r"[яи]$", "", normalized)
    return re.sub(r"[^a-zа-я0-9]+", "", normalized)


def _align_choice_answers_with_options(
    answers: Sequence[str], choices: Sequence[str]
) -> list[str]:
    """Keep stored correct answers in the exact form offered to a student."""

    by_key = {
        _choice_answer_key(choice): choice.strip()
        for choice in choices
        if choice.strip()
    }
    return list(
        dict.fromkeys(
            by_key.get(_choice_answer_key(answer), answer.strip())
            for answer in answers
            if answer.strip()
        )
    )


def _explicit_answer_for_row(task: ParsedTask, row: ExpectedRow, ans_type: str) -> list[str]:
    if not task.answer:
        return []
    part = task.answer
    if task.answer_parts:
        if row.item and row.item_index < len(task.answer_parts):
            part = task.answer_parts[row.item_index]
        elif not row.item and len(task.answer_parts) == 1:
            part = task.answer_parts[0]
    if ans_type in {"Цифра", "Натуральное", "Целое"}:
        match = re.search(r"[-+]?\d+", part)
        return [match.group(0)] if match else []
    expected_counts = {"ДваЦелых": 2, "ТриЦелых": 3, "ЧетыреЦелых": 4}
    if ans_type in expected_counts:
        nums = re.findall(r"[-+]?\d+", part)
        return [", ".join(nums)] if len(nums) == expected_counts[ans_type] else []
    if ans_type in {"ПоследЦелых", "МножЦелых"}:
        nums = re.findall(r"[-+]?\d+", part)
        return [", ".join(nums)] if nums else []
    if ans_type in {"Выбор", "Строка", "ДеньНедели"}:
        plain = _plain_answer_text(part)
        if plain and len(plain) <= 200:
            return [plain]
    if ans_type in {"Отношение", "Действительное", "Дробь", "СмешДробь", "ЧислоТочность"}:
        match = re.search(r"[-+]?(?:\d+(?:/\d+|[.,]\d+)?|[.,]\d+)", part)
        return [match.group(0).replace(",", ".")] if match else []
    if ans_type == "Время":
        match = re.search(r"\d{1,2}(?:\D{1,2}\d{1,2}){1,2}", part)
        return [match.group(0)] if match else []
    if ans_type == "Дата":
        match = re.search(r"\d{1,4}(?:\D{1,2}\d{1,4}){1,2}", part)
        return [match.group(0)] if match else []
    return []


def _append_note(row: LessonRow, note: str) -> LessonRow:
    data = row.model_dump()
    data["notes"] = list(dict.fromkeys([*row.notes, note]))
    return LessonRow.model_validate(data)


def _format_choices_for_prompt(choices: Sequence[str]) -> str:
    clean = [choice.strip() for choice in choices if choice.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} или {clean[1]}"
    return ", ".join(clean[:-1]) + f" или {clean[-1]}"


def _ensure_choice_prompt(prompt: str, choices: Sequence[str]) -> str:
    clean = list(dict.fromkeys(choice.strip() for choice in choices if choice.strip()))
    if not clean:
        return prompt.strip()
    folded_prompt = prompt.casefold()
    if all(choice.casefold() in folded_prompt for choice in clean):
        return prompt.strip()
    rendered = _format_choices_for_prompt(clean)
    base = prompt.strip()
    if not base:
        return f"Выберите один вариант: {rendered}."
    if base.endswith(":"):
        return f"{base} {rendered}"
    separator = "" if base.endswith((".", "!", "?")) else "."
    return f"{base}{separator} Варианты: {rendered}."


def canonicalize_with_source(markup: LessonMarkup, parsed: ParsedLesson) -> LessonMarkup:
    expected_by_id = {row.row_id: row for row in parsed.rows}
    returned_by_id = {row.row_id: row for row in markup.rows}
    if set(returned_by_id) != set(expected_by_id):
        return markup

    result: list[LessonRow] = []
    for expected in parsed.rows:
        row = returned_by_id[expected.row_id]
        task = parsed.tasks[expected.task_index]
        data = row.model_dump()
        data.update(
            row_id=expected.row_id,
            prob=expected.prob,
            item=expected.item,
            prob_type=expected.prob_type,
            source_title=task.metadata.get("btitle", ""),
            prob_text="",
        )
        image_dependency = dict(data.get("image_dependency") or {})
        image_dependency.setdefault("required_for", [])
        image_dependency.setdefault("references", [])
        data["image_dependency"] = image_dependency

        if expected.prob_type != "Тест":
            data.update(
                ans_type="",
                validation={"mode": "none", "regex": "", "choices": []},
                input_prompt="",
                correct_answers=[],
                needs_checker=False,
                checker_reason="",
                wrong_ans="",
                congrat="",
                answer_source="not_applicable",
            )
            if data["status"] in {"needs_checker", "needs_review"}:
                data["status"] = "ready"
            if data["status"] == "needs_image":
                data["image_dependency"]["references"] = list(task.external_images)
                if "title" in data["image_dependency"]["required_for"]:
                    data["title"] = (
                        f"[НУЖНА КАРТИНКА ДЛЯ НАЗВАНИЯ: {expected.row_id}]"
                    )
            else:
                data["image_dependency"]["required_for"] = []
                data["image_dependency"]["references"] = []
            result.append(LessonRow.model_validate(data))
            continue

        metadata = task.metadata
        if metadata.get("btitle"):
            data["source_title"] = metadata["btitle"]
            data["title"] = metadata["btitle"]
        if metadata.get("bptype"):
            mapped = _map_section(metadata["bptype"])
            if mapped:
                data["prob_type"] = mapped
        if metadata.get("batype") in ANSWER_TYPES:
            data["ans_type"] = metadata["batype"]
        elif (hint := _answer_type_hint(task, expected))[0]:
            data["ans_type"] = hint[0]
            if hint[0] == "Выбор":
                data["validation"] = {"mode": "choices", "regex": "", "choices": hint[1]}
        ans_type = str(data["ans_type"])

        if metadata.get("bans"):
            answers = _metadata_answers(metadata["bans"], ans_type)
            if len(answers) <= 24:
                data["correct_answers"] = answers
                data["needs_checker"] = False
                data["checker_reason"] = ""
                data["answer_source"] = "embedded_metadata"
                if data["status"] == "needs_checker":
                    data["status"] = "ready"
            else:
                data["correct_answers"] = []
                data["needs_checker"] = True
                data["checker_reason"] = "В LaTeX задано слишком много смысловых вариантов ответа."
                data["answer_source"] = "embedded_metadata"
                data["status"] = "needs_checker"
        if metadata.get("bchecker"):
            data["correct_answers"] = []
            data["needs_checker"] = True
            data["checker_reason"] = "В LaTeX задан нестандартный чекер."
            data["answer_source"] = "embedded_metadata"
            data["status"] = "needs_checker"
        if metadata.get("bwrong"):
            data["wrong_ans"] = metadata["bwrong"]
        if metadata.get("bcongrat"):
            data["congrat"] = metadata["bcongrat"]
        if metadata.get("bvalerr"):
            prescribed = metadata["bvalerr"].strip()
            generated = str(data.get("input_prompt") or "").strip()
            example = re.search(r"(?i)\bнапример\b.*$", generated)
            data["input_prompt"] = prescribed
            if "например" not in prescribed.casefold() and example:
                data["input_prompt"] += ". " + example.group(0).strip()

        if metadata.get("baval"):
            data["validation"] = {"mode": "regex", "regex": metadata["baval"], "choices": []}
        elif ans_type == "Выбор":
            validation = data.get("validation") or {}
            choices = validation.get("choices") or []
            data["validation"] = {"mode": "choices", "regex": "", "choices": choices}
        elif ans_type not in {"", "Строка"}:
            data["validation"] = {"mode": "builtin", "regex": "", "choices": []}

        if not metadata.get("bans") and not metadata.get("bchecker"):
            explicit = _explicit_answer_for_row(task, expected, ans_type)
            if explicit:
                data["correct_answers"] = explicit
                data["needs_checker"] = False
                data["checker_reason"] = ""
                data["answer_source"] = "explicit_answer"
                if data["status"] == "needs_checker":
                    data["status"] = "ready"

        if ans_type == "Строка" and not metadata.get("baval"):
            answers = [answer.strip() for answer in data.get("correct_answers", []) if answer.strip()]
            validation = data.get("validation") or {}
            if answers:
                escaped = "|".join(re.escape(answer) for answer in answers)
                data["validation"] = {
                    "mode": "regex",
                    "regex": rf"(?i:(?:{escaped}))",
                    "choices": [],
                }
            elif validation.get("mode") != "regex" or not validation.get("regex"):
                data["validation"] = {"mode": "regex", "regex": r"(?s:.+)", "choices": []}

        if ans_type == "Выбор" and data.get("status") != "needs_image":
            validation = data.get("validation") or {}
            choices = list(validation.get("choices") or [])
            data["correct_answers"] = _align_choice_answers_with_options(
                list(data.get("correct_answers") or []), choices
            )
            data["input_prompt"] = _ensure_choice_prompt(
                str(data.get("input_prompt") or ""),
                choices,
            )

        required_for = list(data["image_dependency"].get("required_for") or [])
        if data["status"] == "needs_image":
            data["image_dependency"]["references"] = list(task.external_images)
            if "title" in required_for:
                data["title"] = f"[НУЖНА КАРТИНКА ДЛЯ НАЗВАНИЯ: {expected.row_id}]"
            if "answer_format" in required_for:
                data["input_prompt"] = (
                    f"[НУЖНА КАРТИНКА ДЛЯ ФОРМАТА ОТВЕТА: {expected.row_id}]"
                )
            if "answer" in required_for:
                data["correct_answers"] = [
                    f"[НУЖНА КАРТИНКА ДЛЯ ОТВЕТА: {expected.row_id}]"
                ]
                data["needs_checker"] = False
                data["checker_reason"] = ""
            data["answer_source"] = "image_missing"
        else:
            data["image_dependency"]["required_for"] = []
            data["image_dependency"]["references"] = []

        result.append(LessonRow.model_validate(data))

    warnings = list(dict.fromkeys([*markup.warnings, *parsed.warnings]))
    return LessonMarkup(
        schema_version="vmsh-lesson-json-v3",
        lesson_number=parsed.lesson_number,
        lesson_group=parsed.lesson_group,
        rows=result,
        warnings=warnings,
    )


def _count_ints(answer: str) -> int:
    return len(re.findall(r"[-+]?\d+", answer))


def audit_lesson_markup(
    markup: LessonMarkup,
    parsed: ParsedLesson,
    *,
    existing_titles: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected_ids = [row.row_id for row in parsed.rows]
    actual_ids = [row.row_id for row in markup.rows]
    if actual_ids != expected_ids:
        errors.append(f"row_id/order mismatch: expected {expected_ids}, got {actual_ids}")
    if markup.lesson_number != parsed.lesson_number or markup.lesson_group != parsed.lesson_group:
        errors.append("lesson_number/lesson_group mismatch")

    forbidden_titles = {title.casefold().strip() for title in existing_titles if title.strip()}
    seen_titles: set[str] = set()
    expected_map = {row.row_id: row for row in parsed.rows}
    for row in markup.rows:
        expected = expected_map.get(row.row_id)
        task = parsed.tasks[expected.task_index] if expected else None
        if expected:
            if (row.prob, row.item, row.prob_type) != (expected.prob, expected.item, expected.prob_type):
                errors.append(f"{row.row_id}: structural fields differ from parser")
        title_key = row.title.casefold().strip()
        if not row.title.strip():
            errors.append(f"{row.row_id}: empty title")
        if len(row.title) > 40 and not row.title.startswith("[НУЖНА КАРТИНКА"):
            errors.append(f"{row.row_id}: title longer than 40 characters")
        if title_key in seen_titles:
            errors.append(f"{row.row_id}: duplicate title {row.title!r}")
        if title_key in forbidden_titles:
            errors.append(f"{row.row_id}: title conflicts with existing_titles: {row.title!r}")
        seen_titles.add(title_key)

        if row.prob_type != "Тест":
            if row.ans_type or row.input_prompt or row.correct_answers or row.needs_checker:
                errors.append(f"{row.row_id}: non-test row contains answer configuration")
            if row.validation.mode != "none" or row.wrong_ans or row.congrat:
                errors.append(f"{row.row_id}: non-test row contains test messages")
            continue

        if row.status == "ready" and not row.needs_checker:
            if not row.ans_type:
                errors.append(f"{row.row_id}: ready test row has no ans_type")
            if not row.input_prompt:
                errors.append(f"{row.row_id}: ready test row has no input_prompt")
            if not row.correct_answers:
                errors.append(f"{row.row_id}: ready test row has no correct_answers")
            if not row.wrong_ans or not row.congrat:
                errors.append(f"{row.row_id}: ready test row lacks messages")
        if row.needs_checker:
            if row.correct_answers:
                errors.append(f"{row.row_id}: checker row must not enumerate answers")
            if row.status != "needs_checker":
                errors.append(f"{row.row_id}: needs_checker=true but status={row.status}")
        if row.status == "needs_image":
            if not row.image_dependency.required_for:
                errors.append(f"{row.row_id}: needs_image without required_for")
            if not row.image_dependency.references:
                errors.append(f"{row.row_id}: needs_image without external references")
            if row.answer_source != "image_missing":
                errors.append(f"{row.row_id}: needs_image requires answer_source=image_missing")
            if "title" in row.image_dependency.required_for:
                placeholder = f"[НУЖНА КАРТИНКА ДЛЯ НАЗВАНИЯ: {row.row_id}]"
                if row.title != placeholder:
                    errors.append(f"{row.row_id}: wrong title image placeholder")
            if "answer_format" in row.image_dependency.required_for:
                placeholder = f"[НУЖНА КАРТИНКА ДЛЯ ФОРМАТА ОТВЕТА: {row.row_id}]"
                if row.input_prompt != placeholder:
                    errors.append(f"{row.row_id}: wrong answer-format image placeholder")
            if "answer" in row.image_dependency.required_for:
                placeholder = f"[НУЖНА КАРТИНКА ДЛЯ ОТВЕТА: {row.row_id}]"
                if row.correct_answers != [placeholder]:
                    errors.append(f"{row.row_id}: wrong answer image placeholder")
        elif row.image_dependency.required_for:
            errors.append(f"{row.row_id}: image required_for is non-empty outside needs_image")
        if row.ans_type == "Выбор":
            if row.validation.mode != "choices":
                errors.append(f"{row.row_id}: Выбор requires choices validation")
            missing = set(row.correct_answers) - set(row.validation.choices)
            if missing:
                errors.append(f"{row.row_id}: correct choices absent from choices: {sorted(missing)}")
        elif row.ans_type == "Строка":
            if row.validation.mode != "regex" or not row.validation.regex:
                errors.append(f"{row.row_id}: Строка requires non-empty regex validation")
        elif row.ans_type and row.validation.mode not in {"builtin", "regex"}:
            errors.append(f"{row.row_id}: unexpected validation mode {row.validation.mode}")

        cardinalities = {"ДваЦелых": 2, "ТриЦелых": 3, "ЧетыреЦелых": 4}
        if row.ans_type in cardinalities:
            for answer in row.correct_answers:
                if _count_ints(answer) != cardinalities[row.ans_type]:
                    errors.append(f"{row.row_id}: {row.ans_type} answer has wrong cardinality: {answer!r}")
        if len(row.correct_answers) > 24:
            errors.append(f"{row.row_id}: more than 24 enumerated answers")

        complex_types = {"ДваЦелых", "ТриЦелых", "ЧетыреЦелых", "ПоследЦелых", "МножЦелых", "ПоследДробей", "МультиМнож", "Время", "Дата"}
        if row.ans_type in complex_types and "например" not in row.input_prompt.lower():
            errors.append(f"{row.row_id}: nontrivial input_prompt has no example")
        if row.ans_type == "Выбор" and any(
            choice.casefold() not in row.input_prompt.casefold()
            for choice in row.validation.choices
        ):
            warnings.append(f"{row.row_id}: input_prompt does not name every choice")

    return errors, warnings




def _factual_fields(row: LessonRow) -> dict[str, Any]:
    return {
        "row_id": row.row_id,
        "ans_type": row.ans_type,
        "validation": row.validation.model_dump(mode="json"),
        "correct_answers": list(row.correct_answers),
        "needs_checker": row.needs_checker,
        "checker_reason": row.checker_reason,
        "answer_source": row.answer_source,
        "status": row.status,
        "image_dependency": row.image_dependency.model_dump(mode="json"),
    }


def _fact_review_user_prompt(parsed: ParsedLesson, draft: LessonMarkup) -> str:
    return (
        "Проверь фактологические поля DRAFT_FACTS по MACHINE_PARSE. "
        "EXPECTED_ROWS задаёт точный состав и порядок строк.\n\n"
        "EXPECTED_ROWS:\n"
        + json.dumps(
            [
                {
                    "row_id": row.row_id,
                    "prob": row.prob,
                    "item": row.item,
                    "prob_type": row.prob_type,
                }
                for row in parsed.rows
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n\nMACHINE_PARSE:\n"
        + json.dumps(parsed.prompt_payload(), ensure_ascii=False, indent=2)
        + "\n\nDRAFT_FACTS:\n"
        + json.dumps(
            [_factual_fields(row) for row in draft.rows],
            ensure_ascii=False,
            indent=2,
        )
    )


def _audit_fact_review(
    review: LessonFactReview,
    draft: LessonMarkup,
    parsed: ParsedLesson,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected_ids = [row.row_id for row in parsed.rows]
    actual_ids = [row.row_id for row in review.rows]
    if actual_ids != expected_ids:
        errors.append(f"fact-review row_id/order mismatch: expected {expected_ids}, got {actual_ids}")
        return errors, warnings

    draft_by_id = {row.row_id: row for row in draft.rows}
    expected_by_id = {row.row_id: row for row in parsed.rows}
    for reviewed in review.rows:
        draft_row = draft_by_id[reviewed.row_id]
        expected = expected_by_id[reviewed.row_id]
        reviewed_facts = {
            "row_id": reviewed.row_id,
            "ans_type": reviewed.ans_type,
            "validation": reviewed.validation.model_dump(mode="json"),
            "correct_answers": list(reviewed.correct_answers),
            "needs_checker": reviewed.needs_checker,
            "checker_reason": reviewed.checker_reason,
            "answer_source": reviewed.answer_source,
            "status": reviewed.status,
            "image_dependency": reviewed.image_dependency.model_dump(mode="json"),
        }
        if reviewed.verdict == "confirmed" and reviewed_facts != _factual_fields(draft_row):
            errors.append(
                f"{reviewed.row_id}: verdict=confirmed but factual fields differ from draft"
            )
        if reviewed.verdict == "corrected" and reviewed_facts == _factual_fields(draft_row):
            warnings.append(
                f"{reviewed.row_id}: verdict=corrected but no factual field changed"
            )
        if expected.prob_type != "Тест":
            if reviewed.ans_type or reviewed.correct_answers or reviewed.needs_checker:
                errors.append(f"{reviewed.row_id}: non-test fact review contains answer data")
            if reviewed.validation.mode != "none":
                errors.append(f"{reviewed.row_id}: non-test fact review must use validation.mode=none")
            if reviewed.answer_source != "not_applicable" or reviewed.status != "ready":
                errors.append(f"{reviewed.row_id}: non-test fact review has wrong source/status")
        if reviewed.needs_checker and reviewed.status != "needs_checker":
            errors.append(
                f"{reviewed.row_id}: needs_checker=true requires status=needs_checker"
            )
        if reviewed.ans_type == "Выбор":
            if reviewed.validation.mode != "choices":
                errors.append(f"{reviewed.row_id}: Выбор requires choices validation")
            missing = set(reviewed.correct_answers) - set(reviewed.validation.choices)
            if missing:
                errors.append(
                    f"{reviewed.row_id}: correct choices absent from choices: {sorted(missing)}"
                )
    return errors, warnings


def apply_fact_review(
    draft: LessonMarkup,
    review: LessonFactReview,
    parsed: ParsedLesson,
) -> LessonMarkup:
    errors, _ = _audit_fact_review(review, draft, parsed)
    if errors:
        raise ValueError("Invalid fact review:\n- " + "\n- ".join(errors))

    review_by_id = {row.row_id: row for row in review.rows}
    rows: list[LessonRow] = []
    for draft_row in draft.rows:
        checked = review_by_id[draft_row.row_id]
        data = draft_row.model_dump(mode="python")
        data.update(
            ans_type=checked.ans_type,
            validation=checked.validation.model_dump(mode="python"),
            correct_answers=list(checked.correct_answers),
            needs_checker=checked.needs_checker,
            checker_reason=checked.checker_reason,
            answer_source=checked.answer_source,
            status=checked.status,
            image_dependency=checked.image_dependency.model_dump(mode="python"),
        )
        if checked.verdict == "needs_review" and checked.reason.strip():
            data["notes"] = list(
                dict.fromkeys(
                    [*data.get("notes", []), f"Фактологическая проверка: {checked.reason.strip()}"]
                )
            )
        rows.append(LessonRow.model_validate(data))

    merged = LessonMarkup(
        schema_version="vmsh-lesson-json-v3",
        lesson_number=draft.lesson_number,
        lesson_group=draft.lesson_group,
        rows=rows,
        warnings=list(dict.fromkeys([*draft.warnings, *review.warnings])),
    )
    # Explicit source metadata and answers still outrank both model passes.
    return canonicalize_with_source(merged, parsed)


# ---------------------------------------------------------------------------
# OpenRouter async client
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "dict"):
        try:
            return _jsonable(value.dict())
        except Exception:
            pass
    result: dict[str, Any] = {}
    for name in ("id", "model", "provider", "usage", "choices", "error", "status_code", "body", "data"):
        if hasattr(value, name):
            result[name] = _jsonable(getattr(value, name))
    return result or repr(value)


def _message_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        raise ValueError("OpenRouter response has no choices")
    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None and isinstance(choice, Mapping):
        message = choice.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, Mapping) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
            elif hasattr(part, "text"):
                chunks.append(str(part.text))
        if chunks:
            return "".join(chunks)
    raise ValueError("OpenRouter response contains no textual content")


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("model output root must be a JSON object")
    return value


def _error_details(exc: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)}
    for name in ("status_code", "body", "data", "response", "raw_response"):
        if hasattr(exc, name):
            details[name] = _jsonable(getattr(exc, name))
    return details


def _apply_prompt_cache_breakpoint(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str,
    enabled: bool,
    ttl: Literal["5m", "1h"],
) -> list[dict[str, Any]]:
    """Return request messages with an explicit stable-prefix cache breakpoint when useful.

    OpenAI-compatible endpoints generally use automatic prompt caching, so for
    them a stable ``session_id`` is enough. Anthropic, Gemini and Alibaba/Qwen
    endpoints can benefit from an explicit breakpoint on the static system
    prompt. The dynamic TeX stays in the later user message.
    """

    result = [dict(message) for message in messages]
    if not enabled:
        return result

    model_base = model.split(":", 1)[0]
    explicit_prefixes = ("anthropic/", "google/", "qwen/", "alibaba/")
    if not model_base.startswith(explicit_prefixes):
        return result

    cache_control: dict[str, str] = {"type": "ephemeral"}
    if ttl == "1h":
        cache_control["ttl"] = "1h"

    for index, message in enumerate(result):
        if message.get("role") != "system" or not isinstance(message.get("content"), str):
            continue
        result[index] = {
            **message,
            "content": [
                {
                    "type": "text",
                    "text": message["content"],
                    "cache_control": cache_control,
                }
            ],
        }
        break
    return result


async def _openrouter_chat(
    *,
    api_key: str,
    proxy: str | None,
    model: str,
    messages: list[dict[str, Any]],
    response_schema: Mapping[str, Any],
    schema_name: str,
    reasoning_effort: str | None,
    max_output_tokens: int,
    session_id: str,
    timeout_seconds: float,
    prompt_cache: bool,
    prompt_cache_ttl: Literal["5m", "1h"],
    diagnostics: MutableMapping[str, Any] | None,
) -> dict[str, Any]:
    try:
        from openrouter import OpenRouter
    except ImportError as exc:
        raise RuntimeError(
            "The official OpenRouter SDK is not installed. Run: "
            "uv add 'openrouter>=1,<2' 'pydantic>=2.8,<3'"
        ) from exc

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout_ms": max(1, int(timeout_seconds * 1000)),
    }
    if referer := os.environ.get("OPENROUTER_HTTP_REFERER"):
        client_kwargs["http_referer"] = referer
    if title := os.environ.get("OPENROUTER_APP_TITLE"):
        client_kwargs["x_open_router_title"] = title

    request_messages = _apply_prompt_cache_breakpoint(
        messages,
        model=model,
        enabled=prompt_cache,
        ttl=prompt_cache_ttl,
    )
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": request_messages,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": dict(response_schema),
            },
        },
        "provider": {"require_parameters": True, "sort": "price"},
        "max_completion_tokens": max_output_tokens,
    }
    if reasoning_effort:
        request_kwargs["reasoning_effort"] = reasoning_effort
    if prompt_cache:
        request_kwargs["session_id"] = session_id

    if diagnostics is not None:
        diagnostics["request"] = {
            "model": model,
            "schema_name": schema_name,
            "stream": False,
            "reasoning_effort": reasoning_effort,
            "provider": request_kwargs["provider"],
            "max_completion_tokens": max_output_tokens,
            "session_id": request_kwargs.get("session_id"),
            "prompt_cache": prompt_cache,
            "prompt_cache_ttl": prompt_cache_ttl if prompt_cache else None,
            "explicit_cache_breakpoint": request_messages != messages,
            "schema_sha256": hashlib.sha256(
                json.dumps(response_schema, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "schema_bytes": len(json.dumps(response_schema, ensure_ascii=False).encode("utf-8")),
        }

    if proxy:
        # The official SDK leaves a caller-supplied client open.  Keep its
        # ownership here so this optional route remains OpenRouter-only.
        async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as async_client:
            async with OpenRouter(**client_kwargs, async_client=async_client) as client:
                async with asyncio.timeout(timeout_seconds):
                    response = await client.chat.send_async(**request_kwargs)
    else:
        async with OpenRouter(**client_kwargs) as client:
            async with asyncio.timeout(timeout_seconds):
                response = await client.chat.send_async(**request_kwargs)

    if diagnostics is not None:
        response_dump = _jsonable(response)
        diagnostics["response"] = {
            key: response_dump.get(key)
            for key in ("id", "model", "provider", "usage")
            if isinstance(response_dump, dict) and key in response_dump
        }
    parsed_output = _extract_json_object(_message_content(response))
    if diagnostics is not None:
        diagnostics["model_output"] = parsed_output
    return parsed_output


def _repair_message(previous: Mapping[str, Any] | None, errors: Sequence[str]) -> str:
    return (
        "Предыдущий JSON не прошёл локальную проверку. Верни весь исправленный объект заново.\n"
        "Ошибки:\n- "
        + "\n- ".join(errors)
        + "\nПредыдущий объект:\n"
        + json.dumps(previous or {}, ensure_ascii=False, indent=2)
    )


def _lesson_user_prompt(
    cleaned_latex: str,
    parsed: ParsedLesson,
    existing_titles: Sequence[str],
) -> str:
    return (
        "Разметь занятие. existing_titles и машинный разбор ниже являются частью задания.\n\n"
        "EXISTING_TITLES:\n"
        + json.dumps(list(existing_titles), ensure_ascii=False, indent=2)
        + "\n\nMACHINE_PARSE:\n"
        + json.dumps(parsed.prompt_payload(), ensure_ascii=False, indent=2)
        + "\n\nCLEANED_LATEX:\n"
        + cleaned_latex
    )


def build_lesson_request_preview(
    lesson_latex: str,
    lesson_number: int,
    lesson_group: LessonGroup,
    *,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str | None = "low",
    existing_titles: Sequence[str] = (),
    max_output_tokens: int = 32000,
    prompt_cache: bool = True,
    prompt_cache_ttl: Literal["5m", "1h"] = "1h",
) -> dict[str, Any]:
    """Build the first-pass request without the API key or HTTP-only fields."""

    cleaned = clean_latex_document(lesson_latex)
    parsed = parse_lesson_structure(cleaned, lesson_number, lesson_group)
    request: dict[str, Any] = {
        "model": model,
        "messages": _apply_prompt_cache_breakpoint(
            [
                {"role": "system", "content": LESSON_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _lesson_user_prompt(cleaned, parsed, existing_titles),
                },
            ],
            model=model,
            enabled=prompt_cache,
            ttl=prompt_cache_ttl,
        ),
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": LESSON_SCHEMA_NAME,
                "strict": True,
                "schema": LESSON_REMOTE_SCHEMA,
            },
        },
        "provider": {"require_parameters": True, "sort": "price"},
        "max_completion_tokens": max_output_tokens,
    }
    if reasoning_effort:
        request["reasoning_effort"] = reasoning_effort
    if prompt_cache:
        request["session_id"] = "vmsh-lesson-markup-v3"
    return request


async def generate_lesson_json(
    lesson_latex: str,
    lesson_number: int,
    lesson_group: LessonGroup,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    proxy: str | None = None,
    reasoning_effort: str | None = "low",
    existing_titles: Sequence[str] = (),
    max_attempts: int = 2,
    max_output_tokens: int = 32000,
    timeout_seconds: float = 600,
    prompt_cache: bool = True,
    prompt_cache_ttl: Literal["5m", "1h"] = "1h",
    verify: bool = True,
    verification_model: str | None = None,
    verification_attempts: int = 2,
    verification_strict: bool = False,
    diagnostics: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate validated JSON markup for one complete VMSh lesson.

    The function never generates Python checker code.  Rows requiring a custom
    checker are returned with ``needs_checker=true``.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if verify and verification_attempts < 1:
        raise ValueError("verification_attempts must be at least 1")
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    cleaned = clean_latex_document(lesson_latex)
    parsed = parse_lesson_structure(cleaned, lesson_number, lesson_group)
    user_prompt = _lesson_user_prompt(cleaned, parsed, existing_titles)

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics["preprocessing"] = {
            "source_chars": len(lesson_latex),
            "cleaned_chars": len(cleaned),
            "removed_chars": len(lesson_latex) - len(cleaned),
            "rows": len(parsed.rows),
            "tasks": len(parsed.tasks),
            "parser_trace": parsed.trace,
            "parser_warnings": parsed.warnings,
            "external_images": list(
                dict.fromkeys(ref for task in parsed.tasks for ref in task.external_images)
            ),
        }
        diagnostics["attempts"] = []

    previous: dict[str, Any] | None = None
    last_errors: list[str] = []
    accepted: LessonMarkup | None = None
    accepted_warnings: list[str] = []
    for attempt in range(1, max_attempts + 1):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": LESSON_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if previous is not None:
            messages.append({"role": "user", "content": _repair_message(previous, last_errors)})
        attempt_diag: dict[str, Any] = {"attempt": attempt, "phase": "generation"}
        if diagnostics is not None:
            diagnostics["attempts"].append(attempt_diag)
        try:
            raw = await _openrouter_chat(
                api_key=key,
                proxy=proxy,
                model=model,
                messages=messages,
                response_schema=LESSON_REMOTE_SCHEMA,
                schema_name=LESSON_SCHEMA_NAME,
                reasoning_effort=reasoning_effort,
                max_output_tokens=max_output_tokens,
                session_id="vmsh-lesson-markup-v3",
                timeout_seconds=timeout_seconds,
                prompt_cache=prompt_cache,
                prompt_cache_ttl=prompt_cache_ttl,
                diagnostics=attempt_diag,
            )
            previous = raw
            markup = LessonMarkup.model_validate(raw)
            markup = canonicalize_with_source(markup, parsed)
            errors, warnings = audit_lesson_markup(markup, parsed, existing_titles=existing_titles)
            attempt_diag["semantic_errors"] = errors
            attempt_diag["semantic_warnings"] = warnings
            if not errors:
                accepted = markup
                accepted_warnings = warnings
                break
            last_errors = errors
        except (ValidationError, ValueError) as exc:
            last_errors = [str(exc)]
            attempt_diag["validation_error"] = str(exc)
        except Exception as exc:
            attempt_diag["fatal_error"] = _error_details(exc)
            raise

    if accepted is None:
        raise ValueError("Model output failed validation after retries:\n- " + "\n- ".join(last_errors))

    if diagnostics is not None:
        diagnostics["accepted_generation"] = accepted.model_dump(mode="json")

    if verify:
        verification_prompt = _fact_review_user_prompt(parsed, accepted)
        previous_review: dict[str, Any] | None = None
        last_review_errors: list[str] = []
        review_applied = False
        for review_attempt in range(1, verification_attempts + 1):
            verify_diag: dict[str, Any] = {
                "attempt": review_attempt,
                "phase": "verification",
            }
            if diagnostics is not None:
                diagnostics["attempts"].append(verify_diag)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": FACT_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": verification_prompt},
            ]
            if previous_review is not None:
                messages.append(
                    {
                        "role": "user",
                        "content": _repair_message(previous_review, last_review_errors),
                    }
                )
            try:
                review_raw = await _openrouter_chat(
                    api_key=key,
                    proxy=proxy,
                    model=verification_model or model,
                    messages=messages,
                    response_schema=FACT_REVIEW_REMOTE_SCHEMA,
                    schema_name=FACT_REVIEW_SCHEMA_NAME,
                    reasoning_effort=reasoning_effort,
                    max_output_tokens=min(max_output_tokens, 10000),
                    session_id="vmsh-lesson-fact-review-v1",
                    timeout_seconds=timeout_seconds,
                    prompt_cache=prompt_cache,
                    prompt_cache_ttl=prompt_cache_ttl,
                    diagnostics=verify_diag,
                )
                previous_review = review_raw
                review = LessonFactReview.model_validate(review_raw)
                review_errors, review_warnings = _audit_fact_review(
                    review, accepted, parsed
                )
                verify_diag["review_errors"] = review_errors
                verify_diag["review_warnings"] = review_warnings
                if review_errors:
                    last_review_errors = review_errors
                    continue

                verified = apply_fact_review(accepted, review, parsed)
                verify_errors, verify_warnings = audit_lesson_markup(
                    verified,
                    parsed,
                    existing_titles=existing_titles,
                )
                verify_diag["semantic_errors"] = verify_errors
                verify_diag["semantic_warnings"] = verify_warnings
                if verify_errors:
                    last_review_errors = verify_errors
                    continue

                accepted = verified
                accepted_warnings = [
                    *accepted_warnings,
                    *review_warnings,
                    *verify_warnings,
                ]
                review_applied = True
                if diagnostics is not None:
                    diagnostics["verification_outcome"] = "applied"
                break
            except (ValidationError, ValueError) as exc:
                last_review_errors = [str(exc)]
                verify_diag["validation_error"] = str(exc)
            except Exception as exc:
                verify_diag["fatal_error"] = _error_details(exc)
                if verification_strict:
                    raise
                last_review_errors = [f"{type(exc).__name__}: {exc}"]
                break

        if not review_applied:
            message = (
                "Фактологическая проверка не применена после "
                f"{verification_attempts} попыток: "
                + "; ".join(last_review_errors or ["неизвестная ошибка"])
            )
            if diagnostics is not None:
                diagnostics["verification_outcome"] = "fallback_to_valid_generation"
                diagnostics["verification_errors"] = list(last_review_errors)
            if verification_strict:
                raise ValueError(message)
            accepted_warnings.append(message)

    result = accepted.model_dump(mode="json")
    if accepted_warnings:
        result["warnings"] = list(
            dict.fromkeys([*result["warnings"], *accepted_warnings])
        )
    return result


# ---------------------------------------------------------------------------
# Independent trusted checker generation and validation
# ---------------------------------------------------------------------------

TRUSTED_CHECKER_PATTERN = re.compile(r"^\s*def \w+\s*\(")
TRUSTED_CHECKER_GLOBALS: dict[str, object] = {
    "__builtins__": None,
    "re": re,
    "bool": bool,
    "float": float,
    "int": int,
    "list": list,
    "range": range,
    "set": set,
    "str": str,
    "tuple": tuple,
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "enumerate": enumerate,
    "format": format,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "sorted": sorted,
    "sum": sum,
    "map": map,
    "literal_eval": literal_eval,
}

_FORBIDDEN_CHECKER_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "input",
    "print",
}


def make_checker_function_name(task_latex: str) -> str:
    normalized = re.sub(r"\s+", " ", clean_latex_document(task_latex)).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"check_vmsh_{digest}_{secrets.token_hex(6)}"


def validate_checker_code(source: str, expected_name: str) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        errors.append("python_code must contain exactly one top-level def")
        return errors
    fn = tree.body[0]
    if fn.name != expected_name:
        errors.append(f"function name must be {expected_name}")
    if len(fn.args.args) != 1 or fn.args.args[0].arg != "ans":
        errors.append("function must have exactly one argument named ans")
    if fn.args.defaults or fn.args.kw_defaults or fn.args.vararg or fn.args.kwarg or fn.args.posonlyargs:
        errors.append("function arguments must have no defaults, varargs or positional-only args")
    if fn.decorator_list:
        errors.append("decorators are forbidden")
    if fn.returns or any(arg.annotation is not None for arg in fn.args.args):
        errors.append("annotations are forbidden")

    forbidden_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.ClassDef,
        ast.AsyncFunctionDef,
        ast.Lambda,
        ast.With,
        ast.AsyncWith,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
        ast.Global,
        ast.Nonlocal,
        ast.Assert,
    )
    for node in ast.walk(tree):
        if isinstance(node, forbidden_nodes):
            errors.append(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and "__" in node.id:
            errors.append(f"dunder name is forbidden: {node.id}")
        if isinstance(node, ast.Attribute) and "__" in node.attr:
            errors.append(f"dunder attribute is forbidden: {node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CHECKER_CALLS:
                errors.append(f"forbidden call: {node.func.id}")
            if node.func.id == expected_name:
                errors.append("recursion is forbidden")
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            errors.append("while True is forbidden")

    try:
        table = symtable.symtable(source, "<checker>", "exec")
        children = table.get_children()
        if len(children) == 1:
            allowed_globals = set(TRUSTED_CHECKER_GLOBALS)
            for nested in [children[0], *children[0].get_children()]:
                for symbol in nested.get_symbols():
                    if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in allowed_globals:
                        errors.append(f"unavailable global name: {symbol.get_name()}")
    except SyntaxError as exc:
        errors.append(f"symbol table error: {exc}")

    return list(dict.fromkeys(errors))


def _compile_checker(source: str, expected_name: str) -> Any:
    errors = validate_checker_code(source, expected_name)
    if errors:
        raise ValueError("; ".join(errors))
    locals_: dict[str, object] = {}
    exec(source.strip(), TRUSTED_CHECKER_GLOBALS, locals_)
    if not locals_:
        raise ValueError("checker created no value")
    name, candidate = locals_.popitem()
    if name != expected_name or not callable(candidate):
        raise ValueError("checker executor would not select the expected callable")
    return candidate


def _validate_checker_result(result: Any) -> None:
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or not isinstance(result[0], bool)
        or (result[1] is not None and not isinstance(result[1], str))
    ):
        raise ValueError("checker result must be (bool, str | None)")


def audit_python_checker(checker: PythonChecker, expected_name: str) -> list[str]:
    errors: list[str] = []
    if checker.function_name != expected_name:
        errors.append(f"function_name must be {expected_name}")
    if checker.status != "ready":
        if checker.python_code or checker.tests:
            errors.append("non-ready checker must have empty python_code and tests")
        if not checker.placeholder:
            errors.append("non-ready checker requires placeholder")
        return errors
    if checker.placeholder:
        errors.append("ready checker must have empty placeholder")
    if not 6 <= len(checker.tests) <= 16:
        errors.append("ready checker must have 6–16 tests")
    if not any(test.should_pass for test in checker.tests):
        errors.append("tests need at least one passing case")
    if not any(not test.should_pass for test in checker.tests):
        errors.append("tests need at least one failing case")
    if errors:
        return errors
    try:
        fn = _compile_checker(checker.python_code, expected_name)
        for test in checker.tests:
            try:
                result = fn(test.student_answer)
                _validate_checker_result(result)
                if result[0] is not test.should_pass:
                    errors.append(
                        f"test {test.purpose!r} expected {test.should_pass}, got {result[0]} for {test.student_answer!r}"
                    )
            except Exception as exc:
                errors.append(f"test {test.purpose!r} raised {type(exc).__name__}: {exc}")
        for smoke in ("", "не ответ", "0" * 6001):
            try:
                _validate_checker_result(fn(smoke))
            except Exception as exc:
                errors.append(f"smoke input raised {type(exc).__name__}: {exc}")
    except Exception as exc:
        errors.append(str(exc))
    return list(dict.fromkeys(errors))


async def generate_python_checker(
    task_latex: str,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    reasoning_effort: str | None = "low",
    max_attempts: int = 2,
    max_output_tokens: int = 16000,
    timeout_seconds: float = 600,
    prompt_cache: bool = True,
    prompt_cache_ttl: Literal["5m", "1h"] = "1h",
    diagnostics: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate one independent trusted checker from one task's LaTeX."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    cleaned = clean_latex_document(task_latex)
    function_name = make_checker_function_name(cleaned)
    external_images = _external_image_refs(cleaned)
    user_prompt = (
        f"Точное имя функции: {function_name}\n"
        f"Внешние рисунки, которых нет в запросе: {json.dumps(external_images, ensure_ascii=False)}\n"
        "Сгенерируй чекер только из следующего очищенного LaTeX:\n\n"
        + cleaned
    )

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics["preprocessing"] = {
            "source_chars": len(task_latex),
            "cleaned_chars": len(cleaned),
            "function_name": function_name,
            "external_images": external_images,
        }
        diagnostics["attempts"] = []

    previous: dict[str, Any] | None = None
    last_errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": CHECKER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if previous is not None:
            messages.append({"role": "user", "content": _repair_message(previous, last_errors)})
        attempt_diag: dict[str, Any] = {"attempt": attempt, "phase": "checker_generation"}
        if diagnostics is not None:
            diagnostics["attempts"].append(attempt_diag)
        try:
            raw = await _openrouter_chat(
                api_key=key,
                proxy=None,
                model=model,
                messages=messages,
                response_schema=CHECKER_REMOTE_SCHEMA,
                schema_name=CHECKER_SCHEMA_NAME,
                reasoning_effort=reasoning_effort,
                max_output_tokens=max_output_tokens,
                session_id="vmsh-python-checker-v3",
                timeout_seconds=timeout_seconds,
                prompt_cache=prompt_cache,
                prompt_cache_ttl=prompt_cache_ttl,
                diagnostics=attempt_diag,
            )
            previous = raw
            checker = PythonChecker.model_validate(raw)
            errors = audit_python_checker(checker, function_name)
            attempt_diag["semantic_errors"] = errors
            if not errors:
                return checker.model_dump(mode="json")
            last_errors = errors
        except (ValidationError, ValueError) as exc:
            last_errors = [str(exc)]
            attempt_diag["validation_error"] = str(exc)
        except Exception as exc:
            attempt_diag["fatal_error"] = _error_details(exc)
            raise
    raise ValueError("Checker output failed validation after retries:\n- " + "\n- ".join(last_errors))


__all__ = [
    "ANSWER_TYPES",
    "CHECKER_REMOTE_SCHEMA",
    "CHECKER_SCHEMA_NAME",
    "CHECKER_SYSTEM_PROMPT",
    "DEFAULT_MODEL",
    "FACT_REVIEW_REMOTE_SCHEMA",
    "FACT_REVIEW_SCHEMA_NAME",
    "FACT_REVIEW_SYSTEM_PROMPT",
    "FactualRowReview",
    "LESSON_REMOTE_SCHEMA",
    "LESSON_SCHEMA_NAME",
    "LESSON_SYSTEM_PROMPT",
    "LessonFactReview",
    "LessonMarkup",
    "PythonChecker",
    "TRUSTED_CHECKER_GLOBALS",
    "apply_fact_review",
    "audit_lesson_markup",
    "audit_python_checker",
    "build_lesson_request_preview",
    "canonicalize_with_source",
    "clean_latex_document",
    "decode_tex_bytes",
    "generate_lesson_json",
    "generate_python_checker",
    "infer_lesson_identity",
    "make_checker_function_name",
    "openrouter_schema",
    "parse_lesson_structure",
    "read_tex_file",
    "strip_tex_comments",
    "validate_checker_code",
    "validate_openrouter_schema",
]

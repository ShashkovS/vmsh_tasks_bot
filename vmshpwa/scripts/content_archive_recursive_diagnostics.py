"""Recursively scan the two owner-local VMSh lesson archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from helpers.pwa.content import (  # noqa: E402
    COMPILER_VERSION,
    ContentCompileError,
    ContentRole,
    DiagnosticSeverity,
    compile_latex,
)


DEFAULT_ROOTS = (
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2025-2026 5-7",
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2013-2025 старые",
)
DEFAULT_JSON_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-archive-all-errors.json"
)
DEFAULT_MARKDOWN_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-archive-all-errors.md"
)
LESSON_MASK = re.compile(r"usl-\d{2}-.\.tex|usl-\d{2}-.-sol\.tex")
REPLACEMENT_CHARACTER_UTF8 = b"\xef\xbf\xbd"
REPORT_SCHEMA_VERSION = 1


class RecursiveArchiveDiagnosticsError(ValueError):
    """Raised when the configured owner-local corpora are unavailable."""


def _role_for(path: Path) -> ContentRole:
    return ContentRole.SOLUTION if path.stem.endswith("-sol") else ContentRole.CONDITION


def discover_sources(roots: Sequence[Path]) -> list[tuple[Path, Path]]:
    """Return exact-mask TeX sources as ``(root, path)`` pairs."""

    discovered: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.is_dir():
            raise RecursiveArchiveDiagnosticsError(
                f"Archive directory is unavailable: {root}"
            )
        discovered.extend(
            (root, path)
            for path in root.rglob("*.tex")
            if LESSON_MASK.fullmatch(path.name)
        )
    if not discovered:
        raise RecursiveArchiveDiagnosticsError(
            "No TeX sources matched usl-??-?.tex / usl-??-?-sol.tex"
        )
    return sorted(discovered, key=lambda item: (item[0].name, item[1].as_posix()))


def _display_path(root: Path, path: Path) -> str:
    return f"{root.name}/{path.relative_to(root).as_posix()}"


def build_report(roots: Sequence[Path] = DEFAULT_ROOTS) -> dict[str, Any]:
    """Compile every matching source and retain every positional error."""

    sources = discover_sources(roots)
    ignored: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    errors_by_code: Counter[str] = Counter()
    warnings_by_code: Counter[str] = Counter()
    encodings: Counter[str] = Counter()
    problem_count = 0
    corpus_records: list[dict[str, str]] = []

    for root, path in sources:
        payload = path.read_bytes()
        display_path = _display_path(root, path)
        source_sha256 = hashlib.sha256(payload).hexdigest()
        role = _role_for(path)
        corpus_records.append(
            {"path": display_path, "role": role.value, "sha256": source_sha256}
        )
        if REPLACEMENT_CHARACTER_UTF8 in payload:
            ignored.append(
                {
                    "path": display_path,
                    "reason": "contains literal replacement character U+FFFD",
                    "sourceSha256": source_sha256,
                }
            )
            continue
        try:
            result = compile_latex(payload, source_name=path.name, role=role)
        except ContentCompileError as error:
            errors_by_code["compiler.source_envelope"] += 1
            failed.append(
                {
                    "path": display_path,
                    "role": role.value,
                    "sourceSha256": source_sha256,
                    "errors": [
                        {
                            "code": "compiler.source_envelope",
                            "line": 1,
                            "column": 1,
                            "endLine": 1,
                            "endColumn": 1,
                            "message": str(error),
                        }
                    ],
                }
            )
            continue

        encodings[result.source.encoding.value] += 1
        problem_count += len(result.ast.problems)
        source_errors = []
        for diagnostic in result.diagnostics:
            if diagnostic.severity is DiagnosticSeverity.WARNING:
                warnings_by_code[diagnostic.code] += 1
                continue
            if diagnostic.severity is not DiagnosticSeverity.ERROR:
                continue
            errors_by_code[diagnostic.code] += 1
            source_errors.append(
                {
                    "code": diagnostic.code,
                    "line": diagnostic.span.start.line,
                    "column": diagnostic.span.start.column,
                    "endLine": diagnostic.span.end.line,
                    "endColumn": diagnostic.span.end.column,
                    "message": diagnostic.message,
                }
            )
        if source_errors:
            failed.append(
                {
                    "path": display_path,
                    "role": role.value,
                    "sourceSha256": source_sha256,
                    "errors": source_errors,
                }
            )

    corpus_sha256 = hashlib.sha256(
        json.dumps(
            corpus_records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "compilerVersion": COMPILER_VERSION,
        "selection": {
            "roots": [str(root) for root in roots],
            "mask": "usl-??-?.tex | usl-??-?-sol.tex",
            "matchedSourceCount": len(sources),
            "scannedSourceCount": len(sources) - len(ignored),
            "ignoredReplacementCharacterCount": len(ignored),
            "corpusSetSha256": corpus_sha256,
        },
        "summary": {
            "problemCount": problem_count,
            "failedSourceCount": len(failed),
            "errorCount": sum(errors_by_code.values()),
            "encodings": dict(sorted(encodings.items())),
            "errorsByCode": dict(sorted(errors_by_code.items())),
            "warningsByCode": dict(sorted(warnings_by_code.items())),
        },
        "ignoredSources": ignored,
        "failedSources": failed,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    selection = report["selection"]
    summary = report["summary"]
    ignored = (
        "\n".join(f"- `{source['path']}`" for source in report["ignoredSources"])
        or "- нет"
    )
    codes = (
        "\n".join(
            f"- `{code}`: {count}" for code, count in summary["errorsByCode"].items()
        )
        or "- нет"
    )
    warnings = (
        "\n".join(
            f"- `{code}`: {count}" for code, count in summary["warningsByCode"].items()
        )
        or "- нет"
    )
    rows = []
    for source in report["failedSources"]:
        for error in source["errors"]:
            rows.append(
                "| "
                + " | ".join(
                    (
                        f"`{_cell(source['path'])}`",
                        _cell(source["role"]),
                        str(error["line"]),
                        str(error["column"]),
                        f"`{_cell(error['code'])}`",
                        _cell(error["message"]),
                    )
                )
                + " |"
            )
    return f"""# Полная рекурсивная проверка LaTeX-архивов ВМШ

Отчёт построен production-компилятором `{report["compilerVersion"]}`. Выборка
строго соответствует маскам `usl-??-?.tex` и `usl-??-?-sol.tex`; файлы с
буквальным U+FFFD перечислены отдельно и не компилировались.

## Итог

- найдено файлов по маске: **{selection["matchedSourceCount"]}**;
- проверено: **{selection["scannedSourceCount"]}**;
- пропущено из-за U+FFFD: **{selection["ignoredReplacementCharacterCount"]}**;
- найдено задач: **{summary["problemCount"]}**;
- файлов с blocking errors: **{summary["failedSourceCount"]}**;
- blocking errors: **{summary["errorCount"]}**;
- corpus-set SHA-256: `{selection["corpusSetSha256"]}`.

## Пропущенные файлы с U+FFFD

{ignored}

## Коды ошибок

{codes}

## Предупреждения

{warnings}

## Все ошибки

| Файл | Роль | Строка | Колонка | Код | Сообщение |
| --- | --- | ---: | ---: | --- | --- |
{chr(10).join(rows)}
"""


def run(
    mode: str,
    *,
    roots: Sequence[Path] = DEFAULT_ROOTS,
    json_report: Path = DEFAULT_JSON_REPORT,
    markdown_report: Path = DEFAULT_MARKDOWN_REPORT,
) -> int:
    report = build_report(roots)
    expected_json = render_json(report)
    expected_markdown = render_markdown(report)
    if mode == "write":
        json_report.parent.mkdir(parents=True, exist_ok=True)
        json_report.write_text(expected_json, encoding="utf-8")
        markdown_report.write_text(expected_markdown, encoding="utf-8")
        return 0
    if mode == "check":
        return (
            0
            if (
                json_report.exists()
                and markdown_report.exists()
                and json_report.read_text(encoding="utf-8") == expected_json
                and markdown_report.read_text(encoding="utf-8") == expected_markdown
            )
            else 1
        )
    raise RecursiveArchiveDiagnosticsError(f"Unsupported mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check"))
    args = parser.parse_args()
    raise SystemExit(run(args.mode))


if __name__ == "__main__":
    main()

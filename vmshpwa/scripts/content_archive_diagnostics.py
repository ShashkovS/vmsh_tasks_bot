"""Scan an owner-local lesson archive with the production LaTeX compiler."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


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


DEFAULT_ARCHIVE_PARENT = REPOSITORY_ROOT / "docs/deploy/ВМШ 2013-2025 старые"
DEFAULT_ARCHIVE_GLOB = "ВМШ 2024-2025 *"
DEFAULT_JSON_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-archive-2024-2025-errors.json"
)
DEFAULT_MARKDOWN_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-archive-2024-2025-errors.md"
)
REPORT_SCHEMA_VERSION = 1


class ContentArchiveDiagnosticsError(ValueError):
    """Raised when the requested external corpus cannot be scanned safely."""


def discover_default_archive() -> Path:
    """Resolve the single 2024–2025 archive exposed by the owner-local symlink."""

    candidates = sorted(
        path
        for path in DEFAULT_ARCHIVE_PARENT.glob(DEFAULT_ARCHIVE_GLOB)
        if path.is_dir()
    )
    if len(candidates) != 1:
        raise ContentArchiveDiagnosticsError(
            "Expected exactly one 2024-2025 archive below "
            f"{DEFAULT_ARCHIVE_PARENT}, found {len(candidates)}"
        )
    return candidates[0]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _role_for(path: Path) -> ContentRole:
    return ContentRole.SOLUTION if "-sol" in path.stem else ContentRole.CONDITION


def _is_aggregate_placeholder(path: Path) -> bool:
    return re.fullmatch(r"usl-\d{2}-+\d{2}", path.stem) is not None


def build_report(archive_root: Path) -> dict[str, Any]:
    """Compile every top-level TeX file and return every blocking diagnostic."""

    if not archive_root.is_dir():
        raise ContentArchiveDiagnosticsError(
            f"Archive directory is unavailable: {archive_root}"
        )
    discovered_paths = sorted(archive_root.glob("*.tex"))
    if not discovered_paths:
        raise ContentArchiveDiagnosticsError(
            f"Archive has no top-level TeX sources: {archive_root}"
        )
    placeholder_paths = [
        path for path in discovered_paths if _is_aggregate_placeholder(path)
    ]
    paths = [path for path in discovered_paths if not _is_aggregate_placeholder(path)]
    if not paths:
        raise ContentArchiveDiagnosticsError(
            f"Archive has no lesson or solution TeX sources: {archive_root}"
        )

    errors_by_code: Counter[str] = Counter()
    warnings_by_code: Counter[str] = Counter()
    encodings: Counter[str] = Counter()
    failed_records: list[dict[str, Any]] = []
    corpus_records: list[dict[str, str]] = []
    zero_byte_count = 0
    problem_count = 0

    for path in paths:
        payload = path.read_bytes()
        source_sha256 = hashlib.sha256(payload).hexdigest()
        role = _role_for(path)
        corpus_records.append(
            {
                "path": path.name,
                "role": role.value,
                "sha256": source_sha256,
            }
        )
        if not payload:
            zero_byte_count += 1
        try:
            result = compile_latex(
                payload,
                source_name=path.name,
                role=role,
            )
        except ContentCompileError as error:
            errors_by_code["compiler.source_envelope"] += 1
            failed_records.append(
                {
                    "path": path.name,
                    "role": role.value,
                    "sourceSha256": source_sha256,
                    "sourceBytes": len(payload),
                    "encoding": None,
                    "problemCount": 0,
                    "errors": [
                        {
                            "code": "compiler.source_envelope",
                            "line": 1,
                            "column": 1,
                            "endLine": 1,
                            "endColumn": 1,
                            "message": str(error),
                            "recovery": None,
                        }
                    ],
                }
            )
            continue

        encodings[result.source.encoding.value] += 1
        problem_count += len(result.ast.problems)
        errors = []
        for diagnostic in result.diagnostics:
            if diagnostic.severity is DiagnosticSeverity.WARNING:
                warnings_by_code[diagnostic.code] += 1
                continue
            if diagnostic.severity is not DiagnosticSeverity.ERROR:
                continue
            errors_by_code[diagnostic.code] += 1
            errors.append(
                {
                    "code": diagnostic.code,
                    "line": diagnostic.span.start.line,
                    "column": diagnostic.span.start.column,
                    "endLine": diagnostic.span.end.line,
                    "endColumn": diagnostic.span.end.column,
                    "message": diagnostic.message,
                    "recovery": diagnostic.recovery,
                }
            )
        if errors:
            failed_records.append(
                {
                    "path": path.name,
                    "role": role.value,
                    "sourceSha256": source_sha256,
                    "sourceBytes": len(payload),
                    "encoding": result.source.encoding.value,
                    "problemCount": len(result.ast.problems),
                    "errors": errors,
                }
            )

    corpus_sha256 = hashlib.sha256(
        _canonical_json(corpus_records).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "compilerVersion": COMPILER_VERSION,
        "archive": {
            "name": archive_root.name,
            "discoveredTexCount": len(discovered_paths),
            "sourceCount": len(paths),
            "aggregatePlaceholderCount": len(placeholder_paths),
            "zeroBytePlaceholderCount": sum(
                path.stat().st_size == 0 for path in placeholder_paths
            ),
            "zeroByteSourceCount": zero_byte_count,
            "corpusSetSha256": corpus_sha256,
        },
        "summary": {
            "failedSourceCount": len(failed_records),
            "errorCount": sum(errors_by_code.values()),
            "problemCount": problem_count,
            "encodings": dict(sorted(encodings.items())),
            "errorsByCode": dict(sorted(errors_by_code.items())),
            "warningsByCode": dict(sorted(warnings_by_code.items())),
        },
        "failedSources": failed_records,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _table_text(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    archive = report["archive"]
    summary = report["summary"]
    error_lines = "\n".join(
        f"- `{code}`: {count}" for code, count in summary["errorsByCode"].items()
    )
    warning_lines = (
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
                        f"`{_table_text(source['path'])}`",
                        str(error["line"]),
                        str(error["column"]),
                        f"`{_table_text(error['code'])}`",
                        _table_text(error["message"]),
                    )
                )
                + " |"
            )
    return f"""# Ошибки LaTeX-корпуса ВМШ 2024–2025

Отчёт получен production-компилятором `{report["compilerVersion"]}` из всех
верхнеуровневых `.tex` файлов owner-local архива `{archive["name"]}`. Исходные
файлы и симлинк не изменялись.

## Итог

- источников условий/решений: **{archive["sourceCount"]}**;
- найдено верхнеуровневых `.tex`: **{archive["discoveredTexCount"]}**;
- пропущено агрегатных placeholder-файлов: **{archive["aggregatePlaceholderCount"]}**
  (из них пустых: **{archive["zeroBytePlaceholderCount"]}**);
- пустых файлов среди условий/решений: **{archive["zeroByteSourceCount"]}**;
- найденных задач: **{summary["problemCount"]}**;
- файлов с blocking errors: **{summary["failedSourceCount"]}**;
- blocking errors: **{summary["errorCount"]}**;
- corpus-set SHA-256: `{archive["corpusSetSha256"]}`.

## Коды ошибок

{error_lines}

## Предупреждения

{warning_lines}

## Все ошибки

| Файл | Строка | Колонка | Код | Сообщение |
| --- | ---: | ---: | --- | --- |
{chr(10).join(rows)}

Машиночитаемые SHA-256, размеры, роли, encoding и end-position находятся в
`pwa_tests/reports/phase2-content-archive-2024-2025-errors.json`.
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def run(
    mode: str,
    *,
    archive_root: Path,
    json_report: Path,
    markdown_report: Path,
) -> int:
    report = build_report(archive_root)
    rendered = {
        json_report: render_json(report),
        markdown_report: render_markdown(report),
    }
    if mode == "write":
        for path, content in rendered.items():
            _atomic_write(path, content)
        print(
            f"Wrote {report['summary']['errorCount']} errors from "
            f"{report['archive']['sourceCount']} sources"
        )
        return 0

    stale = []
    for path, expected in rendered.items():
        try:
            actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            stale.append(path)
            continue
        if actual != expected:
            stale.append(path)
    if stale:
        print(
            "Archive diagnostic report is missing or stale: "
            + ", ".join(str(path) for path in stale),
            file=sys.stderr,
        )
        return 1
    print(
        f"Verified {report['summary']['errorCount']} errors from "
        f"{report['archive']['sourceCount']} sources"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check"))
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT,
    )
    arguments = parser.parse_args()
    archive_root = arguments.archive_root or discover_default_archive()
    try:
        return run(
            arguments.mode,
            archive_root=archive_root,
            json_report=arguments.json_report,
            markdown_report=arguments.markdown_report,
        )
    except ContentArchiveDiagnosticsError as error:
        print(f"Archive diagnostics refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

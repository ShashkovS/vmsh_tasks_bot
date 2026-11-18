"""Statically exercise the production parser/TikZ preparer on lesson archives.

This command intentionally does not execute TeX, write the database or touch
object storage.  It is the dry preparation gate before the later SVG/S3 import.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from helpers.pwa.content import (  # noqa: E402
    COMPILER_VERSION,
    AssetConversionError,
    ContentCompileError,
    ContentRole,
    DiagnosticSeverity,
    ParserLimits,
    compile_latex,
    prepare_tikz_standalone_document,
    scan_tikz_sources,
)
from helpers.pwa.content.model import FigureNode  # noqa: E402
from helpers.pwa.content.scanner import SourceMap, decode_source  # noqa: E402
from models.pwa.content_asset_names import (  # noqa: E402
    TIKZ_NORMALIZATION_VERSION,
    figure_lookup_names,
    tikz_source_sha256,
)
from vmshpwa.scripts.content_picture_bank import extract_references  # noqa: E402


DEFAULT_ARCHIVES = (
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2025-2026 5-7",
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2013-2025 старые",
)
DEFAULT_BANK = REPOSITORY_ROOT / "docs/deploy/pictures"
DEFAULT_JSON_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-tikz-corpus-2026-08-13.json"
)
DEFAULT_MARKDOWN_REPORT = (
    REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-tikz-corpus-2026-08-13.md"
)
SOURCE_MASKS = ("usl-??-?.tex", "usl-??-?-sol.tex")
REPORT_SCHEMA_VERSION = 1


class TikzCorpusError(ValueError):
    pass


def _matches_source(path: Path) -> bool:
    return any(fnmatch.fnmatchcase(path.name, mask) for mask in SOURCE_MASKS)


def discover_sources(archives: tuple[Path, ...]) -> list[tuple[Path, Path]]:
    discovered: list[tuple[Path, Path]] = []
    for archive in archives:
        if not archive.is_dir():
            raise TikzCorpusError(f"Archive directory is unavailable: {archive}")
        for folder, directory_names, file_names in os.walk(archive, followlinks=True):
            directory_names.sort()
            for file_name in sorted(file_names):
                path = Path(folder) / file_name
                if _matches_source(path):
                    discovered.append((archive, path))
    if not discovered:
        raise TikzCorpusError("No TeX sources match the requested lesson masks")
    return sorted(discovered, key=lambda item: str(item[1]))


def _walk_figures(value: object):
    if isinstance(value, FigureNode):
        yield value
        return
    if isinstance(value, tuple):
        for item in value:
            yield from _walk_figures(item)
        return
    if is_dataclass(value):
        for field in fields(value):
            yield from _walk_figures(getattr(value, field.name))


def _logical_source_name(archive: Path, path: Path) -> str:
    relative = path.relative_to(archive).as_posix()
    return unicodedata.normalize("NFKC", relative)


def _bank_index(bank: Path | None) -> set[str]:
    if bank is None:
        return set()
    if not bank.is_dir():
        raise TikzCorpusError(f"Picture bank is unavailable: {bank}")
    return {
        unicodedata.normalize("NFC", path.relative_to(bank).as_posix()).casefold()
        for path in bank.rglob("*")
        if path.is_file()
    }


def _external_reference_exists(logical_name: str, bank_index: set[str]) -> bool:
    candidates = [logical_name]
    normalized = logical_name.replace("\\", "/")
    if normalized.casefold().startswith("pictures/"):
        candidates.append(normalized[len("pictures/") :])
    for candidate in candidates:
        try:
            lookup = figure_lookup_names(candidate)
        except (TypeError, ValueError):
            continue
        if any(name.casefold() in bank_index for name, _key in lookup):
            return True
    return False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _report_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def _without_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        escaped = False
        cut = len(line)
        for index, character in enumerate(line):
            if character == "%" and not escaped:
                cut = index
                break
            if character == "\\":
                escaped = not escaped
            else:
                escaped = False
        lines.append(line[:cut])
    return "\n".join(lines)


def build_report(
    archives: tuple[Path, ...], *, bank: Path | None = DEFAULT_BANK
) -> dict[str, Any]:
    paths = discover_sources(archives)
    bank_index = _bank_index(bank)
    encodings: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    contexts: Counter[str] = Counter()
    scan_issues: Counter[str] = Counter()
    parser_errors: Counter[str] = Counter()
    parser_warnings: Counter[str] = Counter()
    preparation_errors: Counter[str] = Counter()
    normalized_hashes: Counter[str] = Counter()
    issue_records: list[dict[str, object]] = []
    parser_diagnostic_records: list[dict[str, object]] = []
    unrepresented: list[dict[str, object]] = []
    missing_external: list[dict[str, object]] = []
    dynamic_external: list[dict[str, object]] = []
    corpus_records: list[dict[str, object]] = []
    source_with_tikz = 0
    raw_environment_count = 0
    uncommented_environment_count = 0
    active_environment_block_count = 0
    parser_tikz_count = 0
    parser_failed_source_count = 0
    external_reference_count = 0
    matched_external_count = 0

    for archive, path in paths:
        payload = path.read_bytes()
        relative = path.relative_to(archive).as_posix()
        source_map_name = _logical_source_name(archive, path)
        source_sha256 = hashlib.sha256(payload).hexdigest()
        corpus_records.append(
            {
                "archive": archive.name,
                "path": relative,
                "sha256": source_sha256,
            }
        )
        try:
            decoded = decode_source(
                payload, source_name=source_map_name, limits=ParserLimits()
            )
        except (UnicodeDecodeError, ValueError) as error:
            parser_failed_source_count += 1
            parser_errors["compiler.source_envelope"] += 1
            issue_records.append(
                {
                    "archive": archive.name,
                    "path": relative,
                    "line": 1,
                    "code": "compiler.source_envelope",
                    "message": str(error),
                }
            )
            continue
        encodings[decoded.encoding.value] += 1
        source_map = SourceMap(source_map_name, decoded.text)
        raw_environment_count += decoded.text.count(r"\begin{tikzpicture}")
        uncommented_environment_count += _without_comments(decoded.text).count(
            r"\begin{tikzpicture}"
        )
        scan = scan_tikz_sources(decoded.text)
        if scan.sources:
            source_with_tikz += 1
        for issue in scan.issues:
            scan_issues[issue.code] += 1
            position = source_map.position(issue.start)
            issue_records.append(
                {
                    "archive": archive.name,
                    "path": relative,
                    "line": position.line,
                    "column": position.column,
                    "code": issue.code,
                    "message": issue.message,
                }
            )

        for source in scan.sources:
            kinds[source.kind] += 1
            if source.kind != "inline":
                active_environment_block_count += source.raw_source.count(
                    r"\begin{tikzpicture}"
                )
            contexts.update(source.context_kinds)
            normalized_hashes[tikz_source_sha256(source.source)] += 1
            position = source_map.position(source.start)
            try:
                prepare_tikz_standalone_document(source.source)
            except AssetConversionError as error:
                preparation_errors[error.code] += 1
                issue_records.append(
                    {
                        "archive": archive.name,
                        "path": relative,
                        "line": position.line,
                        "column": position.column,
                        "code": error.code,
                        "message": str(error),
                    }
                )
            references, dynamic = extract_references(
                source.source,
                f"{archive.name}/{relative}",
            )
            external_reference_count += len(references)
            for reference in references:
                if _external_reference_exists(reference.logical_name, bank_index):
                    matched_external_count += 1
                else:
                    missing_external.append(
                        {
                            "archive": archive.name,
                            "path": relative,
                            "tikzLine": position.line,
                            "logicalName": reference.logical_name,
                            "command": reference.command,
                        }
                    )
            for item in dynamic:
                dynamic_external.append(
                    {
                        "archive": archive.name,
                        "path": relative,
                        "tikzLine": position.line,
                        "expression": item["expression"],
                        "command": item["command"],
                    }
                )

        role = ContentRole.SOLUTION if "-sol" in path.stem else ContentRole.CONDITION
        try:
            compiled = compile_latex(
                payload,
                source_name=source_map_name,
                role=role,
            )
        except ContentCompileError as error:
            parser_failed_source_count += 1
            parser_errors["compiler.source_envelope"] += 1
            issue_records.append(
                {
                    "archive": archive.name,
                    "path": relative,
                    "line": 1,
                    "column": 1,
                    "code": "compiler.source_envelope",
                    "message": str(error),
                }
            )
            continue
        source_has_error = False
        for diagnostic in compiled.diagnostics:
            if diagnostic.severity is DiagnosticSeverity.ERROR:
                parser_errors[diagnostic.code] += 1
                source_has_error = True
            elif diagnostic.severity is DiagnosticSeverity.WARNING:
                parser_warnings[diagnostic.code] += 1
            else:
                continue
            parser_diagnostic_records.append(
                {
                    "archive": archive.name,
                    "path": relative,
                    "line": diagnostic.span.start.line,
                    "column": diagnostic.span.start.column,
                    "severity": diagnostic.severity.value,
                    "code": diagnostic.code,
                    "message": diagnostic.message,
                }
            )
        if source_has_error:
            parser_failed_source_count += 1
        represented_hashes = Counter(
            tikz_source_sha256(figure.tikz_source)
            for figure in _walk_figures(compiled.ast)
            if figure.kind.value == "tikz" and figure.tikz_source is not None
        )
        parser_tikz_count += sum(represented_hashes.values())
        for source in scan.sources:
            source_hash = tikz_source_sha256(source.source)
            if represented_hashes[source_hash]:
                represented_hashes[source_hash] -= 1
                continue
            position = source_map.position(source.start)
            unrepresented.append(
                {
                    "archive": archive.name,
                    "path": relative,
                    "line": position.line,
                    "column": position.column,
                    "kind": source.kind,
                }
            )

    unique_count = len(normalized_hashes)
    tikz_count = sum(kinds.values())
    corpus_hash = hashlib.sha256(
        _canonical_json(corpus_records).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "compilerVersion": COMPILER_VERSION,
        "normalizationVersion": TIKZ_NORMALIZATION_VERSION,
        "scope": {
            "archives": [_report_path(path) for path in archives],
            "sourceMasks": list(SOURCE_MASKS),
            "pictureBank": _report_path(bank) if bank is not None else None,
            "sourceCount": len(paths),
            "sourceWithTikzCount": source_with_tikz,
            "corpusSetSha256": corpus_hash,
        },
        "summary": {
            "encodings": dict(sorted(encodings.items())),
            "rawTikzEnvironmentCount": raw_environment_count,
            "activeTikzCount": tikz_count,
            "activeTikzEnvironmentBlockCount": active_environment_block_count,
            "commentedTikzEnvironmentCount": raw_environment_count
            - uncommented_environment_count,
            "inactiveTikzEnvironmentCount": uncommented_environment_count
            - active_environment_block_count,
            "tikzKinds": dict(sorted(kinds.items())),
            "uniqueNormalizedTikzCount": unique_count,
            "duplicateTikzOccurrenceCount": tikz_count - unique_count,
            "contextKinds": dict(sorted(contexts.items())),
            "scanIssuesByCode": dict(sorted(scan_issues.items())),
            "preparationErrorsByCode": dict(sorted(preparation_errors.items())),
            "parserTikzFigureCount": parser_tikz_count,
            "parserUnrepresentedTikzCount": len(unrepresented),
            "parserFailedSourceCount": parser_failed_source_count,
            "parserErrorsByCode": dict(sorted(parser_errors.items())),
            "parserWarningsByCode": dict(sorted(parser_warnings.items())),
            "externalReferenceCount": external_reference_count,
            "matchedExternalReferenceCount": matched_external_count,
            "missingExternalReferenceCount": len(missing_external),
            "dynamicExternalReferenceCount": len(dynamic_external),
        },
        "issues": issue_records,
        "parserDiagnostics": parser_diagnostic_records,
        "unrepresentedTikz": unrepresented,
        "missingExternalReferences": missing_external,
        "dynamicExternalReferences": dynamic_external,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _counter_lines(values: dict[str, int]) -> str:
    return "\n".join(f"- `{key}`: {value}" for key, value in values.items()) or "- нет"


def render_markdown(report: dict[str, Any]) -> str:
    scope = report["scope"]
    summary = report["summary"]
    issue_rows = "\n".join(
        "| "
        + " | ".join(
            (
                f"`{item['archive']}/{item['path']}`",
                str(item["line"]),
                f"`{item['code']}`",
                str(item["message"]).replace("|", r"\|"),
            )
        )
        + " |"
        for item in report["issues"]
    ) or "| — | — | — | нет |"
    missing_rows = "\n".join(
        f"| `{item['archive']}/{item['path']}` | {item['tikzLine']} | "
        f"`{item['logicalName']}` |"
        for item in report["missingExternalReferences"][:100]
    ) or "| — | — | нет |"
    return f"""# Статический прогон TikZ-корпуса ВМШ

Прогон использует production parser `{report['compilerVersion']}` и
нормализацию `{report['normalizationVersion']}`. TeX/PDF/SVG не компилировались,
S3 и БД не изменялись. Рекурсивно просмотрены только маски
`usl-??-?.tex` и `usl-??-?-sol.tex` с переходом по симлинкам.

## Итог

- TeX-файлов: **{scope['sourceCount']}**;
- файлов с активным TikZ: **{scope['sourceWithTikzCount']}**;
- активных TikZ: **{summary['activeTikzCount']}**
  ({summary['tikzKinds']});
- закомментированных `tikzpicture`, правильно исключённых: **{summary['commentedTikzEnvironmentCount']}**;
- активных по строке, но исключённых как document tail или тело macro-definition:
  **{summary['inactiveTikzEnvironmentCount']}**;
- уникальных после минимальной нормализации: **{summary['uniqueNormalizedTikzCount']}**;
- повторных вхождений: **{summary['duplicateTikzOccurrenceCount']}**;
- статических ошибок подготовки standalone: **{sum(summary['preparationErrorsByCode'].values())}**;
- TikZ, не дошедших до semantic AST: **{summary['parserUnrepresentedTikzCount']}**;
- внешних ссылок из TikZ: **{summary['externalReferenceCount']}**, найдено в банке
  **{summary['matchedExternalReferenceCount']}**, не найдено
  **{summary['missingExternalReferenceCount']}**, динамических
  **{summary['dynamicExternalReferenceCount']}**.

Corpus-set SHA-256: `{scope['corpusSetSha256']}`.

## Подключённый контекст

{_counter_lines(summary['contextKinds'])}

## Проблемы TikZ-сканера

{_counter_lines(summary['scanIssuesByCode'])}

## Blocking diagnostics общего parser

{_counter_lines(summary['parserErrorsByCode'])}

## Все статические ошибки TikZ

| Файл | Строка | Код | Сообщение |
| --- | ---: | --- | --- |
{issue_rows}

## Не найденные внешние файлы из TikZ (первые 100)

| Файл | Строка TikZ | Имя |
| --- | ---: | --- |
{missing_rows}

Полные списки непредставленных TikZ, внешних ссылок и parser diagnostics
находятся в соседнем JSON. Этот отчёт является только статическим gate;
реальные ошибки TeX toolchain появятся на следующем шаге компиляции SVG.
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def run(
    mode: str,
    *,
    archives: tuple[Path, ...],
    bank: Path | None,
    json_report: Path,
    markdown_report: Path,
) -> int:
    report = build_report(archives, bank=bank)
    rendered = {
        json_report: render_json(report),
        markdown_report: render_markdown(report),
    }
    if mode == "write":
        for path, content in rendered.items():
            _atomic_write(path, content)
        print(
            f"Wrote {report['summary']['activeTikzCount']} active TikZ sources "
            f"from {report['scope']['sourceCount']} TeX files"
        )
        return 0
    stale = [
        path
        for path, expected in rendered.items()
        if not path.exists() or path.read_text(encoding="utf-8") != expected
    ]
    if stale:
        print(
            "TikZ corpus report is missing or stale: "
            + ", ".join(str(path) for path in stale),
            file=sys.stderr,
        )
        return 1
    print(
        f"Verified {report['summary']['activeTikzCount']} active TikZ sources "
        f"from {report['scope']['sourceCount']} TeX files"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check"))
    parser.add_argument("--archive", action="append", type=Path)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--without-bank", action="store_true")
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument(
        "--markdown-report", type=Path, default=DEFAULT_MARKDOWN_REPORT
    )
    arguments = parser.parse_args()
    archives = tuple(arguments.archive) if arguments.archive else DEFAULT_ARCHIVES
    try:
        return run(
            arguments.mode,
            archives=archives,
            bank=None if arguments.without_bank else arguments.bank,
            json_report=arguments.json_report,
            markdown_report=arguments.markdown_report,
        )
    except TikzCorpusError as error:
        print(f"TikZ corpus scan refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

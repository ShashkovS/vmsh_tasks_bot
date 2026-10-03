"""Build/check the privacy-safe Phase-2 content compiler characterization.

Only paths, hashes, counters and diagnostic codes are persisted.  Mathematical
text, titles, asset URLs and rendered derivatives are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from dataclasses import fields, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from helpers.pwa.content import COMPILER_VERSION, ContentRole, compile_latex  # noqa: E402
from helpers.pwa.content.model import FigureNode  # noqa: E402
from vmshpwa.scripts.golden_corpus import (  # noqa: E402
    MANIFEST_PATH,
    validate_manifest,
)


JSON_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-compiler.json"
MARKDOWN_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/phase2-content-compiler.md"
REPORT_SCHEMA_VERSION = 1


class ContentCharacterizationError(ValueError):
    """Raised when the committed characterization is stale or malformed."""


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def _walk(value: Any):
    if isinstance(value, StrEnum | str | bytes | int | float | bool) or value is None:
        return
    if is_dataclass(value):
        yield value
        for field in fields(value):
            yield from _walk(getattr(value, field.name))
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
        return
    if isinstance(value, tuple | list):
        for item in value:
            yield from _walk(item)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_report() -> dict[str, Any]:
    """Compile every golden TeX source and return content-free evidence."""

    validate_manifest()
    manifest_payload = MANIFEST_PATH.read_bytes()
    manifest = json.loads(manifest_payload)
    records: list[dict[str, Any]] = []
    aggregate_nodes: Counter[str] = Counter()
    aggregate_diagnostics: Counter[str] = Counter()
    aggregate_roles: Counter[str] = Counter()
    aggregate_encodings: Counter[str] = Counter()
    signal_failures: list[dict[str, str]] = []
    problem_count = 0

    for entry in manifest["entries"]:
        if entry["format"] != "tex":
            continue
        payload = (REPOSITORY_ROOT / entry["path"]).read_bytes()
        result = compile_latex(
            payload,
            source_name=entry["path"],
            role=ContentRole(entry["role"]),
        )
        nodes = Counter(type(node).__name__ for node in _walk(result.ast))
        diagnostics = Counter(
            f"{item.severity.value}:{item.code}" for item in result.diagnostics
        )
        figures = [node for node in _walk(result.ast) if isinstance(node, FigureNode)]
        figure_kinds = Counter(node.kind.value for node in figures)
        structural = entry["structure"]
        signals = {
            "rawHashMatchesManifest": result.source.raw_sha256 == entry["sha256"],
            "encodingMatchesManifest": result.source.encoding.value
            == entry["encoding"],
            "hasActiveProblems": bool(result.ast.problems),
            "webDocumentProduced": result.web_document is not None,
        }
        for signal, passed in signals.items():
            if not passed:
                signal_failures.append({"path": entry["path"], "signal": signal})
        record = {
            "path": entry["path"],
            "role": entry["role"],
            "encoding": result.source.encoding.value,
            "rawSha256": result.source.raw_sha256,
            "astSha256": result.ast_sha256,
            "webDocumentSha256": (
                result.web_document.sha256 if result.web_document is not None else None
            ),
            "webPreviewSha256": result.web.sha256,
            "telegramRichSha256": result.telegram.sha256,
            "activeProblemCount": len(result.ast.problems),
            "lexicalProblemMarkerCount": structural["problemCount"],
            "nodeCounts": dict(sorted(nodes.items())),
            "figureKinds": dict(sorted(figure_kinds.items())),
            "lexicalFigureMarkers": {
                "includegraphics": structural["includedGraphicCount"],
                "tikzpicture": structural["tikzPictureCount"],
            },
            "diagnostics": dict(sorted(diagnostics.items())),
            "signals": signals,
        }
        records.append(record)
        aggregate_nodes.update(nodes)
        aggregate_diagnostics.update(diagnostics)
        aggregate_roles[entry["role"]] += 1
        aggregate_encodings[result.source.encoding.value] += 1
        problem_count += len(result.ast.problems)

    record_set_sha256 = hashlib.sha256(
        _canonical_json(records).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "compilerVersion": COMPILER_VERSION,
        "goldenManifest": {
            "path": _relative(MANIFEST_PATH),
            "sha256": hashlib.sha256(manifest_payload).hexdigest(),
            "entryCount": manifest["entryCount"],
            "texEntryCount": len(records),
        },
        "summary": {
            "compiledSourceCount": len(records),
            "activeProblemCount": problem_count,
            "roles": dict(sorted(aggregate_roles.items())),
            "encodings": dict(sorted(aggregate_encodings.items())),
            "nodeCounts": dict(sorted(aggregate_nodes.items())),
            "diagnostics": dict(sorted(aggregate_diagnostics.items())),
            "signalFailureCount": len(signal_failures),
            "recordSetSha256": record_set_sha256,
        },
        "signalFailures": signal_failures,
        "records": records,
        "privacy": {
            "containsSourceText": False,
            "containsRenderedContent": False,
            "containsTitles": False,
            "containsAssetUrls": False,
        },
    }


def render_json(report: dict[str, Any] | None = None) -> str:
    return json.dumps(report or build_report(), ensure_ascii=False, indent=2) + "\n"


def render_markdown(report: dict[str, Any] | None = None) -> str:
    data = report or build_report()
    summary = data["summary"]
    diagnostics = summary["diagnostics"] or {"none": 0}
    diagnostic_lines = "\n".join(
        f"- `{name}`: {count}" for name, count in diagnostics.items()
    )
    return f"""# Phase 2 content compiler characterization

Этот отчёт воспроизводится из 54/54 записей golden manifest; compiler обрабатывает
30 TeX sources, а PDF/JSON остаются под общим manifest gate. Здесь нет условий,
названий задач, rendered HTML, Telegram-текста или URL assets — только hashes,
структурные счётчики и коды диагностик.

## Итог

- compiler: `{data["compilerVersion"]}`;
- manifest: `{data["goldenManifest"]["path"]}`;
- manifest entries: {data["goldenManifest"]["entryCount"]};
- compiled TeX sources: {summary["compiledSourceCount"]};
- active problem AST nodes: {summary["activeProblemCount"]};
- structural signal failures: {summary["signalFailureCount"]};
- deterministic record-set SHA-256: `{summary["recordSetSha256"]}`.

## Диагностики

{diagnostic_lines}

Единственное ожидаемое предупреждение относится к legacy print-layout, который
пересекает semantic boundary в одном solution source. Семантические поля при
этом сохранены; ошибок compiler и утечек соседних material branches нет.

## Проверка

```text
.venv/bin/python vmshpwa/scripts/content_characterization.py check
.venv/bin/pytest -q pwa_tests/domain/test_content_compiler.py pwa_tests/domain/test_telegram_rich.py
```

Машиночитаемые per-source hashes и counters находятся в
`pwa_tests/reports/phase2-content-compiler.json`; они не дублируют содержимое
golden corpus.
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def write_reports() -> None:
    report = build_report()
    _atomic_write(JSON_REPORT, render_json(report))
    _atomic_write(MARKDOWN_REPORT, render_markdown(report))


def validate_reports() -> None:
    report = build_report()
    expected = {
        JSON_REPORT: render_json(report),
        MARKDOWN_REPORT: render_markdown(report),
    }
    for path, content in expected.items():
        try:
            committed = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ContentCharacterizationError(
                f"Missing report: {_relative(path)}"
            ) from error
        if committed != content:
            raise ContentCharacterizationError(
                f"Stale report: {_relative(path)}; inspect compiler/corpus changes before update"
            )


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        if args.command == "write":
            write_reports()
            print(f"Wrote {_relative(JSON_REPORT)} and {_relative(MARKDOWN_REPORT)}")
        else:
            validate_reports()
            print("Verified Phase-2 content compiler characterization")
    except (ContentCharacterizationError, ValueError) as error:
        print(f"content characterization error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

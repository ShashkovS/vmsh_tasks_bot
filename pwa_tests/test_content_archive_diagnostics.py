"""Owner-local archive diagnostics stay deterministic and content-safe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmshpwa.scripts import content_archive_diagnostics as diagnostics


def _source(body: str) -> bytes:
    return ("\\begin{document}\n" + body + "\n\\end{document}\n").encode("utf-8")


def test_archive_report_contains_every_blocking_position(tmp_path: Path) -> None:
    (tmp_path / "good.tex").write_bytes(_source("\\задача Условие. \\кзадача"))
    (tmp_path / "bad-sol.tex").write_bytes(
        _source("\\задача Текст \\ownerOnly \\кзадача")
    )
    (tmp_path / "corrupt.tex").write_bytes(
        _source("\\задача \\\ufffd\ufffd\ufffd{текст} \\кзадача")
    )
    (tmp_path / "usl-01------------------------01.tex").write_bytes(b"")

    report = diagnostics.build_report(tmp_path)

    assert report["archive"]["discoveredTexCount"] == 4
    assert report["archive"]["sourceCount"] == 3
    assert report["archive"]["aggregatePlaceholderCount"] == 1
    assert report["archive"]["zeroBytePlaceholderCount"] == 1
    assert report["archive"]["zeroByteSourceCount"] == 0
    assert report["summary"]["problemCount"] == 3
    assert report["summary"]["failedSourceCount"] == 2
    assert report["summary"]["errorsByCode"] == {
        "latex.unknown_macro": 1,
        "source.replacement_character": 1,
    }
    bad = next(
        source for source in report["failedSources"] if source["path"] == "bad-sol.tex"
    )
    assert bad["role"] == "solution"
    assert bad["errors"][0]["line"] == 2
    assert bad["errors"][0]["column"] == 15
    assert (
        report["archive"]["corpusSetSha256"]
        == (diagnostics.build_report(tmp_path)["archive"]["corpusSetSha256"])
    )


def test_archive_report_write_and_check_round_trip(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "lesson.tex").write_bytes(_source("\\задача Условие. \\кзадача"))
    json_report = tmp_path / "report.json"
    markdown_report = tmp_path / "report.md"

    assert (
        diagnostics.run(
            "write",
            archive_root=archive,
            json_report=json_report,
            markdown_report=markdown_report,
        )
        == 0
    )
    assert (
        diagnostics.run(
            "check",
            archive_root=archive,
            json_report=json_report,
            markdown_report=markdown_report,
        )
        == 0
    )
    assert (
        json.loads(json_report.read_text(encoding="utf-8"))["summary"]["errorCount"]
        == 0
    )
    assert "Все ошибки" in markdown_report.read_text(encoding="utf-8")


def test_archive_report_rejects_missing_or_empty_corpus(tmp_path: Path) -> None:
    with pytest.raises(diagnostics.ContentArchiveDiagnosticsError):
        diagnostics.build_report(tmp_path / "missing")
    with pytest.raises(diagnostics.ContentArchiveDiagnosticsError):
        diagnostics.build_report(tmp_path)

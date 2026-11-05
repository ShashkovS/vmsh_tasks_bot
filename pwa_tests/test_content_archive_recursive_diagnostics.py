"""Contract tests for the exact-mask recursive archive report."""

from pathlib import Path

from vmshpwa.scripts import content_archive_recursive_diagnostics as diagnostics


def _source(body: str) -> bytes:
    return ("\\begin{document}\n" + body + "\n\\end{document}\n").encode()


def test_recursive_report_uses_exact_mask_roles_and_fffd_exclusion(
    tmp_path: Path,
) -> None:
    current = tmp_path / "current"
    old = tmp_path / "old"
    nested = old / "nested"
    current.mkdir()
    nested.mkdir(parents=True)
    (current / "usl-01-x.tex").write_bytes(_source("\\задача Условие. \\кзадача"))
    (nested / "usl-02-p-sol.tex").write_bytes(
        _source("\\задача Условие. \\кзадача\\решение Решение. \\крешение")
    )
    (nested / "usl-03-n.tex").write_bytes(_source("\\задача � \\кзадача"))
    (nested / "usl-3-n.tex").write_bytes(_source("не подходит по маске"))

    report = diagnostics.build_report((current, old))

    assert report["selection"]["matchedSourceCount"] == 3
    assert report["selection"]["scannedSourceCount"] == 2
    assert report["selection"]["ignoredReplacementCharacterCount"] == 1
    assert report["summary"]["problemCount"] == 2
    assert report["summary"]["failedSourceCount"] == 0
    assert report["ignoredSources"][0]["path"] == "old/nested/usl-03-n.tex"


def test_recursive_report_keeps_every_error_position(tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    (root / "usl-01-x.tex").write_bytes(_source("\\задача \\ownerOnly \\кзадача"))

    report = diagnostics.build_report((root,))

    assert report["summary"]["failedSourceCount"] == 1
    error = report["failedSources"][0]["errors"][0]
    assert error["code"] == "latex.unknown_macro"
    assert (error["line"], error["column"]) == (2, 9)

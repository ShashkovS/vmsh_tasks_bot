from __future__ import annotations

from vmshpwa.scripts.content_characterization import build_report, validate_reports


def test_content_characterization_is_current_and_content_free() -> None:
    validate_reports()
    report = build_report()

    assert report["goldenManifest"]["entryCount"] == 54
    assert report["goldenManifest"]["texEntryCount"] == 30
    assert report["summary"]["activeProblemCount"] == 334
    assert report["summary"]["signalFailureCount"] == 0
    assert report["summary"]["diagnostics"] == {
        "warning:latex.layout_crosses_semantic_boundary": 1
    }
    assert report["privacy"] == {
        "containsSourceText": False,
        "containsRenderedContent": False,
        "containsTitles": False,
        "containsAssetUrls": False,
    }

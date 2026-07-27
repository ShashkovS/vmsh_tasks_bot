"""Prove that every approved educational source has a structural fingerprint."""

from __future__ import annotations

import json

import pytest

from vmshpwa.scripts.golden_corpus import (
    CORPUS_ROOT,
    MANIFEST_PATH,
    GoldenCorpusError,
    build_manifest,
    validate_manifest,
)


ENTRY_KEYS = {
    "path",
    "sha256",
    "sizeBytes",
    "mediaType",
    "encoding",
    "lesson",
    "groupCode",
    "role",
    "format",
    "structure",
}
STRUCTURE_KEYS = {
    "tex": {
        "lineCount",
        "hasDocumentClass",
        "hasBeginDocument",
        "hasEndDocument",
        "problemCount",
        "answerCount",
        "hintCount",
        "solutionCount",
        "tikzPictureCount",
        "includedGraphicCount",
    },
    "json": {"topLevelKeys", "resultCount", "topicAssignmentCount"},
    "pdf": {"pdfVersion", "hasEofMarker"},
}


def test_committed_manifest_matches_every_corpus_file():
    validate_manifest()
    committed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    generated = build_manifest()

    assert committed == generated
    assert committed["entryCount"] == 54
    assert {entry["lesson"] for entry in committed["entries"]} == {21, 27, 39, 40, 41}
    assert {entry["groupCode"] for entry in committed["entries"]} == {"n", "p", "x"}
    assert {entry["format"] for entry in committed["entries"]} == {"tex", "json", "pdf"}
    assert {entry["role"] for entry in committed["entries"]} == {
        "condition",
        "solution",
    }
    assert {entry["path"] for entry in committed["entries"]} == {
        path.relative_to(CORPUS_ROOT.parent).as_posix()
        for path in CORPUS_ROOT.iterdir()
    }


def test_manifest_has_only_non_content_metadata():
    manifest = build_manifest()
    assert set(manifest) == {
        "schemaVersion",
        "sourceRoot",
        "generator",
        "entryCount",
        "entries",
    }
    for entry in manifest["entries"]:
        assert set(entry) == ENTRY_KEYS
        assert set(entry["structure"]) == STRUCTURE_KEYS[entry["format"]]
        assert not entry["path"].startswith("/")
        assert ".." not in entry["path"].split("/")
        assert len(entry["sha256"]) == 64
        assert entry["sizeBytes"] > 0


def test_validator_rejects_an_unreviewed_source_fingerprint(tmp_path):
    manifest = build_manifest()
    manifest["entries"][0]["sha256"] = "0" * 64
    stale_path = tmp_path / "golden-manifest.json"
    stale_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(GoldenCorpusError, match="manifest is stale"):
        validate_manifest(stale_path)

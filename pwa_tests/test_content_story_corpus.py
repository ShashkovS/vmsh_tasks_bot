"""Determinism and fail-closed checks for the real Storybook content corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vmshpwa.scripts import content_story_corpus as corpus


def test_real_corpus_binds_three_exact_sources_and_reference_pdfs() -> None:
    fixtures = corpus.generate()

    assert [fixture.lesson_number for fixture in fixtures] == [39, 40, 41]
    for fixture in fixtures:
        payload = json.loads(fixture.content)
        source_path = corpus.REPOSITORY_ROOT / payload["source"]["path"]
        pdf_path = corpus.REPOSITORY_ROOT / payload["referencePdf"]["path"]

        assert payload["fixtureVersion"] == 1
        assert payload["groupCode"] == "n"
        assert payload["webDocument"]["materialKind"] == "condition"
        assert len(payload["webDocument"]["problems"]) == 11
        assert "<tg-math>" in payload["telegram"]["html"]
        assert payload["source"]["sha256"] == hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest()
        assert payload["referencePdf"]["sha256"] == hashlib.sha256(
            pdf_path.read_bytes()
        ).hexdigest()


def test_check_detects_one_stale_generated_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = corpus.generate()
    monkeypatch.setattr(corpus, "FIXTURE_ROOT", tmp_path)
    assert corpus.run("write") == 0
    assert corpus.run("check") == 0

    stale = tmp_path / fixtures[0].path.name
    stale.write_text("{}\n", encoding="utf-8")

    assert corpus.run("check") == 1


def test_missing_approved_input_fails_without_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    monkeypatch.setattr(corpus, "EXAMPLE_ROOT", tmp_path / "missing")
    monkeypatch.setattr(corpus, "FIXTURE_ROOT", output)

    with pytest.raises(corpus.ContentStoryCorpusError, match="unavailable"):
        corpus.generate()
    assert not output.exists()

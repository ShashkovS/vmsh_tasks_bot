"""Build or verify the real Phase-2 Storybook content corpus.

The three selected lesson sheets are repository-owned acceptance inputs.  This
tool compiles their exact bytes into the same browser and Telegram derivatives
used by the HTTP API and binds those derivatives to the checked-in reference
PDF hashes.  It never edits ``_vmsh_examples`` and has no network side effects.

Authoritative gate: ``vmshpwa/docs/testing-strategy.md`` (content visual gate)
and ``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from helpers.pwa.content import ContentRole, DiagnosticSeverity, compile_latex
from vmshpwa.scripts.report_io import atomic_write_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ROOT = REPOSITORY_ROOT / "_vmsh_examples"
FIXTURE_ROOT = (
    REPOSITORY_ROOT
    / "vmshpwa"
    / "packages"
    / "contracts"
    / "fixtures"
    / "content"
    / "golden"
)
LESSONS = (39, 40, 41)
LEVEL_CODE = "n"
FIXTURE_VERSION = 1


class ContentStoryCorpusError(RuntimeError):
    """Raised when the committed corpus is unsafe, incomplete, or stale."""


@dataclass(frozen=True, slots=True)
class GeneratedFixture:
    lesson_number: int
    path: Path
    content: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _repository_path(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:  # pragma: no cover - constant-path invariant
        raise ContentStoryCorpusError("Corpus path escaped the repository") from error


def build_fixture(lesson_number: int) -> GeneratedFixture:
    """Compile one real condition sheet and bind it to its reference PDF."""

    if lesson_number not in LESSONS:
        raise ContentStoryCorpusError("Lesson is outside the approved corpus")
    source_path = EXAMPLE_ROOT / f"usl-{lesson_number}-{LEVEL_CODE}.tex"
    pdf_path = EXAMPLE_ROOT / f"usl-{lesson_number}-{LEVEL_CODE}.pdf"
    try:
        source = source_path.read_bytes()
        pdf = pdf_path.read_bytes()
    except OSError as error:
        raise ContentStoryCorpusError("Approved corpus input is unavailable") from error

    revision_id = f"revision:golden-{lesson_number}-{LEVEL_CODE}-condition"
    result = compile_latex(
        source,
        source_name=f"golden/{source_path.name}",
        role=ContentRole.CONDITION,
        revision_id=revision_id,
        title=f"Занятие {lesson_number} · Начинающие",
    )
    errors = [
        diagnostic.code
        for diagnostic in result.diagnostics
        if diagnostic.severity is DiagnosticSeverity.ERROR
    ]
    if errors:
        raise ContentStoryCorpusError(
            "Approved corpus no longer compiles: " + ", ".join(sorted(set(errors)))
        )
    if result.web_document is None or not result.telegram.content:
        raise ContentStoryCorpusError("Approved corpus derivative is missing")

    document = json.loads(result.web_document.content)
    payload = {
        "fixtureVersion": FIXTURE_VERSION,
        "corpusId": f"lesson-{lesson_number}-{LEVEL_CODE}-condition",
        "lessonNumber": lesson_number,
        "groupCode": LEVEL_CODE,
        "source": {
            "path": _repository_path(source_path),
            "sha256": _sha256(source),
        },
        "referencePdf": {
            "path": _repository_path(pdf_path),
            "sha256": _sha256(pdf),
        },
        "webDocument": document,
        "telegram": {
            "rendererVersion": result.telegram.renderer_version,
            "sha256": result.telegram.sha256,
            "html": result.telegram.content,
        },
    }
    target = FIXTURE_ROOT / f"lesson-{lesson_number}-{LEVEL_CODE}.v1.json"
    return GeneratedFixture(
        lesson_number=lesson_number,
        path=target,
        content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def generate() -> tuple[GeneratedFixture, ...]:
    return tuple(build_fixture(lesson_number) for lesson_number in LESSONS)


def run(mode: Literal["check", "write"]) -> int:
    fixtures = generate()
    stale: list[str] = []
    for fixture in fixtures:
        if mode == "write":
            atomic_write_text(fixture.path, fixture.content)
            continue
        try:
            current = fixture.path.read_text(encoding="utf-8")
        except OSError:
            stale.append(fixture.path.name)
        else:
            if current != fixture.content:
                stale.append(fixture.path.name)
    if stale:
        print(
            "content Storybook corpus is missing or stale: " + ", ".join(stale),
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "write"), nargs="?", default="check")
    arguments = parser.parse_args(argv)
    try:
        return run(arguments.mode)
    except ContentStoryCorpusError as error:
        print(f"content Storybook corpus refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())

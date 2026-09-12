"""Build and verify the non-personal ``_vmsh_examples`` golden manifest.

The manifest intentionally stores structural counters instead of source excerpts.
That makes source drift reviewable without copying educational content (or future
accidental personal data) into a second file.  See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPOSITORY_ROOT / "_vmsh_examples"
MANIFEST_PATH = REPOSITORY_ROOT / "vmshpwa/fixtures/content/golden-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
GENERATOR = "vmshpwa/scripts/golden_corpus.py"

_NAME_PATTERN = re.compile(
    r"^usl-(?P<lesson>\d+)-(?P<group>[npx])(?P<solution>-sol)?"
    r"\.(?P<format>tex|json|pdf)$"
)
_TEX_COMMANDS = {
    "problemCount": "\\задача",
    "answerCount": "\\ответ",
    "hintCount": "\\подсказка",
    "solutionCount": "\\решение",
    "tikzPictureCount": "\\begin{tikzpicture}",
    "includedGraphicCount": "\\includegraphics",
}


class GoldenCorpusError(ValueError):
    """Raised when the corpus or its committed manifest is invalid."""


def _relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as error:
        raise GoldenCorpusError(
            f"Corpus path escapes the repository: {path}"
        ) from error
    return relative.as_posix()


def _decode_tex(payload: bytes) -> tuple[str, str]:
    """Decode the historical TeX source without relying on locale heuristics."""

    if payload.startswith(b"\xef\xbb\xbf"):
        return payload.decode("utf-8-sig"), "utf-8-sig"
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("windows-1251")
        encoding = "windows-1251"
    else:
        encoding = "utf-8"

    first_line = text.splitlines()[0] if text.splitlines() else ""
    if "TEX encoding = Windows Cyrillic" in first_line and encoding != "windows-1251":
        raise GoldenCorpusError(
            "TeX declares Windows Cyrillic but decodes as UTF-8; "
            "review the source encoding explicitly"
        )
    return text, encoding


def _tex_structure(payload: bytes) -> tuple[str, dict[str, Any]]:
    text, encoding = _decode_tex(payload)
    structure: dict[str, Any] = {
        "lineCount": len(text.splitlines()),
        "hasDocumentClass": "\\documentclass" in text,
        "hasBeginDocument": "\\begin{document}" in text,
        "hasEndDocument": "\\end{document}" in text,
    }
    structure.update(
        {name: text.count(command) for name, command in _TEX_COMMANDS.items()}
    )
    if not all(
        structure[key]
        for key in ("hasDocumentClass", "hasBeginDocument", "hasEndDocument")
    ):
        raise GoldenCorpusError("TeX source is missing a complete document envelope")
    if structure["problemCount"] == 0:
        raise GoldenCorpusError("TeX source contains no problem blocks")
    return encoding, structure


def _json_structure(payload: bytes) -> tuple[str, dict[str, Any]]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoldenCorpusError(f"Invalid UTF-8 JSON fixture: {error}") from error
    if not isinstance(document, dict):
        raise GoldenCorpusError("Golden JSON fixture must have an object at its root")
    results = document.get("results")
    if not isinstance(results, list):
        raise GoldenCorpusError("Golden JSON fixture must contain a results array")
    topic_count = 0
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("topics"), list):
            raise GoldenCorpusError(
                "Each golden JSON result must contain a topics array"
            )
        topic_count += len(result["topics"])
    return "utf-8", {
        "topLevelKeys": sorted(document),
        "resultCount": len(results),
        "topicAssignmentCount": topic_count,
    }


def _pdf_structure(payload: bytes) -> tuple[None, dict[str, Any]]:
    header_match = re.match(rb"%PDF-(\d\.\d)", payload[:16])
    if header_match is None or b"%%EOF" not in payload[-2048:]:
        raise GoldenCorpusError("PDF fixture has an invalid header or EOF marker")
    return None, {
        "pdfVersion": header_match.group(1).decode("ascii"),
        "hasEofMarker": True,
    }


def _entry(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GoldenCorpusError(f"Corpus entries must be regular files: {path}")
    match = _NAME_PATTERN.fullmatch(path.name)
    if match is None:
        raise GoldenCorpusError(f"Unrecognised golden corpus filename: {path.name}")

    payload = path.read_bytes()
    file_format = match.group("format")
    if file_format == "tex":
        encoding, structure = _tex_structure(payload)
        media_type = "application/x-tex"
    elif file_format == "json":
        encoding, structure = _json_structure(payload)
        media_type = "application/json"
    else:
        encoding, structure = _pdf_structure(payload)
        media_type = "application/pdf"

    return {
        "path": _relative_path(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sizeBytes": len(payload),
        "mediaType": media_type,
        "encoding": encoding,
        "lesson": int(match.group("lesson")),
        "groupCode": match.group("group"),
        "role": "solution" if match.group("solution") else "condition",
        "format": file_format,
        "structure": structure,
    }


def build_manifest() -> dict[str, Any]:
    """Return a deterministic, schema-validated manifest for every corpus file."""

    if not CORPUS_ROOT.is_dir():
        raise GoldenCorpusError(f"Golden corpus root does not exist: {CORPUS_ROOT}")
    entries = [_entry(path) for path in sorted(CORPUS_ROOT.iterdir())]
    if not entries:
        raise GoldenCorpusError("Golden corpus is empty")
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "sourceRoot": _relative_path(CORPUS_ROOT),
        "generator": GENERATOR,
        "entryCount": len(entries),
        "entries": entries,
    }


def render_manifest(manifest: dict[str, Any] | None = None) -> str:
    return (
        json.dumps(
            manifest if manifest is not None else build_manifest(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )


def validate_manifest(path: Path = MANIFEST_PATH) -> None:
    """Fail if the committed manifest differs from the current source corpus."""

    try:
        committed = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise GoldenCorpusError(f"Golden manifest is missing: {path}") from error
    expected = render_manifest()
    if committed != expected:
        raise GoldenCorpusError(
            "Golden corpus manifest is stale; inspect source changes and run "
            f"`python {GENERATOR} write` after approval"
        )


def write_manifest(path: Path = MANIFEST_PATH) -> None:
    """Atomically replace only the repository-owned manifest path."""

    if path.resolve() != MANIFEST_PATH.resolve():
        raise GoldenCorpusError("Refusing to write outside the canonical manifest path")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_manifest()
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("check", "write"),
        help="validate the committed manifest or replace it after reviewed changes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "write":
            write_manifest()
            print(f"Wrote {_relative_path(MANIFEST_PATH)}")
        else:
            validate_manifest()
            print(f"Verified {_relative_path(MANIFEST_PATH)}")
    except GoldenCorpusError as error:
        print(f"golden corpus error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

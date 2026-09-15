"""Discover and idempotently import only archive-referenced lesson pictures.

The source corpus is enumerated with ripgrep, then decoded and parsed through a
small bounded LaTeX-aware scanner.  See the reusable-picture increment in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import os
import re
import subprocess
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.content import ContentConflict, PwaContentRepository
from helpers.object_storage import create_object_storage
from helpers.pwa.content.asset_service import ContentAssetService
from helpers.pwa.content.assets import ConfiguredContentAssetConverter
from helpers.pwa.content.compiler import compile_latex
from helpers.pwa.content.model import ContentRole, canonical_json
from helpers.pwa.storage_config import load_storage_config
from models.pwa.content_asset_names import FIGURE_EXTENSION_PRIORITY
from models.pwa.content_asset_names import TIKZ_NORMALIZATION_VERSION, tikz_source_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BANK = REPOSITORY_ROOT / "docs/deploy/pictures"
DEFAULT_ARCHIVES = (
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2025-2026 5-7",
    REPOSITORY_ROOT / "docs/deploy/ВМШ 2013-2025 старые",
)
DEFAULT_REPORT = REPOSITORY_ROOT / ".runtime/vmshpwa/content-picture-bank/report.json"
PRODUCTION_OPT_IN = "VMSH_ENABLE_CONTENT_BANK_IMPORT"

_COMMAND_ARGUMENTS: Mapping[str, tuple[int, int]] = {
    "includegraphics": (1, 0),
    "rightpicture": (4, 3),
    "leftpicture": (4, 3),
    "putpicture": (3, 2),
    "putpict": (4, 2),
    "putpicts": (5, 2),
    "dmvnpicmbox": (1, 0),
    "dmvnpicrh": (1, 0),
    "dmvnpiclh": (1, 0),
    "dmvnpic": (1, 0),
    "dmvnpicr": (1, 0),
    "dmvnpicra": (1, 0),
    "dmvnpicl": (1, 0),
    "dmvnpicla": (1, 0),
    "picturer": (1, 0),
}
_COMMAND_RE = re.compile(
    r"\\(" + "|".join(sorted(_COMMAND_ARGUMENTS, key=len, reverse=True)) + r")\*?\b"
)
_ANIMATE_RE = re.compile(r"\\animategraphics\*?\b")
_VARIABLE_RE = re.compile(r"\\([A-Za-z@]+)")
_LITERAL_RE = re.compile(r"[^{}%#\\]+\Z")
_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


class PictureBankError(RuntimeError):
    """The importer cannot continue without guessing or unsafe side effects."""


@dataclass(frozen=True, slots=True)
class PictureReference:
    logical_name: str
    command: str
    source_file: str
    line: int


def _balanced(text: str, start: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    if start >= len(text) or text[start] != opening:
        raise ValueError("balanced argument does not start at delimiter")
    depth = 1
    cursor = start + 1
    while cursor < len(text):
        character = text[cursor]
        if character == opening and (cursor == 0 or text[cursor - 1] != "\\"):
            depth += 1
        elif character == closing and (cursor == 0 or text[cursor - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start + 1 : cursor], cursor + 1
        cursor += 1
    raise ValueError("unclosed LaTeX argument")


def _arguments(text: str, start: int, count: int) -> tuple[list[str], int] | None:
    cursor = start
    arguments: list[str] = []
    try:
        while len(arguments) < count:
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            while cursor < len(text) and text[cursor] == "[":
                _optional, cursor = _balanced(text, cursor, "[", "]")
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                return None
            value, cursor = _balanced(text, cursor)
            arguments.append(value.strip())
    except ValueError:
        return None
    return arguments, cursor


def _strip_comments_and_tail(text: str) -> str:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        output: list[str] = []
        for index, character in enumerate(line):
            if character == "%":
                slashes = 0
                cursor = index - 1
                while cursor >= 0 and line[cursor] == "\\":
                    slashes += 1
                    cursor -= 1
                if slashes % 2 == 0:
                    break
            output.append(character)
        lines.append("".join(output))
    active = "\n".join(lines)
    ending = re.search(r"\\end\s*\{\s*document\s*\}", active)
    return active if ending is None else active[: ending.end()]


def decode_tex(payload: bytes) -> tuple[str, str]:
    directive = re.search(
        br"%\s*!TEX\s+encoding\s*=\s*([^\r\n]+)", payload[:4096], re.IGNORECASE
    )
    if directive is not None:
        label = directive.group(1).strip().decode("ascii", "ignore").casefold()
        if "1251" in label:
            return payload.decode("cp1251"), "cp1251"
        if "utf" in label:
            return payload.decode("utf-8-sig"), "utf-8"
    try:
        return payload.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return payload.decode("cp1251"), "cp1251"


def _literal_variable_values(text: str) -> dict[str, set[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for match in re.finditer(r"\\def\s*\\([A-Za-z@]+)\s*\{", text):
        try:
            value, _end = _balanced(text, match.end() - 1)
        except ValueError:
            continue
        value = value.strip()
        if value and _LITERAL_RE.fullmatch(value):
            values[match.group(1)].add(value)
    for match in re.finditer(r"\\foreach\s+([^\s]+)\s+in\s*\{", text):
        try:
            raw_values, _end = _balanced(text, match.end() - 1)
        except ValueError:
            continue
        variables = [item.lstrip("\\") for item in match.group(1).split("/")]
        for item in raw_values.split(","):
            fields = [field.strip() for field in item.split("/")]
            if len(fields) != len(variables):
                continue
            for variable, field in zip(variables, fields, strict=True):
                if field and _LITERAL_RE.fullmatch(field) and "..." not in field:
                    values[variable].add(field)
    return values


def _expand_name(name: str, variables: Mapping[str, set[str]]) -> tuple[str, ...]:
    used = sorted(set(_VARIABLE_RE.findall(name)))
    if not used:
        return (name.strip(),) if name.strip() else ()
    if any(variable not in variables or not variables[variable] for variable in used):
        return ()
    expanded: list[str] = []
    choices = [sorted(variables[variable]) for variable in used]
    if sum(len(choice) for choice in choices) > 500:
        return ()
    for replacements in itertools.product(*choices):
        value = name
        for variable, replacement in zip(used, replacements, strict=True):
            value = value.replace(f"\\{variable}", replacement)
        if "\\" not in value and "#" not in value:
            expanded.append(value.strip())
    return tuple(dict.fromkeys(expanded))


def _newcommand_expansions(text: str) -> tuple[list[tuple[str, str, int]], list[tuple[int, int]]]:
    results: list[tuple[str, str, int]] = []
    declaration_spans: list[tuple[int, int]] = []
    declaration = re.compile(r"\\newcommand\s*\{\\([A-Za-z@]+)\}\s*(?:\[([0-9])\])?\s*\{")
    for match in declaration.finditer(text):
        try:
            body, end = _balanced(text, match.end() - 1)
        except ValueError:
            continue
        declaration_spans.append((match.start(), end))
        parameter_count = int(match.group(2) or 0)
        if not _COMMAND_RE.search(body):
            continue
        invocation = re.compile(rf"\\{re.escape(match.group(1))}\b")
        for call in invocation.finditer(text):
            if match.start() <= call.start() < end:
                continue
            parsed = _arguments(text, call.end(), parameter_count)
            if parsed is None:
                continue
            arguments, _call_end = parsed
            expanded = body
            for index, value in enumerate(arguments, start=1):
                expanded = expanded.replace(f"#{index}", value)
            for reference in _extract_direct(expanded, "", variables={}):
                results.append((reference.logical_name, match.group(1), call.start()))
    return results, declaration_spans


def _extract_direct(
    text: str,
    source_file: str,
    *,
    variables: Mapping[str, set[str]],
) -> list[PictureReference]:
    references: list[PictureReference] = []
    for match in _COMMAND_RE.finditer(text):
        command = match.group(1)
        argument_count, image_index = _COMMAND_ARGUMENTS[command]
        parsed = _arguments(text, match.end(), argument_count)
        if parsed is None:
            continue
        arguments, _end = parsed
        raw_name = arguments[image_index]
        for name in _expand_name(raw_name, variables):
            references.append(
                PictureReference(name, command, source_file, text.count("\n", 0, match.start()) + 1)
            )
    for match in _ANIMATE_RE.finditer(text):
        parsed = _arguments(text, match.end(), 4)
        if parsed is None:
            continue
        arguments, _end = parsed
        prefix, first, last = arguments[1], arguments[2], arguments[3]
        if first.strip().lstrip("-").isdigit() and last.strip().lstrip("-").isdigit():
            start, stop = int(first), int(last)
            if 0 <= stop - start <= 500:
                for frame in range(start, stop + 1):
                    references.append(
                        PictureReference(
                            f"{prefix}{frame}",
                            "animategraphics",
                            source_file,
                            text.count("\n", 0, match.start()) + 1,
                        )
                    )
    return references


def extract_references(text: str, source_file: str) -> tuple[list[PictureReference], list[dict[str, object]]]:
    active = _strip_comments_and_tail(text)
    variables = _literal_variable_values(active)
    macro_references, spans = _newcommand_expansions(active)
    masked = list(active)
    for start, end in spans:
        masked[start:end] = [
            "\n" if character == "\n" else " " for character in active[start:end]
        ]
    references = _extract_direct("".join(masked), source_file, variables=variables)
    references.extend(
        PictureReference(name, command, source_file, active.count("\n", 0, offset) + 1)
        for name, command, offset in macro_references
    )
    dynamics: list[dict[str, object]] = []
    for match in _COMMAND_RE.finditer("".join(masked)):
        command = match.group(1)
        parsed = _arguments(active, match.end(), _COMMAND_ARGUMENTS[command][0])
        if parsed is None:
            continue
        raw_name = parsed[0][_COMMAND_ARGUMENTS[command][1]]
        if ("\\" in raw_name or "#" in raw_name) and not _expand_name(raw_name, variables):
            dynamics.append(
                {
                    "sourceFile": source_file,
                    "line": active.count("\n", 0, match.start()) + 1,
                    "command": command,
                    "expression": raw_name,
                }
            )
    unique = list(dict.fromkeys(references))
    return unique, dynamics


def _rg_tex_files(archives: Sequence[Path]) -> list[Path]:
    command = ["rg", "--follow", "--files", "-0", "-g", "*.tex", *map(str, archives)]
    result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in {0, 1}:
        raise PictureBankError("ripgrep could not enumerate the archive corpus")
    return sorted(Path(item.decode()) for item in result.stdout.split(b"\0") if item)


def _bank_index(bank: Path) -> tuple[dict[str, list[Path]], list[Path]]:
    files = sorted(path for path in bank.rglob("*") if path.is_file())
    index: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        relative = unicodedata.normalize("NFC", path.relative_to(bank).as_posix())
        index[relative.casefold()].append(path)
    return index, files


def _candidate_names(logical_name: str, command: str) -> list[str]:
    value = unicodedata.normalize("NFC", logical_name.strip().replace("\\", "/"))
    while value.startswith("./"):
        value = value[2:]
    names = [value]
    if value.casefold().startswith("pictures/"):
        names.append(value[len("pictures/") :])
    if command == "picturer":
        names.extend(re.sub(r"\.([0-9]+)$", r"-\1", item) for item in tuple(names))
    expanded: list[str] = []
    for name in names:
        suffix = PurePosixPath(name).suffix
        if suffix:
            expanded.append(name)
        else:
            expanded.extend(f"{name}.{extension}" for extension in FIGURE_EXTENSION_PRIORITY)
    return list(dict.fromkeys(expanded))


def _sniff_kind(path: Path) -> str:
    prefix = path.read_bytes()[:4096]
    stripped = prefix.lstrip()
    if prefix.startswith(b"%PDF-"):
        return "pdf"
    if stripped.startswith((b"<svg", b"<?xml")) and b"<svg" in stripped:
        return "svg"
    if prefix.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF8", b"RIFF")):
        return "raster"
    if path.suffix.casefold() in _RASTER_SUFFIXES:
        return "raster"
    if path.suffix.casefold() == ".svg":
        return "svg"
    if path.suffix.casefold() == ".pdf":
        return "pdf"
    return "unsupported"


def _pdf_pages(path: Path) -> int | None:
    result = subprocess.run(
        ["pdfinfo", str(path)], check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    if result.returncode != 0:
        return None
    match = re.search(br"^Pages:\s*([0-9]+)\s*$", result.stdout, re.MULTILINE)
    return None if match is None else int(match.group(1))


def scan_picture_bank(archives: Sequence[Path], bank: Path) -> dict[str, object]:
    tex_files = _rg_tex_files(archives)
    index, bank_files = _bank_index(bank)
    references: list[PictureReference] = []
    dynamic: list[dict[str, object]] = []
    encodings: dict[str, int] = defaultdict(int)
    decode_errors: list[dict[str, str]] = []
    for source in tex_files:
        try:
            text, encoding = decode_tex(source.read_bytes())
            encodings[encoding] += 1
            found, unresolved = extract_references(text, str(source))
            references.extend(found)
            dynamic.extend(unresolved)
        except (OSError, UnicodeError) as error:
            decode_errors.append({"sourceFile": str(source), "error": type(error).__name__})

    found_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    used_files: set[Path] = set()
    grouped_aliases: dict[Path, set[str]] = defaultdict(set)
    grouped_occurrences: dict[Path, list[dict[str, object]]] = defaultdict(list)
    for reference in references:
        selected: Path | None = None
        for candidate in _candidate_names(reference.logical_name, reference.command):
            matches = index.get(candidate.casefold(), [])
            if len(matches) > 1:
                conflicts.append(
                    {**asdict(reference), "candidate": candidate, "files": [str(path) for path in matches]}
                )
                selected = None
                break
            if matches:
                selected = matches[0]
                break
        if selected is None:
            missing_rows.append(asdict(reference))
            continue
        used_files.add(selected)
        grouped_aliases[selected].add(reference.logical_name)
        grouped_aliases[selected].add(selected.relative_to(bank).as_posix())
        occurrence = asdict(reference)
        occurrence["bankFile"] = str(selected)
        found_rows.append(occurrence)
        grouped_occurrences[selected].append(occurrence)

    imports: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for path in sorted(grouped_aliases):
        kind = _sniff_kind(path)
        reason: str | None = None
        if kind == "unsupported":
            reason = "unsupported_format"
        elif kind == "pdf":
            pages = _pdf_pages(path)
            if pages is None:
                reason = "pdf_page_count_unavailable"
            elif pages != 1:
                reason = f"multipage_pdf:{pages}"
        row = {
            "bankFile": str(path),
            "logicalNames": sorted(grouped_aliases[path], key=str.casefold),
            "sourceKind": kind,
            "occurrences": grouped_occurrences[path],
        }
        if reason is None:
            imports.append(row)
        else:
            skipped.append({**row, "reason": reason})

    unique_logical = {reference.logical_name.casefold() for reference in references}
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "archives": [str(path) for path in archives],
        "bank": str(bank),
        "stats": {
            "texFiles": len(tex_files),
            "encodings": dict(sorted(encodings.items())),
            "references": len(references),
            "uniqueLogicalNames": len(unique_logical),
            "matchedOccurrences": len(found_rows),
            "missingOccurrences": len(missing_rows),
            "importFiles": len(imports),
            "skippedFiles": len(skipped),
            "unusedBankFiles": len(set(bank_files) - used_files),
            "dynamicExpressions": len(dynamic),
            "conflicts": len(conflicts),
        },
        "imports": imports,
        "missing": missing_rows,
        "dynamic": dynamic,
        "conflicts": conflicts,
        "skipped": skipped,
        "decodeErrors": decode_errors,
        "unused": [str(path) for path in sorted(set(bank_files) - used_files)],
    }


def _tool_config() -> object:
    return SimpleNamespace(
        pdflatex_path=os.environ.get("VMSH_PDFLATEX_PATH", "pdflatex"),
        pdf2svg_path=os.environ.get("VMSH_PDF2SVG_PATH", "pdf2svg"),
        magick_path=os.environ.get("VMSH_MAGICK_PATH", "magick"),
        cwebp_path=os.environ.get("VMSH_CWEBP_PATH", "cwebp"),
    )


async def apply_picture_bank(
    report: dict[str, object],
    *,
    database: Path,
    runtime_profile: str,
    media_root: Path,
    actor_user_id: int | None,
) -> None:
    if runtime_profile == "pwa-production" and os.environ.get(PRODUCTION_OPT_IN) != "true":
        raise PictureBankError(f"production import requires {PRODUCTION_OPT_IN}=true")
    factory = PwaConnectionFactory(database)
    repository = PwaContentRepository(factory)
    storage_config = load_storage_config(
        runtime_profile=runtime_profile,
        media_root=str(media_root),
        repository_root=REPOSITORY_ROOT,
    )
    service = ContentAssetService(
        converter=ConfiguredContentAssetConverter(_tool_config()),
        storage=create_object_storage(storage_config),
        repository=repository,
    )

    def legacy_rows(connection):
        return connection.execute(
            "SELECT logical_name, asset_id FROM content_revision_assets "
            "WHERE role = 'figure' ORDER BY revision_id, logical_name"
        ).fetchall()

    backfill = {"bound": 0, "reused": 0, "conflicts": []}
    for row in await factory.run_read_async(legacy_rows):
        try:
            created = await repository.bind_content_asset_name(
                logical_name=str(row["logical_name"]),
                asset_id=int(row["asset_id"]),
                origin="backfill",
                actor_user_id=actor_user_id,
            )
            backfill["bound" if created else "reused"] += 1
        except (ContentConflict, ValueError) as error:
            backfill["conflicts"].append(
                {"logicalName": str(row["logical_name"]), "error": type(error).__name__}
            )

    applied: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for item in report["imports"]:
        if not isinstance(item, dict):
            continue
        path = Path(str(item["bankFile"]))
        try:
            record, reused = await service.import_named_figure(
                logical_names=tuple(str(value) for value in item["logicalNames"]),
                payload=path.read_bytes(),
                source_kind=str(item["sourceKind"]),
                source_filename=path.name,
                actor_user_id=actor_user_id,
            )
            applied.append(
                {
                    "bankFile": str(path),
                    "assetId": record.public_id,
                    "reused": reused,
                    "logicalNameCount": len(item["logicalNames"]),
                }
            )
        except Exception as error:  # one bad legacy file must not hide the rest
            failures.append({"bankFile": str(path), "error": type(error).__name__})

    def revision_rows(connection):
        return [
            (str(row["public_id"]), str(row["status"]))
            for row in connection.execute(
                "SELECT public_id, status FROM content_revisions ORDER BY id"
            ).fetchall()
        ]

    resolver = {
        "revisions": 0,
        "attachments": 0,
        "tikzBackfilled": 0,
        "tikzConflicts": [],
        "failures": [],
    }
    for revision_public_id, revision_status in await factory.run_read_async(
        revision_rows
    ):
        try:
            context = await repository.get_revision_context(revision_public_id)
            encoding = "cp1251" if context.source.source_encoding == "cp1251" else "utf-8"
            prefix = (
                b"\xef\xbb\xbf"
                if encoding == "utf-8"
                and context.revision.provenance.get("sourceHadUtf8Bom") is True
                else b""
            )
            payload = prefix + context.revision.latex_text.encode(encoding)
            result = compile_latex(
                payload,
                source_name=context.source.logical_filename,
                role=ContentRole(context.source.kind.value),
                revision_id=context.revision.public_id,
            )
            ast = json.loads(canonical_json(result.ast))
            stack = [ast]
            discovered: list[dict[str, object]] = []
            while stack:
                current = stack.pop()
                if isinstance(current, dict):
                    if current.get("kind") in {"asset", "tikz"} and isinstance(
                        current.get("logical_name"), str
                    ):
                        discovered.append(current)
                    stack.extend(current.values())
                elif isinstance(current, list):
                    stack.extend(current)
            attachments = await repository.list_revision_assets(
                revision_id=context.revision.id
            )
            attached = {record.logical_name for record in attachments}
            attachment_by_name = {record.logical_name: record for record in attachments}
            version = context.revision.version
            created = 0
            ordered: list[dict[str, object]] = []
            seen_names: set[str] = set()
            for reference in sorted(
                discovered,
                key=lambda item: (
                    int(
                        item.get("span", {}).get("start", {}).get("offset", 0)
                        if isinstance(item.get("span"), dict)
                        and isinstance(item.get("span", {}).get("start"), dict)
                        else 0
                    ),
                    str(item["logical_name"]),
                ),
            ):
                name = str(reference["logical_name"])
                if name not in seen_names:
                    seen_names.add(name)
                    ordered.append(reference)
            for ordinal, reference in enumerate(ordered):
                logical_name = str(reference["logical_name"])
                if reference["kind"] == "tikz" and logical_name in attachment_by_name:
                    source = reference.get("tikz_source")
                    attachment = attachment_by_name[logical_name]
                    if isinstance(source, str):
                        winner = await repository.cache_tikz_asset(
                            normalized_sha256=tikz_source_sha256(source),
                            normalization_version=TIKZ_NORMALIZATION_VERSION,
                            conversion_version=attachment.asset.conversion_version,
                            source_sha256=hashlib.sha256(source.strip().encode("utf-8")).hexdigest(),
                            asset_id=attachment.asset.id,
                            actor_user_id=actor_user_id,
                        )
                        if winner.id == attachment.asset.id:
                            resolver["tikzBackfilled"] += 1
                        else:
                            resolver["tikzConflicts"].append(
                                {"revisionId": revision_public_id, "logicalName": logical_name}
                            )
                if logical_name in attached:
                    continue
                if revision_status != "uploaded":
                    continue
                common = {
                    "revision_id": context.revision.id,
                    "logical_name": logical_name,
                    "expected_revision_version": version,
                    "ordinal": ordinal,
                    "alt_text": (
                        str(reference["alt_text"])
                        if isinstance(reference.get("alt_text"), str)
                        else None
                    ),
                }
                if reference["kind"] == "tikz":
                    source = reference.get("tikz_source")
                    persisted = (
                        None
                        if not isinstance(source, str)
                        else await service.resolve_and_attach_tikz(**common, source=source)
                    )
                else:
                    persisted = await service.resolve_and_attach_figure(**common)
                if persisted is not None and persisted.revision_version is not None:
                    version = persisted.revision_version
                    attached.add(logical_name)
                    created += 1
            resolver["revisions"] += 1
            resolver["attachments"] += created
        except Exception as error:
            resolver["failures"].append(
                {"revisionId": revision_public_id, "error": type(error).__name__}
            )
    report["apply"] = {
        "backfill": backfill,
        "assets": applied,
        "count": len(applied),
        "failures": failures,
        "resolver": resolver,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("scan", "dry-run", "apply"))
    parser.add_argument("--archive", action="append", type=Path, dest="archives")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--runtime-profile", default="pwa-agent")
    parser.add_argument("--media-root", type=Path, default=REPOSITORY_ROOT / ".runtime/vmshpwa/media")
    parser.add_argument("--actor-user-id", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    archives = tuple(arguments.archives or DEFAULT_ARCHIVES)
    report = scan_picture_bank(archives, arguments.bank)
    if arguments.mode == "apply":
        if arguments.database is None:
            raise PictureBankError("apply requires --database")
        asyncio.run(
            apply_picture_bank(
                report,
                database=arguments.database,
                runtime_profile=arguments.runtime_profile,
                media_root=arguments.media_root,
                actor_user_id=arguments.actor_user_id,
            )
        )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["stats"], ensure_ascii=False, sort_keys=True))
    print(f"report={arguments.report}")
    apply_result = report.get("apply")
    if isinstance(apply_result, dict) and apply_result.get("failures"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

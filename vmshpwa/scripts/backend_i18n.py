"""Extract and check the PWA backend translation catalog.

Russian literals are catalog keys (see ``helpers/pwa/i18n.py``). Extraction
scans the PWA backend for Russian string literals passed to ``N_()`` / ``_()``
and to ``PwaApiError(message=...)`` (the error middleware translates those),
then rewrites ``helpers/pwa/locales/en.po`` keeping existing translations.

``check`` fails when the catalog is stale, when a message used by a translated
scope (``backend`` globs in ``vmshpwa/i18n-scopes.json``) has no English, or
when such a scope builds a message dynamically (f-string, concatenation,
``.format``) instead of passing ``params``: a built string never matches a key.

Run through ``make pwa-i18n-extract`` / ``make pwa-i18n-check``.
See ``vmshpwa/docs/i18n.md``.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from babel.messages.pofile import read_po

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (
    "apps/pwa_app.py",
    "apps/pwa_api",
    "helpers/pwa",
    "models/pwa",
    "db_methods/pwa",
)
CATALOG_PATH = REPOSITORY_ROOT / "helpers" / "pwa" / "locales" / "en.po"
SCOPES_PATH = REPOSITORY_ROOT / "vmshpwa" / "i18n-scopes.json"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
MARKER_FUNCTIONS = frozenset({"N_", "_"})
CATALOG_HEADER = (
    "# PWA backend messages. The Russian msgid is the source text and the key\n"
    "# (helpers/pwa/i18n.py). Regenerate with `make pwa-i18n-extract`; edit only msgstr.\n"
    'msgid ""\n'
    'msgstr ""\n'
    '"Content-Type: text/plain; charset=utf-8\\n"\n'
    '"Language: en\\n"\n'
)


@dataclass(frozen=True, slots=True)
class DynamicMessage:
    origin: str
    line: int
    kind: str


@dataclass(slots=True)
class Extraction:
    messages: dict[str, set[str]]
    dynamic: list[DynamicMessage]


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _message_argument(node: ast.Call) -> ast.expr | None:
    name = _call_name(node.func)
    if name in MARKER_FUNCTIONS:
        return node.args[0] if node.args else None
    if name == "PwaApiError":
        return next(
            (keyword.value for keyword in node.keywords if keyword.arg == "message"),
            None,
        )
    return None


def _dynamic_kind(argument: ast.expr) -> str | None:
    if isinstance(argument, ast.JoinedStr):
        return "f-string"
    if isinstance(argument, ast.BinOp):
        return "concatenation"
    if isinstance(argument, ast.Call) and _call_name(argument.func) == "format":
        return ".format()"
    return None


def python_sources(root: Path = REPOSITORY_ROOT) -> list[Path]:
    files: list[Path] = []
    for entry in SOURCE_ROOTS:
        path = root / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                file for file in path.rglob("*.py") if "__pycache__" not in file.parts
            )
    return sorted(files)


def extract(files: Iterable[Path], root: Path = REPOSITORY_ROOT) -> Extraction:
    messages: dict[str, set[str]] = {}
    dynamic: list[DynamicMessage] = []
    for file in files:
        origin = file.relative_to(root).as_posix()
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=origin)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            argument = _message_argument(node)
            if argument is None:
                continue
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                if CYRILLIC.search(argument.value):
                    messages.setdefault(argument.value, set()).add(origin)
                continue
            kind = _dynamic_kind(argument)
            if kind is not None:
                dynamic.append(DynamicMessage(origin, argument.lineno, kind))
    return Extraction(messages, dynamic)


def read_translations(path: Path = CATALOG_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        catalog = read_po(file, locale="en")
    return {
        message.id: message.string or ""
        for message in catalog
        if message.id and isinstance(message.id, str)
    }


def _po_string(keyword: str, value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    lines = escaped.split("\n")
    if len(lines) == 1:
        return f'{keyword} "{escaped}"\n'
    parts = [f"{line}\\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    return f'{keyword} ""\n' + "".join(f'"{part}"\n' for part in parts)


def render_catalog(
    messages: Mapping[str, set[str]], translations: Mapping[str, str]
) -> str:
    entries = [CATALOG_HEADER]
    for message in sorted(messages):
        origins = "".join(f"#: {origin}\n" for origin in sorted(messages[message]))
        entries.append(
            origins
            + _po_string("msgid", message)
            + _po_string("msgstr", translations.get(message, ""))
        )
    return "\n".join(entries)


def load_scopes(path: Path = SCOPES_PATH) -> list[str]:
    return list(json.loads(path.read_text(encoding="utf-8")).get("backend", []))


def _in_scope(origin: str, scopes: Iterable[str]) -> bool:
    return any(PurePosixPath(origin).full_match(glob) for glob in scopes)


def check(
    extraction: Extraction,
    *,
    catalog_text: str,
    translations: Mapping[str, str],
    scopes: list[str],
) -> list[str]:
    problems: list[str] = []
    if catalog_text != render_catalog(extraction.messages, translations):
        problems.append(
            "helpers/pwa/locales/en.po is out of sync with the code; run `make pwa-i18n-extract`."
        )
    untranslated = sorted(
        f"{origin}: {message!r}"
        for message, origins in extraction.messages.items()
        if not translations.get(message)
        for origin in sorted(origins)
        if _in_scope(origin, scopes)
    )
    if untranslated:
        problems.append(
            f"{len(untranslated)} backend message(s) in translated scopes have no English:\n  "
            + "\n  ".join(untranslated)
        )
    dynamic = [
        f"{item.origin}:{item.line} builds a message with {item.kind}; pass params instead"
        for item in extraction.dynamic
        if _in_scope(item.origin, scopes)
    ]
    if dynamic:
        problems.append("\n".join(dynamic))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("extract", "check"))
    arguments = parser.parse_args(argv)

    extraction = extract(python_sources())
    translations = read_translations()
    if arguments.command == "extract":
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_PATH.write_text(
            render_catalog(extraction.messages, translations), encoding="utf-8"
        )
        missing = sum(
            1 for message in extraction.messages if not translations.get(message)
        )
        print(
            f"Backend catalog: {len(extraction.messages)} messages, {missing} without English, "
            f"{len(extraction.dynamic)} dynamic message(s) outside the catalog."
        )
        return 0

    catalog_text = (
        CATALOG_PATH.read_text(encoding="utf-8") if CATALOG_PATH.exists() else ""
    )
    problems = check(
        extraction,
        catalog_text=catalog_text,
        translations=translations,
        scopes=load_scopes(),
    )
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 1
    print("Backend i18n catalog: in sync, translated scopes covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

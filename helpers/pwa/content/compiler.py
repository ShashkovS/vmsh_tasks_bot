"""Side-effect-free entry point for the PWA LaTeX content compiler."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from pathlib import PurePosixPath

from .model import (
    CompileResult,
    ContentDerivative,
    ContentRole,
    Diagnostic,
    ast_sha256,
    canonical_json,
    sha256_text,
)
from .parser import LatexAstParser
from .renderers import (
    TELEGRAM_RENDERER_VERSION,
    WEB_RENDERER_VERSION,
    is_safe_media_url,
    render_telegram_rich_html,
    render_web_html,
)
from .scanner import (
    ParserLimits,
    SourceMap,
    decode_source,
    is_escaped,
    normalize_asset_reference,
    read_command,
    skip_comment,
    syntax_diagnostic,
)
from .telegram import TelegramMarkupError
from .web_document import (
    WebAssetDescriptor,
    WebDocumentError,
    render_web_document,
    validate_web_asset_descriptor,
)


COMPILER_VERSION = "vmsh-latex-compiler/5"
_MAX_KNOWN_ASSETS = 20_000
_FORBIDDEN_TEX_COMMANDS = {
    "catcode",
    "csname",
    "directlua",
    "include",
    "input",
    "luaexec",
    "newread",
    "newwrite",
    "openin",
    "openout",
    "read",
    "special",
    "write",
}


class ContentCompileError(ValueError):
    """Raised before parsing when the immutable source envelope is invalid."""


def _normalized_assets(
    assets: Mapping[str, WebAssetDescriptor] | None,
) -> tuple[Mapping[str, str] | None, Mapping[str, WebAssetDescriptor]]:
    if assets is None:
        return None, {}
    if len(assets) > _MAX_KNOWN_ASSETS:
        raise ContentCompileError(
            f"known_assets exceeds {_MAX_KNOWN_ASSETS} descriptors"
        )
    hashes: dict[str, str] = {}
    descriptors: dict[str, WebAssetDescriptor] = {}
    for raw_name, descriptor in assets.items():
        if not isinstance(raw_name, str):
            raise ContentCompileError("Invalid logical asset name")
        name = normalize_asset_reference(raw_name)
        if name is None or len(name) > 2_000:
            raise ContentCompileError("Invalid logical asset name")
        try:
            validate_web_asset_descriptor(descriptor)
        except WebDocumentError as error:
            raise ContentCompileError(
                f"Invalid published descriptor for logical asset {name!r}: {error}"
            ) from error
        existing = descriptors.get(name)
        if existing is not None and existing != descriptor:
            raise ContentCompileError(
                f"Conflicting published descriptors for logical asset {name!r}"
            )
        hashes[name] = descriptor.content_sha256
        descriptors[name] = descriptor
    return hashes, descriptors


def _normalized_urls(
    urls: Mapping[str, str] | None,
) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    accepted: dict[str, str] = {}
    rejected: list[tuple[str, str]] = []
    for raw_name, raw_url in (urls or {}).items():
        name = normalize_asset_reference(raw_name)
        if name is None or not is_safe_media_url(raw_url):
            rejected.append((raw_name, raw_url))
            continue
        accepted[name] = raw_url
    return accepted, tuple(rejected)


def _forbidden_command_diagnostics(
    text: str, source_map: SourceMap
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    cursor = 0
    end = len(text)
    while cursor < end:
        if text[cursor] == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        command = read_command(text, cursor, end)
        if command is None:
            cursor += 1
            continue
        if command.name in _FORBIDDEN_TEX_COMMANDS:
            diagnostics.append(
                syntax_diagnostic(
                    code="latex.command_forbidden",
                    message=(
                        f"Команда \\{command.name} запрещена в загружаемом content source."
                    ),
                    source_map=source_map,
                    start=command.start,
                    end=command.end,
                    recovery="Удалите файловый, динамический или output-примитив из source.",
                )
            )
        cursor = command.end
    return diagnostics


def compile_latex(
    payload: bytes,
    *,
    source_name: str,
    role: ContentRole,
    known_assets: Mapping[str, WebAssetDescriptor] | None = None,
    asset_urls: Mapping[str, str] | None = None,
    limits: ParserLimits | None = None,
    revision_id: str | None = None,
    title: str | None = None,
) -> CompileResult:
    """Compile bytes into typed AST and deterministic, side-effect-free derivatives.

    ``role`` is mandatory so a condition derivative can never accidentally
    include an answer or solution present in a legacy combined TeX file.
    Asset bytes and converter execution belong to later fixed-toolchain stages.
    """

    parser_limits = limits or ParserLimits()
    if not isinstance(payload, bytes):
        raise ContentCompileError("LaTeX payload must be immutable bytes")
    source_path = PurePosixPath(source_name)
    if (
        not source_name
        or len(source_name) > 240
        or source_name != source_path.as_posix()
        or source_name != unicodedata.normalize("NFKC", source_name)
        or source_path.is_absolute()
        or not source_path.name
        or any(part in {"", ".", ".."} for part in source_path.parts)
        or "\\" in source_name
        or any(
            ord(character) < 32 or ord(character) == 127 for character in source_name
        )
    ):
        raise ContentCompileError(
            "source_name must be a bounded, relative logical path without controls"
        )
    if not isinstance(role, ContentRole):
        raise ContentCompileError("role must be an explicit ContentRole")
    try:
        source = decode_source(
            payload,
            source_name=source_name,
            limits=parser_limits,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ContentCompileError(str(error)) from error

    normalized_asset_hashes, normalized_asset_descriptors = _normalized_assets(
        known_assets
    )
    normalized_urls, rejected_urls = _normalized_urls(asset_urls)
    parser = LatexAstParser(
        source_name=source.source_name,
        source_sha256=source.raw_sha256,
        source_encoding=source.encoding,
        text=source.text,
        limits=parser_limits,
        known_assets=normalized_asset_hashes,
    )
    document = parser.parse()
    diagnostics = list(parser.diagnostics)
    diagnostics.extend(_forbidden_command_diagnostics(source.text, parser.source_map))
    for logical_name, _url in rejected_urls:
        diagnostics.append(
            syntax_diagnostic(
                code="asset.url_unsafe",
                message="URL производного asset использует запрещённую схему или authority.",
                source_map=parser.source_map,
                start=0,
                end=min(1, len(source.text)),
                recovery=f"Исправьте URL mapping для логического asset {logical_name!r}.",
            )
        )

    for logical_name, descriptor in normalized_asset_descriptors.items():
        previous_url = normalized_urls.get(logical_name)
        if previous_url is not None and previous_url != descriptor.src:
            diagnostics.append(
                syntax_diagnostic(
                    code="asset.url_conflict",
                    message=(
                        "URL производного asset расходится с опубликованным "
                        "typed descriptor."
                    ),
                    source_map=parser.source_map,
                    start=0,
                    end=min(1, len(source.text)),
                    recovery=(
                        "Используйте один опубликованный descriptor для web и Telegram."
                    ),
                )
            )
        # The descriptor is the single source of truth for every derivative.
        normalized_urls[logical_name] = descriptor.src

    web_content = render_web_html(
        document,
        role=role,
        asset_urls=normalized_urls,
    )
    web_document: ContentDerivative | None = None
    if role is not ContentRole.FULL_PREVIEW:
        try:
            web_document_content = canonical_json(
                render_web_document(
                    document,
                    role=role,
                    revision_id=revision_id,
                    title=title,
                    assets=normalized_asset_descriptors,
                )
            )
        except WebDocumentError as error:
            diagnostics.append(
                syntax_diagnostic(
                    code="web.derivative_invalid",
                    message=f"WebContentDocument v1 не прошёл contract boundary: {error}",
                    source_map=parser.source_map,
                    start=0,
                    end=len(source.text),
                    recovery="Исправьте AST adapter; публикация такого derivative запрещена.",
                )
            )
        else:
            web_document = ContentDerivative(
                kind="web_content_document",
                renderer_version="vmsh-web-content-document/2",
                content=web_document_content,
                sha256=sha256_text(web_document_content),
            )
    try:
        telegram_content = render_telegram_rich_html(
            document,
            role=role,
            asset_urls=normalized_urls,
        )
    except (TelegramMarkupError, ValueError) as error:
        diagnostics.append(
            syntax_diagnostic(
                code="telegram.derivative_invalid",
                message=(
                    "Telegram Rich derivative не прошёл allowlist/limits-проверку: "
                    f"{error}"
                ),
                source_map=parser.source_map,
                start=0,
                end=len(source.text),
                recovery="Исправьте AST renderer; отправка такого derivative запрещена.",
            )
        )
        telegram_content = ""

    diagnostics.sort(
        key=lambda diagnostic: (
            diagnostic.span.start.offset,
            diagnostic.code,
            diagnostic.message,
        )
    )
    return CompileResult(
        source=source,
        role=role,
        ast=document,
        diagnostics=tuple(diagnostics),
        ast_sha256=ast_sha256(document),
        web_document=web_document,
        web=ContentDerivative(
            kind="web_html",
            renderer_version=WEB_RENDERER_VERSION,
            content=web_content,
            sha256=sha256_text(web_content),
        ),
        telegram=ContentDerivative(
            kind="telegram_html",
            renderer_version=TELEGRAM_RENDERER_VERSION,
            content=telegram_content,
            sha256=sha256_text(telegram_content),
        ),
    )

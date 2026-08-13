"""Bounded external-tool pipeline for Phase-2 content assets.

The compiler only discovers figures and TikZ sources.  This module owns the
separate, fixed-argv conversion boundary described in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.  It never
uses a shell, never keeps the uploaded original, and returns immutable bytes
that can be stored through :mod:`helpers.object_storage`.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from helpers.pwa.toolchain import resolve_executable, run_fixed_command


_SVG_NAMESPACE: Final = "http://www.w3.org/2000/svg"
_XLINK_NAMESPACE: Final = "http://www.w3.org/1999/xlink"
_MAX_TIKZ_CHARACTERS: Final = 250_000
_MAX_RASTER_INPUT_BYTES: Final = 25 * 1024 * 1024
_MAX_SVG_BYTES: Final = 8 * 1024 * 1024
_MAX_WEBP_BYTES: Final = 20 * 1024 * 1024
_MAX_SVG_NODES: Final = 100_000
_MAX_ATTRIBUTE_CHARACTERS: Final = 65_536
_MAX_DIMENSION: Final = 20_000
_OUTPUT_MAX_SIDE: Final = 1_920

_FORBIDDEN_TEX_COMMAND = re.compile(
    r"\\(?:"
    r"catcode|csname|directlua|documentclass|everyjob|include|includeonly|input|"
    r"immediate|newread|newwrite|openin|openout|read|requirepackage|special|"
    r"usepackage|write|write18"
    r")\b",
    flags=re.IGNORECASE,
)
_FORBIDDEN_TEX_PRIMITIVE = re.compile(
    r"\\(?:pdf|luatex|shellescap|sys|file|primitive)[A-Za-z@]*",
    flags=re.IGNORECASE,
)
_SAFE_SVG_ELEMENTS = frozenset(
    {
        "circle",
        "clipPath",
        "defs",
        "desc",
        "ellipse",
        "g",
        "line",
        "linearGradient",
        "marker",
        "mask",
        "path",
        "pattern",
        "polygon",
        "polyline",
        "radialGradient",
        "rect",
        "stop",
        "svg",
        "symbol",
        "text",
        "title",
        "tspan",
        "use",
    }
)
_SAFE_SVG_ATTRIBUTES = frozenset(
    {
        "class",
        "clip-path",
        "clip-rule",
        "cx",
        "cy",
        "d",
        "display",
        "dominant-baseline",
        "dx",
        "dy",
        "fill",
        "fill-opacity",
        "fill-rule",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "gradientTransform",
        "gradientUnits",
        "height",
        "id",
        "marker-end",
        "marker-mid",
        "marker-start",
        "mask",
        "offset",
        "opacity",
        "orient",
        "overflow",
        "pathLength",
        "patternContentUnits",
        "patternTransform",
        "patternUnits",
        "points",
        "preserveAspectRatio",
        "r",
        "refX",
        "refY",
        "rx",
        "ry",
        "spreadMethod",
        "stop-color",
        "stop-opacity",
        "stroke",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-width",
        "text-anchor",
        "transform",
        "vector-effect",
        "version",
        "viewBox",
        "width",
        "x",
        "x1",
        "x2",
        "y",
        "y1",
        "y2",
        "xmlns",
    }
)
_SAFE_STYLE_PROPERTIES = frozenset(
    {
        "clip-rule",
        "fill",
        "fill-opacity",
        "fill-rule",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "opacity",
        "stop-color",
        "stop-opacity",
        "stroke",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-width",
        "text-anchor",
    }
)
_LOCAL_FRAGMENT = re.compile(r"#[A-Za-z_][A-Za-z0-9_.:-]*")
_LOCAL_URL = re.compile(r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)")


class AssetConversionError(RuntimeError):
    """A redacted conversion failure safe for API diagnostics."""

    def __init__(self, code: str, capability: str, detail: str) -> None:
        self.code = code
        self.capability = capability
        self.detail = detail
        super().__init__(f"{capability}: {detail}")


@dataclass(frozen=True)
class ConvertedAsset:
    source_sha256: str
    output_sha256: str
    media_type: str
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class ContentAssetTools:
    pdflatex: str
    pdf2svg: str
    magick: str
    cwebp: str

    @classmethod
    def from_config(
        cls, config: object, *, path: str | None = None
    ) -> "ContentAssetTools":
        resolved: dict[str, str] = {}
        for field in ("pdflatex_path", "pdf2svg_path", "magick_path", "cwebp_path"):
            configured = getattr(config, field, None)
            executable = resolve_executable(configured, path=path)
            if executable is None:
                raise AssetConversionError(
                    "asset.tool_unavailable",
                    field,
                    "configured executable is disabled, missing or not executable",
                )
            resolved[field] = executable
        return cls(
            pdflatex=resolved["pdflatex_path"],
            pdf2svg=resolved["pdf2svg_path"],
            magick=resolved["magick_path"],
            cwebp=resolved["cwebp_path"],
        )


def _configured_tool(config: object, field: str) -> str:
    executable = resolve_executable(getattr(config, field, None))
    if executable is None:
        raise AssetConversionError(
            "asset.tool_unavailable",
            field,
            "configured executable is disabled, missing or not executable",
        )
    return executable


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_environment(temp_directory: Path) -> dict[str, str]:
    """Return a narrow converter environment without changing process globals."""

    inherited_path = os.environ.get("PATH")
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MAGICK_TMPDIR": str(temp_directory),
        "TMPDIR": str(temp_directory),
        "openin_any": "p",
        "openout_any": "p",
        "shell_escape": "f",
    }
    if inherited_path:
        environment["PATH"] = inherited_path
    for identity_name in ("HOME", "USER", "LOGNAME"):
        identity_value = os.environ.get(identity_name)
        if identity_value:
            environment[identity_name] = identity_value
    return environment


def _assert_command_succeeded(
    *, capability: str, return_code: int, output_path: Path, maximum_bytes: int
) -> bytes:
    if return_code != 0:
        raise AssetConversionError(
            "asset.converter_failed",
            capability,
            f"converter exited with code {return_code}",
        )
    try:
        data = output_path.read_bytes()
    except FileNotFoundError as error:
        raise AssetConversionError(
            "asset.output_missing", capability, "converter did not create output"
        ) from error
    if not data:
        raise AssetConversionError(
            "asset.output_empty", capability, "converter output is empty"
        )
    if len(data) > maximum_bytes:
        raise AssetConversionError(
            "asset.output_too_large",
            capability,
            "converter output exceeds the configured limit",
        )
    return data


def _validate_tikz_source(source: str) -> str:
    if not isinstance(source, str):
        raise TypeError("TikZ source must be text")
    normalized = source.strip()
    if not normalized:
        raise AssetConversionError(
            "asset.tikz_empty", "latex-to-pdf", "TikZ source is empty"
        )
    if len(normalized) > _MAX_TIKZ_CHARACTERS:
        raise AssetConversionError(
            "asset.tikz_too_large",
            "latex-to-pdf",
            "TikZ source exceeds 250000 characters",
        )
    if _FORBIDDEN_TEX_COMMAND.search(normalized) or _FORBIDDEN_TEX_PRIMITIVE.search(
        normalized
    ):
        raise AssetConversionError(
            "asset.tikz_forbidden_command",
            "latex-to-pdf",
            "TikZ source contains a file, dynamic or output primitive",
        )
    if "\\begin{document}" in normalized or "\\end{document}" in normalized:
        raise AssetConversionError(
            "asset.tikz_document_boundary",
            "latex-to-pdf",
            "TikZ source must not define a document boundary",
        )
    return normalized


def _standalone_document(tikz_source: str) -> str:
    return (
        "\\documentclass[tikz,border=5pt]{standalone}\n"
        "\\usepackage{amsmath}\n"
        "\\usepackage{tkz-euclide}\n"
        "\\usetikzlibrary{angles,arrows.meta,backgrounds,calc,decorations.markings,"
        "decorations.pathmorphing,decorations.pathreplacing,intersections,matrix,patterns,"
        "quotes,shapes.geometric,through}\n"
        "\\begin{document}\n"
        f"{tikz_source}\n"
        "\\end{document}\n"
    )


def prepare_tikz_standalone_document(source: str) -> str:
    """Validate TikZ and assemble the exact TeX input without executing tools."""

    return _standalone_document(_validate_tikz_source(source))


def _split_svg_name(name: str) -> tuple[str | None, str]:
    if name.startswith("{"):
        namespace, _, local_name = name[1:].partition("}")
        return namespace, local_name
    return None, name


def _sanitize_style(value: str) -> str:
    declarations: list[str] = []
    for declaration in value.split(";"):
        declaration = declaration.strip()
        if not declaration:
            continue
        property_name, separator, property_value = declaration.partition(":")
        property_name = property_name.strip().casefold()
        property_value = property_value.strip()
        if (
            separator != ":"
            or property_name not in _SAFE_STYLE_PROPERTIES
            or not property_value
            or "url(" in property_value.casefold()
            or "expression" in property_value.casefold()
            or any(ord(character) < 32 for character in property_value)
        ):
            raise AssetConversionError(
                "asset.svg_unsafe_style",
                "svg-sanitizer",
                "SVG style is outside the allowlist",
            )
        declarations.append(f"{property_name}:{property_value}")
    return ";".join(declarations)


def _safe_paint_or_reference(value: str) -> bool:
    lowered = value.casefold()
    if "url(" not in lowered:
        return not any(token in lowered for token in ("javascript:", "data:", "http:"))
    return _LOCAL_URL.fullmatch(value.strip()) is not None


def sanitize_svg(svg: bytes) -> bytes:
    """Fail closed to a presentation-only SVG subset and canonical bytes."""

    if not isinstance(svg, bytes):
        raise TypeError("SVG payload must be bytes")
    if not svg or len(svg) > _MAX_SVG_BYTES:
        raise AssetConversionError(
            "asset.svg_size",
            "svg-sanitizer",
            "SVG is empty or exceeds the configured limit",
        )
    lowered_prefix = svg[:16_384].lower()
    if (
        b"<!doctype" in lowered_prefix
        or b"<!entity" in lowered_prefix
        or b"<?xml-stylesheet" in lowered_prefix
    ):
        raise AssetConversionError(
            "asset.svg_declaration",
            "svg-sanitizer",
            "SVG contains a forbidden declaration",
        )
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as error:
        raise AssetConversionError(
            "asset.svg_invalid", "svg-sanitizer", "SVG is not well-formed XML"
        ) from error

    namespace, root_name = _split_svg_name(root.tag)
    if namespace != _SVG_NAMESPACE or root_name != "svg":
        raise AssetConversionError(
            "asset.svg_root", "svg-sanitizer", "SVG root or namespace is invalid"
        )

    node_count = 0
    for element in root.iter():
        node_count += 1
        if node_count > _MAX_SVG_NODES:
            raise AssetConversionError(
                "asset.svg_nodes", "svg-sanitizer", "SVG contains too many nodes"
            )
        element_namespace, element_name = _split_svg_name(element.tag)
        if (
            element_namespace != _SVG_NAMESPACE
            or element_name not in _SAFE_SVG_ELEMENTS
        ):
            raise AssetConversionError(
                "asset.svg_element",
                "svg-sanitizer",
                "SVG contains an unsupported element",
            )
        normalized_attributes: dict[str, str] = {}
        for raw_name, value in element.attrib.items():
            attribute_namespace, attribute_name = _split_svg_name(raw_name)
            if attribute_namespace not in {None, _XLINK_NAMESPACE}:
                raise AssetConversionError(
                    "asset.svg_attribute",
                    "svg-sanitizer",
                    "SVG attribute namespace is invalid",
                )
            if len(value) > _MAX_ATTRIBUTE_CHARACTERS or any(
                ord(character) < 32 and character not in "\t\n\r" for character in value
            ):
                raise AssetConversionError(
                    "asset.svg_attribute", "svg-sanitizer", "SVG attribute is invalid"
                )
            if attribute_name == "style":
                normalized_attributes["style"] = _sanitize_style(value)
                continue
            if attribute_namespace == _XLINK_NAMESPACE or attribute_name == "href":
                if element_name != "use" or _LOCAL_FRAGMENT.fullmatch(value) is None:
                    raise AssetConversionError(
                        "asset.svg_external_reference",
                        "svg-sanitizer",
                        "SVG references must stay inside the document",
                    )
                normalized_attributes[f"{{{_XLINK_NAMESPACE}}}href"] = value
                continue
            if (
                attribute_name.casefold().startswith("on")
                or attribute_name not in _SAFE_SVG_ATTRIBUTES
            ):
                raise AssetConversionError(
                    "asset.svg_attribute",
                    "svg-sanitizer",
                    "SVG contains an unsupported attribute",
                )
            if attribute_name in {
                "clip-path",
                "fill",
                "marker-end",
                "marker-mid",
                "marker-start",
                "mask",
                "stroke",
            } and not _safe_paint_or_reference(value):
                raise AssetConversionError(
                    "asset.svg_external_reference",
                    "svg-sanitizer",
                    "SVG paint or reference is unsafe",
                )
            normalized_attributes[attribute_name] = value
        element.attrib.clear()
        element.attrib.update(sorted(normalized_attributes.items()))

    ElementTree.register_namespace("", _SVG_NAMESPACE)
    ElementTree.register_namespace("xlink", _XLINK_NAMESPACE)
    sanitized = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(sanitized) > _MAX_SVG_BYTES:
        raise AssetConversionError(
            "asset.svg_size",
            "svg-sanitizer",
            "Sanitized SVG exceeds the configured limit",
        )
    return sanitized


def _svg_dimensions(svg: bytes) -> tuple[int, int]:
    root = ElementTree.fromstring(svg)
    view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(view_box) == 4:
        try:
            width = round(abs(float(view_box[2])))
            height = round(abs(float(view_box[3])))
        except ValueError:
            width = height = 0
        if 1 <= width <= _MAX_DIMENSION and 1 <= height <= _MAX_DIMENSION:
            return width, height
    raise AssetConversionError(
        "asset.svg_dimensions",
        "svg-sanitizer",
        "SVG requires a bounded numeric viewBox",
    )


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise AssetConversionError(
            "asset.webp_invalid", "raster-to-webp", "converter output is not WebP"
        )
    kind = data[12:16]
    if kind == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
    elif kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        packed = int.from_bytes(data[21:25], "little")
        width = (packed & 0x3FFF) + 1
        height = ((packed >> 14) & 0x3FFF) + 1
    elif kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
    else:
        raise AssetConversionError(
            "asset.webp_invalid", "raster-to-webp", "WebP dimensions are unavailable"
        )
    if not 1 <= width <= _OUTPUT_MAX_SIDE or not 1 <= height <= _OUTPUT_MAX_SIDE:
        raise AssetConversionError(
            "asset.webp_dimensions",
            "raster-to-webp",
            "WebP dimensions exceed the 1920-pixel output boundary",
        )
    return width, height


class ContentAssetConverter:
    def __init__(
        self,
        tools: ContentAssetTools,
        *,
        temp_root: str | Path | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.tools = tools
        self.temp_root = Path(temp_root) if temp_root is not None else None
        self.timeout_seconds = timeout_seconds

    async def _run(
        self,
        *,
        capability: str,
        executable: str,
        args: Sequence[str],
        cwd: Path,
        environment: Mapping[str, str],
    ):
        try:
            return await run_fixed_command(
                executable,
                args,
                timeout_seconds=self.timeout_seconds,
                cwd=cwd,
                environment=environment,
            )
        except TimeoutError as error:
            raise AssetConversionError(
                "asset.converter_timeout",
                capability,
                "converter exceeded the configured timeout",
            ) from error
        except OSError as error:
            raise AssetConversionError(
                "asset.converter_start_failed",
                capability,
                "converter could not be started",
            ) from error

    async def tikz_to_svg(self, source: str) -> ConvertedAsset:
        normalized_source = _validate_tikz_source(source)
        source_bytes = normalized_source.encode("utf-8")
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            directory = Path(temporary)
            tex_path = directory / "content.tex"
            pdf_path = directory / "content.pdf"
            svg_path = directory / "content.svg"
            tex_path.write_text(
                prepare_tikz_standalone_document(normalized_source), encoding="utf-8"
            )
            environment = _safe_environment(directory)
            latex_result = await self._run(
                capability="latex-to-pdf",
                executable=self.tools.pdflatex,
                args=(
                    "-no-shell-escape",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-file-line-error",
                    f"-output-directory={directory}",
                    tex_path.name,
                ),
                cwd=directory,
                environment=environment,
            )
            _assert_command_succeeded(
                capability="latex-to-pdf",
                return_code=latex_result.return_code,
                output_path=pdf_path,
                maximum_bytes=32 * 1024 * 1024,
            )
            svg_result = await self._run(
                capability="pdf-to-svg",
                executable=self.tools.pdf2svg,
                args=(str(pdf_path), str(svg_path), "1"),
                cwd=directory,
                environment=environment,
            )
            raw_svg = _assert_command_succeeded(
                capability="pdf-to-svg",
                return_code=svg_result.return_code,
                output_path=svg_path,
                maximum_bytes=_MAX_SVG_BYTES,
            )
        sanitized_svg = sanitize_svg(raw_svg)
        width, height = _svg_dimensions(sanitized_svg)
        return ConvertedAsset(
            source_sha256=_sha256(source_bytes),
            output_sha256=_sha256(sanitized_svg),
            media_type="image/svg+xml",
            data=sanitized_svg,
            width=width,
            height=height,
        )

    async def svg_to_svg(self, payload: bytes) -> ConvertedAsset:
        """Sanitize an uploaded SVG through the same presentation allowlist.

        Direct SVG uploads deliberately do not enter ImageMagick: keeping the
        vector is useful for mathematical figures, while ``sanitize_svg``
        rejects scripts, external references and unsupported XML before the
        bytes can become public.
        """

        sanitized_svg = sanitize_svg(payload)
        width, height = _svg_dimensions(sanitized_svg)
        return ConvertedAsset(
            source_sha256=_sha256(payload),
            output_sha256=_sha256(sanitized_svg),
            media_type="image/svg+xml",
            data=sanitized_svg,
            width=width,
            height=height,
        )

    async def pdf_to_svg(self, payload: bytes) -> ConvertedAsset:
        """Convert the first page of a caller-validated single-page PDF."""

        if not isinstance(payload, bytes):
            raise TypeError("PDF payload must be bytes")
        if not payload.startswith(b"%PDF-") or len(payload) > 32 * 1024 * 1024:
            raise AssetConversionError(
                "asset.pdf_size", "pdf-to-svg", "PDF is invalid or exceeds 32 MiB"
            )
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            directory = Path(temporary)
            pdf_path = directory / "content.pdf"
            svg_path = directory / "content.svg"
            pdf_path.write_bytes(payload)
            result = await self._run(
                capability="pdf-to-svg",
                executable=self.tools.pdf2svg,
                args=(str(pdf_path), str(svg_path), "1"),
                cwd=directory,
                environment=_safe_environment(directory),
            )
            raw_svg = _assert_command_succeeded(
                capability="pdf-to-svg",
                return_code=result.return_code,
                output_path=svg_path,
                maximum_bytes=_MAX_SVG_BYTES,
            )
        sanitized_svg = sanitize_svg(raw_svg)
        width, height = _svg_dimensions(sanitized_svg)
        return ConvertedAsset(
            source_sha256=_sha256(payload),
            output_sha256=_sha256(sanitized_svg),
            media_type="image/svg+xml",
            data=sanitized_svg,
            width=width,
            height=height,
        )

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        if not isinstance(payload, bytes):
            raise TypeError("Raster payload must be bytes")
        if not payload or len(payload) > _MAX_RASTER_INPUT_BYTES:
            raise AssetConversionError(
                "asset.raster_size",
                "image-normalization",
                "Raster input is empty or exceeds 25 MiB",
            )
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            directory = Path(temporary)
            input_path = directory / "input.bin"
            normalized_path = directory / "normalized.png"
            webp_path = directory / "output.webp"
            input_path.write_bytes(payload)
            environment = _safe_environment(directory)
            normalize_result = await self._run(
                capability="image-normalization",
                executable=self.tools.magick,
                args=(
                    "-limit",
                    "memory",
                    "256MiB",
                    "-limit",
                    "map",
                    "512MiB",
                    "-limit",
                    "disk",
                    "1GiB",
                    str(input_path),
                    "-auto-orient",
                    "-strip",
                    "-resize",
                    f"{_OUTPUT_MAX_SIDE}x{_OUTPUT_MAX_SIDE}>",
                    str(normalized_path),
                ),
                cwd=directory,
                environment=environment,
            )
            _assert_command_succeeded(
                capability="image-normalization",
                return_code=normalize_result.return_code,
                output_path=normalized_path,
                maximum_bytes=64 * 1024 * 1024,
            )
            webp_result = await self._run(
                capability="raster-to-webp",
                executable=self.tools.cwebp,
                args=(
                    "-quiet",
                    "-q",
                    "82",
                    "-metadata",
                    "none",
                    str(normalized_path),
                    "-o",
                    str(webp_path),
                ),
                cwd=directory,
                environment=environment,
            )
            webp = _assert_command_succeeded(
                capability="raster-to-webp",
                return_code=webp_result.return_code,
                output_path=webp_path,
                maximum_bytes=_MAX_WEBP_BYTES,
            )
        width, height = _webp_dimensions(webp)
        return ConvertedAsset(
            source_sha256=_sha256(payload),
            output_sha256=_sha256(webp),
            media_type="image/webp",
            data=webp,
            width=width,
            height=height,
        )


class ConfiguredContentAssetConverter:
    """Resolve optional external tools only when conversion is requested.

    PWA health, auth, reading and realtime must start even on a process that
    does not perform Staff asset conversion. The upload endpoint still fails
    closed with ``asset.tool_unavailable`` when the configured toolchain is
    genuinely needed and unavailable.
    """

    def __init__(self, config: object) -> None:
        self._config = config

    async def tikz_to_svg(self, source: str) -> ConvertedAsset:
        converter = ContentAssetConverter(
            ContentAssetTools(
                pdflatex=_configured_tool(self._config, "pdflatex_path"),
                pdf2svg=_configured_tool(self._config, "pdf2svg_path"),
                magick="",
                cwebp="",
            )
        )
        return await converter.tikz_to_svg(source)

    async def svg_to_svg(self, payload: bytes) -> ConvertedAsset:
        converter = ContentAssetConverter(ContentAssetTools("", "", "", ""))
        return await converter.svg_to_svg(payload)

    async def pdf_to_svg(self, payload: bytes) -> ConvertedAsset:
        converter = ContentAssetConverter(
            ContentAssetTools(
                pdflatex="",
                pdf2svg=_configured_tool(self._config, "pdf2svg_path"),
                magick="",
                cwebp="",
            )
        )
        return await converter.pdf_to_svg(payload)

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        converter = ContentAssetConverter(
            ContentAssetTools(
                pdflatex="",
                pdf2svg="",
                magick=_configured_tool(self._config, "magick_path"),
                cwebp=_configured_tool(self._config, "cwebp_path"),
            )
        )
        return await converter.raster_to_webp(payload)

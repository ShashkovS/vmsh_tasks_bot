"""Reproducible, bounded PDF derivative boundary for complete LaTeX sources.

The Phase-2 contract lives in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.  This adapter accepts
only a source that first passes the pure content compiler, resolves and probes
one configured ``pdflatex`` executable, and then runs a fixed argv without a
shell in an isolated temporary directory.  Printing and print-pack assembly
deliberately remain outside this module.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from helpers.pwa.toolchain import (
    ToolProbe,
    ToolSpec,
    ToolStatus,
    probe_tool,
    run_fixed_command,
)

from .compiler import COMPILER_VERSION, compile_latex
from .model import ContentRole


PDF_RENDERER_VERSION: Final = "vmsh-content-pdf/1"
PDF_SOURCE_DATE_EPOCH: Final = "1767225600"
PDF_TOOL_SPEC: Final = ToolSpec(
    capability="content-pdf",
    config_field="pdflatex_path",
    version_args=("-version",),
)

_MAX_PDF_BYTES: Final = 64 * 1024 * 1024
_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_.-])(?:/[A-Za-z0-9_.+@~-]+){2,}")


class PdfDerivativeError(RuntimeError):
    """A stable and redacted PDF diagnostic safe for an API response."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class PdfToolCapability:
    """A ready, already-probed executable plus redacted provenance."""

    executable_name: str
    version: str
    _resolved_path: str = field(repr=False, compare=False)

    def public_dict(self) -> dict[str, str]:
        return {
            "capability": PDF_TOOL_SPEC.capability,
            "configField": PDF_TOOL_SPEC.config_field,
            "status": ToolStatus.READY.value,
            "executable": self.executable_name,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class PdfDerivative:
    source_sha256: str
    output_sha256: str
    media_type: str
    data: bytes
    provenance: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PdfCapabilityProbe:
    status: ToolStatus
    executable_name: str | None
    version: str | None
    diagnostic: str | None
    _resolved_path: str | None = field(default=None, repr=False, compare=False)

    def public_dict(self) -> dict[str, str | None]:
        return {
            "capability": PDF_TOOL_SPEC.capability,
            "configField": PDF_TOOL_SPEC.config_field,
            "status": self.status.value,
            "executable": self.executable_name,
            "version": self.version,
            "diagnostic": self.diagnostic,
        }


def _normalized_version(probe: ToolProbe) -> str:
    value = " ".join((probe.version or "version not reported").split())[:256]
    if probe.resolved_path:
        value = value.replace(probe.resolved_path, "[executable]")
    value = _ABSOLUTE_PATH.sub("[path]", value)
    return value or "version not reported"


async def probe_pdf_tool(
    config: object,
    *,
    path: str | None = None,
    timeout_seconds: float = 5.0,
) -> PdfCapabilityProbe:
    """Probe only the configured content-PDF capability, without rendering."""

    raw_probe = await probe_tool(
        PDF_TOOL_SPEC,
        getattr(config, PDF_TOOL_SPEC.config_field, None),
        path=path,
        timeout_seconds=timeout_seconds,
    )
    return PdfCapabilityProbe(
        status=raw_probe.status,
        executable_name=raw_probe.executable_name,
        version=_normalized_version(raw_probe) if raw_probe.version else None,
        diagnostic=raw_probe.diagnostic,
        _resolved_path=raw_probe.resolved_path,
    )


async def require_pdf_tool(
    config: object,
    *,
    path: str | None = None,
    timeout_seconds: float = 5.0,
) -> PdfToolCapability:
    """Return a private executable handle only after a successful probe."""

    probe = await probe_pdf_tool(
        config,
        path=path,
        timeout_seconds=timeout_seconds,
    )
    if probe.status is not ToolStatus.READY or probe._resolved_path is None:
        raise PdfDerivativeError(
            f"pdf.tool_{probe.status.value}",
            "The configured content-PDF capability is not ready",
        )
    return PdfToolCapability(
        executable_name=probe.executable_name or "pdflatex",
        version=probe.version or "version not reported",
        _resolved_path=probe._resolved_path,
    )


def _safe_environment(directory: Path) -> dict[str, str]:
    environment = {
        "FORCE_SOURCE_DATE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "SOURCE_DATE_EPOCH": PDF_SOURCE_DATE_EPOCH,
        "TMPDIR": str(directory),
        "TZ": "UTC",
        "openin_any": "p",
        "openout_any": "p",
        "shell_escape": "f",
    }
    inherited_path = os.environ.get("PATH")
    if inherited_path:
        environment["PATH"] = inherited_path
    # MiKTeX and TeX Live may need their already-configured user package roots.
    # Inheriting identity is not repurposing it and does not expose it in output.
    for name in ("HOME", "USER", "LOGNAME"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _validate_complete_source(payload: bytes, source_name: str):
    result = compile_latex(
        payload,
        source_name=source_name,
        role=ContentRole.FULL_PREVIEW,
    )
    if result.has_errors:
        codes = sorted(
            {
                diagnostic.code
                for diagnostic in result.diagnostics
                if diagnostic.severity.value == "error"
            }
        )
        first_code = codes[0] if codes else "latex.invalid"
        raise PdfDerivativeError(
            "pdf.source_invalid",
            f"The source did not pass the content compiler ({first_code})",
        )
    if (
        result.source.text.count(r"\begin{document}") != 1
        or result.source.text.count(r"\end{document}") != 1
        or result.source.text.index(r"\begin{document}")
        >= result.source.text.index(r"\end{document}")
    ):
        raise PdfDerivativeError(
            "pdf.document_boundary",
            "A PDF derivative requires one complete LaTeX document",
        )
    return result


def _validated_pdf(path: Path, return_code: int) -> bytes:
    if return_code != 0:
        raise PdfDerivativeError(
            "pdf.converter_failed",
            f"The content-PDF converter exited with code {return_code}",
        )
    try:
        payload = path.read_bytes()
    except FileNotFoundError as error:
        raise PdfDerivativeError(
            "pdf.output_missing",
            "The content-PDF converter did not create an output",
        ) from error
    if not payload:
        raise PdfDerivativeError("pdf.output_empty", "The PDF derivative is empty")
    if len(payload) > _MAX_PDF_BYTES:
        raise PdfDerivativeError(
            "pdf.output_too_large",
            "The PDF derivative exceeds the configured limit",
        )
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-2048:]:
        raise PdfDerivativeError(
            "pdf.output_invalid",
            "The converter output is not a complete PDF",
        )
    return payload


def _deterministic_driver(source_sha256: str) -> bytes:
    """Set pdfTeX metadata/trailer inputs before loading the validated source."""

    # The source compiler rejects file/dynamic primitives in user content. This
    # one fixed local \input is generated by the adapter and can resolve only the
    # sibling source.tex under openin_any=p.
    return (
        "\\pdfinfoomitdate=1\n"
        "\\pdfsuppressptexinfo=15\n"
        f"\\pdftrailerid{{[<{source_sha256}><{source_sha256}>]}}\n"
        "\\input{source.tex}\n"
    ).encode("ascii")


class PdfDerivativeRenderer:
    """Render complete compiler-approved LaTeX into an immutable PDF."""

    def __init__(
        self,
        capability: PdfToolCapability,
        *,
        temp_root: str | Path | None = None,
        timeout_seconds: float = 45.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.capability = capability
        self.temp_root = Path(temp_root) if temp_root is not None else None
        self.timeout_seconds = timeout_seconds

    @classmethod
    async def from_config(
        cls,
        config: object,
        *,
        path: str | None = None,
        temp_root: str | Path | None = None,
        probe_timeout_seconds: float = 5.0,
        timeout_seconds: float = 45.0,
    ) -> "PdfDerivativeRenderer":
        capability = await require_pdf_tool(
            config,
            path=path,
            timeout_seconds=probe_timeout_seconds,
        )
        return cls(
            capability,
            temp_root=temp_root,
            timeout_seconds=timeout_seconds,
        )

    async def render(self, payload: bytes, *, source_name: str) -> PdfDerivative:
        compile_result = _validate_complete_source(payload, source_name)
        with tempfile.TemporaryDirectory(
            prefix="vmsh-content-pdf-",
            dir=self.temp_root,
        ) as temporary:
            directory = Path(temporary)
            source_path = directory / "source.tex"
            driver_path = directory / "content.tex"
            output_path = directory / "content.pdf"
            source_path.write_bytes(payload)
            driver_path.write_bytes(
                _deterministic_driver(compile_result.source.raw_sha256)
            )
            try:
                command = await run_fixed_command(
                    self.capability._resolved_path,
                    (
                        "-no-shell-escape",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        "-recorder",
                        "-jobname=content",
                        "-output-directory=.",
                        driver_path.name,
                    ),
                    cwd=directory,
                    environment=_safe_environment(directory),
                    timeout_seconds=self.timeout_seconds,
                )
            except TimeoutError as error:
                raise PdfDerivativeError(
                    "pdf.converter_timeout",
                    "The content-PDF converter exceeded the configured timeout",
                ) from error
            except OSError as error:
                raise PdfDerivativeError(
                    "pdf.converter_start_failed",
                    "The content-PDF converter could not be started",
                ) from error
            pdf = _validated_pdf(output_path, command.return_code)

        output_sha256 = hashlib.sha256(pdf).hexdigest()
        provenance: Mapping[str, object] = {
            "compilerVersion": COMPILER_VERSION,
            "rendererVersion": PDF_RENDERER_VERSION,
            "sourceEncoding": compile_result.source.encoding.value,
            "sourceSha256": compile_result.source.raw_sha256,
            "sourceDateEpoch": PDF_SOURCE_DATE_EPOCH,
            "tool": self.capability.public_dict(),
            "toolProfile": "pdflatex-no-shell-escape-v1",
            "reproducibilityProfile": "source-date-and-trailer-id-v1",
        }
        return PdfDerivative(
            source_sha256=compile_result.source.raw_sha256,
            output_sha256=output_sha256,
            media_type="application/pdf",
            data=pdf,
            provenance=provenance,
        )

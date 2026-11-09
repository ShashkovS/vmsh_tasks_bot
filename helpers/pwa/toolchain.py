"""Resolve and probe the fixed external converter toolchain safely.

The contract is documented in ``vmshpwa/docs/latex-content-pipeline.md``.
Configuration selects one executable per capability; callers, not user input,
own the argv.  This module therefore never invokes a shell.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ToolStatus(StrEnum):
    READY = "ready"
    DISABLED = "disabled"
    MISSING = "missing"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ToolSpec:
    capability: str
    config_field: str
    version_args: tuple[str, ...]
    accepted_return_codes: frozenset[int] | None = frozenset({0})


@dataclass(frozen=True)
class CommandResult:
    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ToolProbe:
    capability: str
    config_field: str
    status: ToolStatus
    executable_name: str | None = None
    version: str | None = None
    diagnostic: str | None = None
    resolved_path: str | None = field(default=None, repr=False, compare=False)

    def public_dict(self) -> dict[str, str | None]:
        """Return a report safe for logs, health checks and committed proofs."""

        return {
            "capability": self.capability,
            "configField": self.config_field,
            "status": self.status.value,
            "executable": self.executable_name,
            "version": self.version,
            "diagnostic": self.diagnostic,
        }


DEFAULT_TOOL_SPECS = (
    # pdf2svg has no portable version flag. Invoking it without operands emits
    # usage and a platform-specific non-zero code, which still proves that the
    # configured executable can start; the conversion smoke proves behavior.
    ToolSpec("pdf-to-svg", "pdf2svg_path", (), None),
    ToolSpec("raster-to-webp", "cwebp_path", ("-version",)),
    ToolSpec("latex-to-pdf", "pdflatex_path", ("-version",)),
    ToolSpec("image-normalization", "magick_path", ("-version",)),
)


def resolve_executable(
    configured: str | None, *, path: str | None = None
) -> str | None:
    """Resolve an executable name/path with the process profile's PATH."""

    if configured is None:
        return None
    if not isinstance(configured, str):
        raise TypeError("Executable configuration must be a string or None")
    if not configured or configured != configured.strip() or "\0" in configured:
        raise ValueError("Executable configuration must be one non-empty path")
    return shutil.which(configured, mode=os.F_OK | os.X_OK, path=path)


def _limited_text(data: bytes, limit: int) -> str:
    if len(data) > limit:
        data = data[-limit:]
        prefix = "[truncated]\n"
    else:
        prefix = ""
    return prefix + data.decode("utf-8", errors="replace").strip()


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    # Converter programs can spawn helpers. A private process group prevents a
    # timed-out child from surviving and writing into an already-cleaned tempdir.
    if os.name == "posix":
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    else:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    with contextlib.suppress(ProcessLookupError):
        await process.wait()


async def run_fixed_command(
    executable: str,
    args: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    output_limit: int = 8_192,
) -> CommandResult:
    """Run a trusted argv without a shell and with bounded output/lifetime."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if output_limit <= 0:
        raise ValueError("output_limit must be positive")

    process = await asyncio.create_subprocess_exec(
        executable,
        *args,
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
    except TimeoutError:
        await _terminate_process(process)
        raise

    return CommandResult(
        return_code=process.returncode or 0,
        stdout=_limited_text(stdout, output_limit),
        stderr=_limited_text(stderr, output_limit),
    )


def _version_line(result: CommandResult) -> str | None:
    for line in (*result.stdout.splitlines(), *result.stderr.splitlines()):
        normalized = " ".join(line.split())
        if normalized:
            return normalized[:256]
    return None


async def probe_tool(
    spec: ToolSpec,
    configured: str | None,
    *,
    path: str | None = None,
    timeout_seconds: float = 5.0,
) -> ToolProbe:
    if configured is None:
        return ToolProbe(spec.capability, spec.config_field, ToolStatus.DISABLED)

    try:
        resolved = resolve_executable(configured, path=path)
    except (TypeError, ValueError) as error:
        return ToolProbe(
            spec.capability,
            spec.config_field,
            ToolStatus.FAILED,
            diagnostic=str(error),
        )
    if resolved is None:
        return ToolProbe(
            spec.capability,
            spec.config_field,
            ToolStatus.MISSING,
            executable_name=Path(configured).name,
            diagnostic="configured executable was not found or is not executable",
        )

    executable_name = Path(resolved).name
    try:
        result = await run_fixed_command(
            resolved,
            spec.version_args,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError:
        return ToolProbe(
            spec.capability,
            spec.config_field,
            ToolStatus.TIMEOUT,
            executable_name=executable_name,
            diagnostic="capability probe timed out",
            resolved_path=resolved,
        )
    except OSError:
        return ToolProbe(
            spec.capability,
            spec.config_field,
            ToolStatus.FAILED,
            executable_name=executable_name,
            diagnostic="capability probe could not start",
            resolved_path=resolved,
        )

    version = _version_line(result)
    if (
        spec.accepted_return_codes is not None
        and result.return_code not in spec.accepted_return_codes
    ):
        return ToolProbe(
            spec.capability,
            spec.config_field,
            ToolStatus.FAILED,
            executable_name=executable_name,
            version=version,
            diagnostic=f"version probe exited with code {result.return_code}",
            resolved_path=resolved,
        )
    return ToolProbe(
        spec.capability,
        spec.config_field,
        ToolStatus.READY,
        executable_name=executable_name,
        version=version,
        resolved_path=resolved,
    )


async def probe_toolchain(
    config: object,
    *,
    specs: Sequence[ToolSpec] = DEFAULT_TOOL_SPECS,
    path: str | None = None,
    timeout_seconds: float = 10.0,
) -> tuple[ToolProbe, ...]:
    return tuple(
        await asyncio.gather(
            *(
                probe_tool(
                    spec,
                    getattr(config, spec.config_field),
                    path=path,
                    timeout_seconds=timeout_seconds,
                )
                for spec in specs
            )
        )
    )


def toolchain_ready(probes: Sequence[ToolProbe]) -> bool:
    return bool(probes) and all(probe.status is ToolStatus.READY for probe in probes)

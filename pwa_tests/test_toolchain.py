import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers.config import Config, _optional_executable_from_env
from helpers.pwa.toolchain import (
    ToolSpec,
    ToolStatus,
    probe_tool,
    probe_toolchain,
    resolve_executable,
    run_fixed_command,
    toolchain_ready,
)
from vmshpwa.scripts.toolchain_preflight import toolchain_preflight

TEST_PROCESS_TIMEOUT_SECONDS = 5


def _executable(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_config_has_portable_tool_defaults_and_explicit_disable(monkeypatch):
    config = Config()
    assert (
        config.pdf2svg_path,
        config.cwebp_path,
        config.pdflatex_path,
        config.magick_path,
    ) == ("pdf2svg", "cwebp", "pdflatex", "magick")

    monkeypatch.setenv("TEST_TOOL_PATH", " disabled ")
    assert _optional_executable_from_env("TEST_TOOL_PATH", "fallback") is None
    monkeypatch.setenv("TEST_TOOL_PATH", "/opt/tools/example")
    assert _optional_executable_from_env("TEST_TOOL_PATH", "fallback") == (
        "/opt/tools/example"
    )


def test_pwa_profile_reads_tool_overrides_without_legacy_credentials(tmp_path):
    environment = os.environ.copy()
    environment.update(
        {
            "VMSH_RUNTIME_PROFILE": "pwa-agent",
            "VMSH_PDFLATEX_PATH": str(tmp_path / "custom-pdflatex"),
            "VMSH_CWEBP_PATH": "disabled",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from helpers.config import config; "
            "print(config.pdflatex_path); print(config.cwebp_path)",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [str(tmp_path / "custom-pdflatex"), "None"]
    assert "гугл-креды" not in result.stderr


def test_resolve_executable_uses_supplied_path_and_rejects_ambiguous_values(tmp_path):
    executable = _executable(tmp_path, "converter", "print('ok')")
    assert resolve_executable("converter", path=str(tmp_path)) == str(executable)
    assert resolve_executable(None, path=str(tmp_path)) is None

    for invalid in ("", " converter", "converter ", "converter\0flag"):
        with pytest.raises(ValueError):
            resolve_executable(invalid, path=str(tmp_path))


@pytest.mark.asyncio
async def test_fixed_command_does_not_interpolate_shell_and_bounds_output(tmp_path):
    marker = tmp_path / "must-not-exist"
    executable = _executable(
        tmp_path,
        "argv-printer",
        "import sys\nprint(sys.argv[1])\nprint('x' * 200, file=sys.stderr)",
    )
    shell_like_argument = ";touch must-not-exist"

    result = await run_fixed_command(
        str(executable),
        [shell_like_argument],
        # Eight xdist workers can delay process startup on a busy laptop.  This
        # test checks argv/output handling, not the timeout boundary below.
        timeout_seconds=TEST_PROCESS_TIMEOUT_SECONDS,
        cwd=tmp_path,
        output_limit=32,
    )

    assert result.stdout == shell_like_argument
    assert result.stderr.startswith("[truncated]\n")
    assert len(result.stderr) <= 45
    assert not marker.exists()


@pytest.mark.asyncio
async def test_probe_matrix_reports_ready_disabled_missing_failure_and_timeout(
    tmp_path,
):
    ready = _executable(tmp_path, "ready", "print('Converter 2.4')")
    failed = _executable(tmp_path, "failed", "raise SystemExit(7)")
    slow = _executable(tmp_path, "slow", "import time\ntime.sleep(5)")
    spec = ToolSpec("test", "test_path", ("--version",))

    ready_probe = await probe_tool(
        spec, str(ready), timeout_seconds=TEST_PROCESS_TIMEOUT_SECONDS
    )
    disabled_probe = await probe_tool(
        spec, None, timeout_seconds=TEST_PROCESS_TIMEOUT_SECONDS
    )
    missing_probe = await probe_tool(
        spec,
        "does-not-exist",
        path=str(tmp_path),
        timeout_seconds=TEST_PROCESS_TIMEOUT_SECONDS,
    )
    failed_probe = await probe_tool(
        spec, str(failed), timeout_seconds=TEST_PROCESS_TIMEOUT_SECONDS
    )
    # This is the only branch whose purpose is to exercise the short timeout.
    timeout_probe = await probe_tool(spec, str(slow), timeout_seconds=0.05)

    assert ready_probe.status is ToolStatus.READY
    assert ready_probe.version == "Converter 2.4"
    assert ready_probe.resolved_path == str(ready)
    assert ready_probe.resolved_path not in str(ready_probe.public_dict())
    assert disabled_probe.status is ToolStatus.DISABLED
    assert missing_probe.status is ToolStatus.MISSING
    assert failed_probe.status is ToolStatus.FAILED
    assert failed_probe.diagnostic == "version probe exited with code 7"
    assert timeout_probe.status is ToolStatus.TIMEOUT


@pytest.mark.asyncio
async def test_toolchain_preflight_is_redacted_and_requires_every_tool(tmp_path):
    executable = _executable(tmp_path, "converter", "print('Synthetic 1.0')")
    config = SimpleNamespace(
        runtime_profile="pwa-agent",
        pdf2svg_path=str(executable),
        cwebp_path=str(executable),
        pdflatex_path=str(executable),
        magick_path=str(executable),
    )

    # Process startup may briefly exceed one second when the full suite runs in
    # eight xdist workers; this test checks readiness/redaction, not a 1 s SLA.
    probes = await probe_toolchain(config, timeout_seconds=5)
    report, ready = await toolchain_preflight(config)

    assert toolchain_ready(probes)
    assert ready is True
    assert report["profile"] == "pwa-agent"
    assert all(tool["status"] == "ready" for tool in report["tools"])
    assert str(tmp_path) not in str(report)

    config.cwebp_path = None
    report, ready = await toolchain_preflight(config)
    assert ready is False
    assert report["tools"][1]["status"] == "disabled"


def test_configured_path_is_not_added_to_process_path(tmp_path):
    executable = _executable(tmp_path, "isolated-converter", "print('ok')")
    inherited_path = os.environ.get("PATH", "")
    assert resolve_executable(executable.name, path=inherited_path) is None

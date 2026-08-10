"""Fail-closed structural preflight for the rendered production PWA unit."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
from pathlib import Path


MARKER = re.compile(r"@@[A-Z0-9_]+@@")
ENVIRONMENT_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
REQUIRED_ENVIRONMENT = frozenset(
    {
        "VMSH_PWA_TRUSTED_PROXY_HOPS",
        "VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON",
    }
)
FORBIDDEN_ENVIRONMENT = frozenset(
    {
        "PROD",
        "VMSH_RUNTIME_PROFILE",
        "VMSH_PWA_PROTOTYPE",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "TELEGRAM_BOT_TOKEN",
    }
)


class SystemdProfileError(ValueError):
    """Rendered systemd profile is incomplete or weakens the PWA boundary."""


def _regular_private_file(path: Path) -> str:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise SystemdProfileError("PWA environment file is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise SystemdProfileError("PWA environment file must be one regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise SystemdProfileError("PWA environment file must have mode 0600")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemdProfileError("PWA environment file cannot be read") from error


def _environment(source: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not ENVIRONMENT_NAME.fullmatch(name):
            raise SystemdProfileError(
                f"PWA environment line {number} is not canonical KEY=value"
            )
        if name in values:
            raise SystemdProfileError(f"PWA environment repeats {name}")
        if not value or "\x00" in value or "\n" in value:
            raise SystemdProfileError(f"PWA environment value {name} is empty")
        values[name] = value
    missing = sorted(REQUIRED_ENVIRONMENT - values.keys())
    if missing:
        raise SystemdProfileError(
            "PWA environment is incomplete: " + ", ".join(missing)
        )
    forbidden = sorted(FORBIDDEN_ENVIRONMENT & values.keys())
    if forbidden:
        raise SystemdProfileError(
            "PWA environment must not select adapters/profile: " + ", ".join(forbidden)
        )
    return values


def _json_array(value: str, *, field: str) -> list[object]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise SystemdProfileError(f"{field} is not valid JSON") from error
    if not isinstance(payload, list):
        raise SystemdProfileError(f"{field} must be a JSON array")
    return payload


def _validate_environment(values: dict[str, str]) -> None:
    sockets = _json_array(
        values["VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON"],
        field="VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON",
    )
    if (
        len(sockets) != 1
        or not isinstance(sockets[0], str)
        or not Path(sockets[0]).is_absolute()
    ):
        raise SystemdProfileError(
            "PWA trusted proxy must name one absolute Unix socket"
        )
    if values["VMSH_PWA_TRUSTED_PROXY_HOPS"] != "1":
        raise SystemdProfileError("PWA production proxy hop count must be one")


def _validate_unit(source: str, *, env_file: Path) -> None:
    if MARKER.search(source):
        raise SystemdProfileError("PWA systemd unit contains unresolved markers")
    required_fragments = (
        "[Service]",
        f"EnvironmentFile={env_file}",
        "ExecStart=/usr/bin/env VMSH_RUNTIME_PROFILE=pwa-production "
        "VMSH_PWA_PROTOTYPE=false ",
        "--workers 2",
        "--worker-class uvloop_worker.GunicornUVLoopWebWorkerFixed",
        "--bind unix:",
        "--umask 007",
        "main:app",
        "Restart=on-failure",
        "KillSignal=SIGTERM",
        "UMask=0007",
        "NoNewPrivileges=true",
        "ProtectSystem=strict",
        "ReadWritePaths=",
    )
    missing = [item for item in required_fragments if item not in source]
    if missing:
        raise SystemdProfileError(
            "PWA systemd unit is incomplete: " + ", ".join(missing)
        )
    forbidden_fragments = (
        "ExecReload=",
        "--preload",
        "--workers 1",
        "aiohttp.GunicornWebWorker",
        "telegram",
        "google",
    )
    found = [
        item for item in forbidden_fragments if item.casefold() in source.casefold()
    ]
    if found:
        raise SystemdProfileError(
            "PWA systemd unit contains a forbidden legacy/reload setting: "
            + ", ".join(found)
        )


def check_systemd_profile(
    *, unit_path: Path, env_path: Path, require_systemd_analyze: bool
) -> dict[str, object]:
    try:
        unit_source = unit_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemdProfileError("PWA systemd unit cannot be read") from error
    values = _environment(_regular_private_file(env_path))
    _validate_environment(values)
    _validate_unit(unit_source, env_file=env_path)

    analyzer = shutil.which("systemd-analyze")
    if require_systemd_analyze and analyzer is None:
        raise SystemdProfileError("systemd-analyze is required on the production host")
    analyzed = False
    if analyzer is not None:
        result = subprocess.run(
            [analyzer, "verify", str(unit_path)],
            check=False,
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0:
            raise SystemdProfileError("systemd-analyze rejected the PWA unit")
        analyzed = True
    return {
        "schemaVersion": 1,
        "profile": "pwa-production",
        "workers": 2,
        "systemdAnalyze": analyzed,
        "environmentMode": "0600",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--require-systemd-analyze", action="store_true")
    arguments = parser.parse_args()
    try:
        report = check_systemd_profile(
            unit_path=arguments.unit,
            env_path=arguments.environment,
            require_systemd_analyze=arguments.require_systemd_analyze,
        )
    except SystemdProfileError as error:
        print(f"PWA systemd profile rejected: {error}")
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

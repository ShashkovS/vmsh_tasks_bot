"""Resolve the already installed pinned pnpm without mutating dependencies."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def frontend_environment(
    workspace: Path, environment: dict[str, str]
) -> dict[str, str]:
    """Fail before a build/test if versions or installed lockfile are stale."""

    expected = json.loads((workspace / "package.json").read_text())["packageManager"]
    version = expected.removeprefix("pnpm@")
    candidates = [shutil.which("pnpm", path=environment.get("PATH"))]
    homes = [Path.home() / "Library/pnpm", Path.home() / ".local/share/pnpm"]
    if environment.get("PNPM_HOME"):
        homes.insert(0, Path(environment["PNPM_HOME"]))
    for home in homes:
        candidates.extend(
            str(path)
            for path in home.glob(
                f"package-manager-store/v*/links/@pnpm/exe/{version}/*/bin/pnpm"
            )
        )
    selected = None
    for candidate in dict.fromkeys(candidates):
        if (
            candidate
            and subprocess.check_output(
                [candidate, "--version"], env=environment, text=True
            ).strip()
            == version
        ):
            selected = candidate
            break
    if not selected:
        raise RuntimeError(
            f"Install {expected} before testing; dependencies are never reinstalled during a run"
        )
    result = {
        **environment,
        "PATH": f"{Path(selected).parent}{os.pathsep}{environment.get('PATH', '')}",
    }
    node = subprocess.check_output(["node", "--version"], env=result, text=True).strip()
    if not node.startswith("v26."):
        raise RuntimeError(f"Node 26 is required; found {node}")
    installed_lock = workspace / "node_modules/.pnpm/lock.yaml"
    if (
        not installed_lock.is_file()
        or installed_lock.read_bytes() != (workspace / "pnpm-lock.yaml").read_bytes()
    ):
        raise RuntimeError(
            "Frontend dependencies differ from pnpm-lock.yaml; run the pinned pnpm install --frozen-lockfile once before testing"
        )
    print(f"Toolchain: {node}, {expected}, installed lockfile matches", flush=True)
    result.update(VMSH_CHECK_NODE_VERSION=node, VMSH_CHECK_PNPM_VERSION=version)
    return result

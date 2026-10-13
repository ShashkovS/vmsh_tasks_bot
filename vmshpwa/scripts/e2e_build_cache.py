"""Reuse only byte-verified E2E artifacts for the same source/environment.

The caller holds e2e_runner.exclusive_e2e_run throughout lookup/build/use.
See testing-strategy.md and the check-optimization-20261003 report.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

APPLICATIONS = ("student", "family", "staff", "landing")
EXCLUDED_DIRECTORIES = {
    "node_modules",
    "dist",
    "dev-dist",
    "storybook-static",
    "playwright-report",
    "test-results",
    "dev",
    "docs",
    "e2e",
    ".storybook",
    ".git",
    "__pycache__",
}


def build_input_digest(workspace: Path, environment: dict[str, str]) -> str:
    digest = hashlib.sha256()
    inputs = {
        key: value
        for key, value in environment.items()
        if key.startswith("VITE_")
        or key
        in {
            "VMSH_API_ORIGIN",
            "VMSH_PWA_DEV_SW",
            "VMSH_FRONTEND_BUILD_PROFILE",
            "NODE_ENV",
            "VMSH_CHECK_NODE_VERSION",
            "VMSH_CHECK_PNPM_VERSION",
        }
    }
    digest.update(
        json.dumps({"version": 1, "environment": inputs}, sort_keys=True).encode()
    )
    for root, directories, filenames in os.walk(workspace):
        directories[:] = sorted(
            name for name in directories if name not in EXCLUDED_DIRECTORIES
        )
        if any((Path(root) / name).is_symlink() for name in directories):
            raise RuntimeError("Frontend source directories must not be symlinks")
        for name in sorted(filenames):
            if (
                any(marker in name for marker in (".test.", ".stories.", ".spec."))
                or name.endswith((".md", ".tsbuildinfo", ".py", ".pyc", ".log"))
                or name in {"routeTree.gen.ts", ".DS_Store"}
            ):
                continue
            if name.startswith(("playwright.", "vitest.", "eslint.", "prettier.")):
                continue
            path = Path(root) / name
            if path.is_symlink():
                raise RuntimeError("Frontend source files must not be symlinks")
            digest.update(str(path.relative_to(workspace)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def artifact_manifest(workspace: Path) -> dict[str, str]:
    files = {}
    for application in APPLICATIONS:
        root = workspace / "apps" / application / "dist"
        if root.is_symlink():
            raise RuntimeError(f"E2E bundle root must not be a symlink: {application}")
        if not (root / "index.html").is_file():
            raise ValueError(f"Missing or unsafe E2E bundle: {application}")
        provenance = json.loads((root / "build-provenance.json").read_text())
        if not (
            provenance.get("application") == application
            and provenance.get("profile") == "verification"
            and provenance.get("msw") is False
            and provenance.get("prototype") is False
            and provenance.get("publicMediaOrigin") is None
            and provenance.get("sentryConfigured") is False
        ):
            raise ValueError(f"Unsafe E2E build provenance: {application}")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("E2E artifacts must not contain symlinks")
            if path.is_file():
                files[str(path.relative_to(workspace))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return files


def cached_build_is_current(workspace: Path, environment: dict[str, str]) -> bool:
    manifest = workspace.parent / ".runtime/vmshpwa/e2e-cache/build.json"
    try:
        record = json.loads(manifest.read_text())
        return record["inputs"] == build_input_digest(
            workspace, environment
        ) and record["artifacts"] == artifact_manifest(workspace)
    except OSError, ValueError, KeyError:
        return False


def record_build(workspace: Path, environment: dict[str, str]) -> None:
    record = {
        "inputs": build_input_digest(workspace, environment),
        "artifacts": artifact_manifest(workspace),
    }
    path = workspace.parent / ".runtime/vmshpwa/e2e-cache/build.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True) + "\n")
    temporary.replace(path)

"""Package and atomically select one set of production frontend bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from vmshpwa.scripts.report_io import atomic_write_text


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = REPOSITORY_ROOT / ".runtime" / "phase11-rehearsal" / "releases"
APP_SOURCES = {
    "student": REPOSITORY_ROOT / "vmshpwa" / "apps" / "student" / "dist",
    "family": REPOSITORY_ROOT / "vmshpwa" / "apps" / "family" / "dist",
    "staff": REPOSITORY_ROOT / "vmshpwa" / "apps" / "staff" / "dist",
}
REQUIRED_FILES = {
    "student": ("index.html", "manifest.webmanifest", "sw.js"),
    "family": ("index.html", "manifest.webmanifest", "sw.js"),
    "staff": ("index.html",),
}
RELEASE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


def _validate_release_id(release_id: str) -> None:
    if not RELEASE_ID_PATTERN.fullmatch(release_id) or release_id in {".", ".."}:
        raise ValueError("Release ID must be a short lowercase revision label")


def _tree_summary(root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Release bundle contains a symlink: {path}")
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        contents = path.read_bytes()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(contents).digest())
        file_count += 1
        byte_count += len(contents)
    return {
        "files": file_count,
        "bytes": byte_count,
        "sha256": digest.hexdigest(),
    }


def package_release(
    release_id: str,
    recorded_at: str,
    *,
    sources: dict[str, Path] | None = None,
) -> dict[str, object]:
    """Copy three complete builds into a new immutable release directory."""

    _validate_release_id(release_id)
    source_directories = APP_SOURCES if sources is None else sources
    if set(source_directories) != set(REQUIRED_FILES):
        raise ValueError("Exactly the student, family and staff bundles are required")

    for app_name, required_files in REQUIRED_FILES.items():
        source = source_directories[app_name]
        if not source.is_dir():
            raise ValueError(f"Missing {app_name} production bundle")
        for relative_path in required_files:
            if not (source / relative_path).is_file():
                raise ValueError(f"Missing {app_name}/{relative_path}")

    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    destination = RELEASE_ROOT / release_id
    if destination.exists():
        raise ValueError("Release directory already exists")

    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=RELEASE_ROOT))
    try:
        applications: dict[str, object] = {}
        for app_name, source in source_directories.items():
            app_destination = staging / app_name
            shutil.copytree(source, app_destination)
            applications[app_name] = _tree_summary(app_destination)

        manifest = {
            "schemaVersion": 1,
            "releaseId": release_id,
            "recordedAt": recorded_at,
            "applications": applications,
        }
        (staging / "release.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return manifest


def activate_release(
    release_id: str, recorded_at: str, *, action: str = "activate"
) -> dict[str, object]:
    """Atomically point ``current`` at an existing release."""

    _validate_release_id(release_id)
    destination = RELEASE_ROOT / release_id
    if not destination.is_dir() or not (destination / "release.json").is_file():
        raise ValueError("Release directory is missing or incomplete")

    current = RELEASE_ROOT / "current"
    if current.exists() and not current.is_symlink():
        raise ValueError("The current release path exists and is not a symlink")
    previous_release_id = (
        current.readlink().as_posix() if current.is_symlink() else None
    )

    temporary = RELEASE_ROOT / f".current.{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("Temporary activation link already exists")
    try:
        temporary.symlink_to(release_id)
        os.replace(temporary, current)
    finally:
        temporary.unlink(missing_ok=True)

    if current.resolve() != destination.resolve():
        raise RuntimeError(
            "Activated release does not resolve to the requested directory"
        )
    return {
        "schemaVersion": 1,
        "operation": f"static-release-{action}",
        "recordedAt": recorded_at,
        "releaseId": release_id,
        "previousReleaseId": previous_release_id,
        "currentLinkTarget": current.readlink().as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("package", "activate", "rollback"))
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--recorded-at",
        default=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    arguments = parser.parse_args()

    if arguments.action == "package":
        report = package_release(arguments.release_id, arguments.recorded_at)
    else:
        report = activate_release(
            arguments.release_id,
            arguments.recorded_at,
            action=arguments.action,
        )
    atomic_write_text(
        arguments.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

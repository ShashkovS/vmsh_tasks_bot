"""Prepare fresh E2E state by copying a verified DB/media seed snapshot.

One seed process replaces thirteen Python startups. The running backend is
never reseeded: lifecycle locks still exclude it. See testing-strategy.md and
pwa_tests/reports/check-optimization-20261003/README.md.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

from db_methods.pwa import maintenance_database_lock, require_current_schema
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_runtime import _prepare_target_for_replace, seed_runtime

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "db/vmshpwa_e2e.sqlite3"
MEDIA = ROOT / ".runtime/vmshpwa/e2e"
CACHE = ROOT / ".runtime/vmshpwa/e2e-cache/seeds"
SEEDS = (
    ("seed_e2e_content", "seed_e2e_content"),
    ("seed_e2e_review", "seed_e2e_review"),
    ("seed_e2e_classrooms", "seed_e2e_classrooms"),
    ("seed_e2e_family_progress", "seed_e2e_family_progress"),
    ("seed_e2e_oral", "seed_e2e_oral"),
    ("seed_e2e_live_marking", "seed"),
    ("seed_e2e_news", "seed_e2e_news"),
    ("seed_e2e_statistics", "seed_e2e_statistics"),
    ("seed_e2e_student_results", "seed"),
    ("seed_e2e_worksheet_print", "seed"),
    ("seed_e2e_whiteboard", "seed"),
    ("seed_e2e_problem_release", "seed"),
)


def seed_digest(*, statistics: bool, support: bool) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {
                "version": 1,
                "python": sys.version,
                "sqlite": sqlite3.sqlite_version,
                "statistics": statistics,
                "support": support,
            },
            sort_keys=True,
        ).encode()
    )
    paths = [
        ROOT / "uv.lock",
        ROOT / "pyproject.toml",
        ROOT / "vmshpwa/scripts/prepare_e2e.py",
    ]
    for folder in (
        "migrations",
        "db_methods",
        "models",
        "helpers",
        "pwa_tests/fixtures",
    ):
        paths.extend(
            path
            for path in (ROOT / folder).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix
            in {".py", ".sql", ".json", ".tex", ".webp", ".png", ".svg", ".po"}
        )
    paths.extend((ROOT / "vmshpwa/scripts").glob("seed*.py"))
    paths.append(ROOT / "vmshpwa/scripts/runtime_guard.py")
    for path in sorted(set(paths)):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def snapshot_files(folder: Path) -> dict[str, str]:
    result = {}
    if folder.is_symlink():
        raise ValueError("E2E snapshot must not be a symlink")
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("E2E snapshot must not contain symlinks")
        if path.is_file() and path != folder / "manifest.json":
            result[str(path.relative_to(folder))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def snapshot_is_current(folder: Path, key: str) -> bool:
    if folder.is_symlink() or (folder / "manifest.json").is_symlink():
        raise ValueError("E2E snapshot must not be a symlink")
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
        return (
            manifest["key"] == key
            and manifest["files"] == snapshot_files(folder)
            and (folder / "database.sqlite3").is_file()
            and (folder / "media").is_dir()
        )
    except OSError, ValueError, KeyError:
        return False


def require_e2e_target(config) -> None:
    if (
        config.runtime_profile != "pwa-e2e"
        or os.environ.get("PROD", "").lower() == "true"
    ):
        raise RuntimeError("Cached seed requires the isolated pwa-e2e profile")
    if (
        Path(config.db_filename).absolute() != DATABASE
        or Path(config.pwa_media_root).absolute() != MEDIA
    ):
        raise RuntimeError("Cached seed refuses a non-E2E DB/media target")
    if any(
        path.is_symlink()
        for root in (DATABASE, MEDIA, CACHE)
        for path in (root, *root.parents)
    ):
        raise RuntimeError("Cached seed refuses symlink paths")


def _media_entries():
    # Analytics has its own lifecycle lock. Keep that lock inode permanently;
    # neither snapshots nor media cleanup own it (ADR 0002).
    return [
        path
        for path in MEDIA.iterdir()
        if not path.name.startswith("analytics.sqlite3")
        and not path.name.endswith(".vmshpwa-lifecycle.lock")
    ]


def _clear_media_and_analytics() -> None:
    analytics = MEDIA / "analytics.sqlite3"
    with maintenance_database_lock(DATABASE), maintenance_database_lock(analytics):
        _prepare_target_for_replace(DATABASE)
        _prepare_target_for_replace(analytics)
        analytics.unlink(missing_ok=True)
        for path in _media_entries():
            if path.is_symlink():
                raise RuntimeError("E2E media must not contain symlinks")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def seed_all(config, *, statistics: bool, support: bool) -> None:
    seed_runtime(config)
    for module_name, function_name in SEEDS:
        function = getattr(
            importlib.import_module(f"vmshpwa.scripts.{module_name}"), function_name
        )
        function(config)
    if statistics:
        importlib.import_module("vmshpwa.scripts.seed_e2e_statistics_reports").main()
    if support:
        importlib.import_module("vmshpwa.scripts.seed_e2e_support_navigation").main()


def _save_snapshot(folder: Path, key: str) -> None:
    folder.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(dir=folder.parent, prefix="building-"))
    try:
        target = temporary / "database.sqlite3"
        with (
            closing(sqlite3.connect(DATABASE)) as source,
            closing(sqlite3.connect(target)) as destination,
        ):
            source.backup(destination)
            destination.execute("PRAGMA journal_mode=WAL")
            destination.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        require_current_schema(target)
        # Read-only schema inspection may create empty WAL/SHM files. The
        # checkpointed snapshot owns only the main DB, not transient sidecars.
        for suffix in ("-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
        media = temporary / "media"
        media.mkdir()
        if any(path.is_symlink() for path in MEDIA.rglob("*")):
            raise RuntimeError("E2E media must not contain symlinks")
        for path in _media_entries():
            if path.is_dir():
                shutil.copytree(path, media / path.name)
            else:
                shutil.copyfile(path, media / path.name)
        # Validate paths before publishing; never cache an escaping media link.
        files = snapshot_files(temporary)
        (temporary / "manifest.json").write_text(
            json.dumps({"key": key, "files": files}, sort_keys=True) + "\n"
        )
        if folder.exists():
            shutil.rmtree(folder)
        temporary.replace(folder)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _restore_snapshot(folder: Path) -> None:
    _clear_media_and_analytics()
    with maintenance_database_lock(DATABASE):
        _prepare_target_for_replace(DATABASE)
        descriptor, name = tempfile.mkstemp(
            dir=DATABASE.parent, prefix="e2e-restore-", suffix=".tmp"
        )
        os.close(descriptor)
        target = Path(name)
        try:
            shutil.copyfile(folder / "database.sqlite3", target)
            target.chmod(0o600)
            require_current_schema(target)
            target.replace(DATABASE)
        finally:
            for path in (target, Path(f"{target}-wal"), Path(f"{target}-shm")):
                path.unlink(missing_ok=True)
        for path in (folder / "media").iterdir():
            if path.is_dir():
                shutil.copytree(path, MEDIA / path.name)
            else:
                shutil.copyfile(path, MEDIA / path.name)


def prepare(config, *, fresh: bool = False) -> dict:
    require_e2e_target(config)
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    statistics = os.environ.get("VMSH_E2E_LARGE_STATISTICS") == "1"
    support = os.environ.get("VMSH_E2E_SUPPORT_NAVIGATION") == "1"
    key = seed_digest(statistics=statistics, support=support)
    folder = CACHE / key
    started = time.monotonic()
    hit = not fresh and snapshot_is_current(folder, key)
    if hit:
        _restore_snapshot(folder)
    else:
        _clear_media_and_analytics()
        seed_all(config, statistics=statistics, support=support)
        if key != seed_digest(statistics=statistics, support=support):
            raise RuntimeError("Seed inputs changed during preparation; rerun")
        _save_snapshot(folder, key)
    result = {
        "seed_cache_hit": hit,
        "seconds": round(time.monotonic() - started, 3),
        "key": key,
    }
    print("E2E preparation: " + json.dumps(result), flush=True)
    # Playwright normally hides successful webServer stdout. Keep this phase
    # measurement alongside the parent runner's build/browser timings.
    (CACHE.parent / "preparation-latest.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result


def main() -> None:
    if (
        require_pwa_profile_environment() != "pwa-e2e"
        or os.environ.get("PROD", "").lower() == "true"
    ):
        raise RuntimeError("Cached seed requires the isolated pwa-e2e profile")
    from helpers.config import config

    prepare(config, fresh=os.environ.get("VMSH_E2E_FRESH_SEED") == "1")


if __name__ == "__main__":
    main()

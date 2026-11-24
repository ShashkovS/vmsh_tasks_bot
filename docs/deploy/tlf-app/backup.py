"""Compressed online SQLite safety snapshots with verified restoration.

See README.md and ../cross-backup/README.md (2026-11-05 compression decision).
Includes the lossless Zoom table in the default main+analytics backup.
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/web/vmsh_tasks_bot")
CODE = BASE / "vmsh_tasks_bot"


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_7zip(executable, arguments, cwd):
    subprocess.run(
        [executable, *arguments],
        cwd=cwd,
        check=True,
        timeout=3600,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def create_archive(sources, destination, *, zoom_receipts=False):
    """Publish only after extracting and verifying the compressed bytes.

    Raw snapshots live only in a private temporary directory. Existing backups
    are never overwritten; compression/verification failures publish nothing.
    """
    executable = shutil.which("7zz") or shutil.which("7z")
    if executable is None:
        raise RuntimeError("7zip is required for safety backups")
    destination = destination.absolute()
    if destination.exists():
        raise FileExistsError(destination)
    now = datetime.now(UTC)
    with tempfile.TemporaryDirectory(
        prefix=".sqlite-backup-", dir=destination.parent
    ) as temporary:
        work = Path(temporary)
        snapshots = work / "snapshots"
        snapshots.mkdir(mode=0o700)
        databases = {}
        for label, source in sources.items():
            source = source.resolve(strict=True)
            target = snapshots / f"{label}.sqlite3"
            with (
                closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src,
                closing(sqlite3.connect(target)) as dst,
            ):
                src.backup(dst, pages=256, sleep=0.05)
            databases[label] = {
                "sha256": checksum(target),
                "bytes": target.stat().st_size,
            }
        report = {
            "createdAt": now.isoformat(),
            "integrity": "ok",
            "compression": "7z/LZMA2/mx=5",
            "databases": databases,
        }
        if zoom_receipts:
            with closing(sqlite3.connect(snapshots / "main.sqlite3")) as db:
                report["zoomReceipts"] = db.execute(
                    "SELECT count(*) FROM zoom_webhook_receipts"
                ).fetchone()[0]
        (snapshots / "report.json").write_text(json.dumps(report) + "\n")
        candidate = work / "backup.7z"
        members = [f"{label}.sqlite3" for label in sources] + ["report.json"]
        run_7zip(
            executable,
            ["a", "-t7z", "-m0=LZMA2", "-mx=5", "-mmt=2", str(candidate), *members],
            snapshots,
        )
        restored = work / "restored"
        restored.mkdir(mode=0o700)
        run_7zip(executable, ["x", "-y", f"-o{restored}", str(candidate)], work)
        if json.loads((restored / "report.json").read_text()) != report:
            raise RuntimeError("Restored backup report mismatch")
        for label, expected in databases.items():
            restored_db = restored / f"{label}.sqlite3"
            if checksum(restored_db) != expected["sha256"]:
                raise RuntimeError(f"{label} restore checksum failed")
            with closing(sqlite3.connect(restored_db)) as db:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise RuntimeError(f"{label} restore integrity failed")
        candidate.chmod(0o600)
        # Same-filesystem link is atomic and refuses an existing destination.
        os.link(candidate, destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="Single SQLite safety snapshot")
    parser.add_argument("--output", type=Path, help="New .7z archive (must not exist)")
    args = parser.parse_args()
    if bool(args.database) != bool(args.output):
        parser.error("--database and --output must be used together")
    if args.database:
        report = create_archive({"main": args.database}, args.output)
        print(json.dumps({"backup": str(args.output), **report}))
        return
    config = json.loads((CODE / "creds_prod/vmsh_bot_config_prod.json").read_text())
    directory = BASE / "backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory.mkdir(mode=0o700)
    try:
        report = create_archive(
            {
                "main": CODE / config["db_filename"],
                "analytics": CODE / config["pwa_analytics_db_filename"],
            },
            directory / "backup.7z",
            zoom_receipts=True,
        )
        (directory / "report.json").write_text(json.dumps(report) + "\n")
        print(json.dumps({"backup": directory.name, **report}))
    except BaseException:
        shutil.rmtree(directory)
        raise


if __name__ == "__main__":
    main()

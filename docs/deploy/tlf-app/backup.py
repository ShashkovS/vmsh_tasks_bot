"""Online SQLite safety snapshots and temporary restore verification.

See README.md. Includes the lossless Zoom table in the main database.
"""

import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/web/vmsh_tasks_bot")
CODE = BASE / "vmsh_tasks_bot"


def main():
    config = json.loads((CODE / "creds_prod/vmsh_bot_config_prod.json").read_text())
    now = datetime.now(UTC)
    directory = BASE / "backups" / now.strftime("%Y%m%dT%H%M%S.%fZ")
    directory.mkdir(mode=0o700)
    try:
        counts = {}
        for label, field in (
            ("main", "db_filename"),
            ("analytics", "pwa_analytics_db_filename"),
        ):
            source = CODE / config[field]
            if not source.is_file():
                raise RuntimeError(f"{label} database is missing")
            target = directory / f"{label}.sqlite3"
            with (sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as src,
                  sqlite3.connect(target) as dst):
                src.backup(dst)
            with tempfile.TemporaryDirectory(prefix="tlf-restore-") as temporary:
                restored = Path(temporary) / "restored.sqlite3"
                shutil.copyfile(target, restored)
                with sqlite3.connect(restored) as db:
                    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                        raise RuntimeError(f"{label} restore integrity failed")
                    if label == "main":
                        counts["zoomReceipts"] = db.execute(
                            "SELECT count(*) FROM zoom_webhook_receipts"
                        ).fetchone()[0]
        report = {"createdAt": now.isoformat(), "integrity": "ok", **counts}
        (directory / "report.json").write_text(json.dumps(report) + "\n")
        # Owner decision: cross-backup/README.md. Existing/deployment archives
        # stay separate; retention belongs only to the new cross-backup store.
        print(json.dumps({"backup": directory.name, **report}))
    except BaseException:
        # Failed, incomplete snapshots must not be mistaken for usable backups.
        shutil.rmtree(directory)
        raise


if __name__ == "__main__":
    main()

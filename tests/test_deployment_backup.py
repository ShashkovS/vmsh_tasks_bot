"""Safety archive contract: docs/deploy/cross-backup/README.md."""

import importlib.util
import json
import shutil
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "deployment_backup", ROOT / "docs/deploy/tlf-app/backup.py"
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)
pytestmark = pytest.mark.skipif(
    not (shutil.which("7zz") or shutil.which("7z")), reason="7zip is required"
)


def test_compressed_snapshot_restores_committed_wal_and_legacy_report(tmp_path):
    source = tmp_path / "live.db"
    with closing(sqlite3.connect(source)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE zoom_webhook_receipts(value TEXT)")
        db.executemany(
            "INSERT INTO zoom_webhook_receipts VALUES (?)", [("event",)] * 2000
        )
        db.commit()
        destination = tmp_path / "backup.7z"
        report = backup.create_archive(
            {"main": source}, destination, zoom_receipts=True
        )
        assert report["zoomReceipts"] == 2000
        assert db.execute("SELECT count(*) FROM zoom_webhook_receipts").fetchone() == (
            2000,
        )
    assert destination.stat().st_mode & 0o777 == 0o600
    assert {p.name for p in tmp_path.iterdir()} == {"live.db", "backup.7z"}
    assert destination.stat().st_size < report["databases"]["main"]["bytes"]
    restored = tmp_path / "extracted"
    backup.run_7zip(
        shutil.which("7zz") or shutil.which("7z"),
        ["x", "-y", f"-o{restored}", str(destination)],
        tmp_path,
    )
    assert json.loads((restored / "report.json").read_text()) == report
    with sqlite3.connect(restored / "main.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM zoom_webhook_receipts").fetchone() == (
            2000,
        )
    with pytest.raises(FileExistsError):
        backup.create_archive({"main": source}, destination)


@pytest.mark.parametrize("failure", ["compression", "restored_bytes"])
def test_failed_archive_never_publishes_or_changes_source(
    tmp_path, monkeypatch, failure
):
    source = tmp_path / "live.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE events(value TEXT)")
        db.execute("INSERT INTO events VALUES ('preserved')")
    before = backup.checksum(source)
    real_run = backup.run_7zip

    def fail(executable, arguments, cwd):
        if failure == "compression":
            raise subprocess.CalledProcessError(2, ["7zip"])
        real_run(executable, arguments, cwd)
        if arguments[0] == "x":
            (cwd / "restored/main.sqlite3").write_bytes(b"corrupted restored bytes")

    monkeypatch.setattr(backup, "run_7zip", fail)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        backup.create_archive({"main": source}, tmp_path / "failed.7z")
    assert backup.checksum(source) == before
    assert {p.name for p in tmp_path.iterdir()} == {"live.db"}


def test_default_helper_retains_directory_json_contract_and_only_compressed_db(
    tmp_path, monkeypatch, capsys
):
    code = tmp_path / "vmsh_tasks_bot"
    (code / "creds_prod").mkdir(parents=True)
    (tmp_path / "backups").mkdir()
    config = {"db_filename": "main.db", "pwa_analytics_db_filename": "analytics.db"}
    (code / "creds_prod/vmsh_bot_config_prod.json").write_text(json.dumps(config))
    for name in config.values():
        with sqlite3.connect(code / name) as db:
            db.execute("CREATE TABLE zoom_webhook_receipts(value TEXT)")
    monkeypatch.setattr(backup, "BASE", tmp_path)
    monkeypatch.setattr(backup, "CODE", code)
    monkeypatch.setattr("sys.argv", ["backup.py"])
    backup.main()
    result = json.loads(capsys.readouterr().out)
    directory = tmp_path / "backups" / result["backup"]
    assert {p.name for p in directory.iterdir()} == {"backup.7z", "report.json"}
    assert set(result["databases"]) == {"main", "analytics"}
    assert result["zoomReceipts"] == 0

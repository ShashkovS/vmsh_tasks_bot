"""TLF cutover proof; docs/deploy/tlf-app/deploy_problem_release.sh."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "docs/deploy/tlf-app/problem_release_data_check.py"


def report(path: Path, *, baseline: bool = False) -> dict:
    arguments = [sys.executable, str(CHECKER), str(path)]
    if baseline:
        arguments.append("--baseline")
    return json.loads(subprocess.check_output(arguments))


def legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE group_lessons(id INTEGER PRIMARY KEY, title TEXT);
            CREATE TABLE problems(id INTEGER PRIMARY KEY);
            CREATE TABLE content_revisions(id INTEGER PRIMARY KEY);
            CREATE TABLE users(id INTEGER PRIMARY KEY);
            CREATE TABLE zoom_webhook_receipts(id INTEGER PRIMARY KEY, raw_body BLOB);
            INSERT INTO group_lessons VALUES(1,'Preserved worksheet');
            INSERT INTO zoom_webhook_receipts VALUES(1,X'0001FF');
        """)


def migrate(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript((ROOT / "migrations/0108.pwa_problem_release.sql").read_text())


def test_cutover_preserves_all_old_columns_and_detects_data_changes(tmp_path):
    path = tmp_path / "release.sqlite3"
    legacy_database(path)
    before = report(path)
    migrate(path)
    assert report(path, baseline=True) == before
    with sqlite3.connect(path) as connection:
        connection.executescript(
            (ROOT / "migrations/0108.pwa_problem_release.rollback.sql").read_text()
        )
    assert report(path) == before
    migrate(path)
    assert report(path, baseline=True) == before
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE group_lessons SET title='Changed'")
    assert report(path)["group_lessons"] != before["group_lessons"]


def test_cutover_rejects_a_changed_release_baseline(tmp_path):
    path = tmp_path / "release.sqlite3"
    legacy_database(path)
    migrate(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE group_lessons SET problem_release_version=2")
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(path), "--baseline"], capture_output=True
    )
    assert result.returncode != 0
    assert b"Release version did not start at one" in result.stderr

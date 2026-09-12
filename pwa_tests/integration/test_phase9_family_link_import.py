from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys

from db_methods.pwa.migrations import apply_schema_migrations
from helpers.consts import USER_TYPE
from vmshpwa.scripts.family_link_import import preview_family_link_import


NOW = "2026-08-03T10:00:00Z"


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed(database_path) -> None:
    apply_schema_migrations(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for user_id in range(91_001, 91_005):
            connection.execute(
                "INSERT INTO users (id, type, name, surname, token) "
                "VALUES (?, ?, 'Ученик', 'Тестовый', ?)",
                (user_id, int(USER_TYPE.STUDENT), f"token-{user_id}"),
            )
        for account_id, username in ((92_001, "family-one"), (92_002, "family-two")):
            connection.execute(
                "INSERT INTO auth_accounts "
                "(id, audience, username, username_normalized, "
                "provisioning_source, display_name, credential_kind, credential_hash, "
                "status, created_at, updated_at) VALUES "
                "(?, 'family', ?, ?, 'synthetic-test', 'Семья', 'password', "
                "'hash', 'active', ?, ?)",
                (
                    account_id,
                    username,
                    username,
                    NOW,
                    NOW,
                ),
            )
        connection.executemany(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (92_001, 91_002, "отец", 0, NOW, NOW, None),
                (92_002, 91_003, "мама", 1, NOW, NOW, "2026-08-03T11:00:00Z"),
                (92_002, 91_004, "мама", 1, NOW, NOW, None),
            ),
        )


def test_preview_classifies_links_and_keeps_migrated_sqlite_read_only(tmp_path):
    database_path = tmp_path / "family-links.sqlite3"
    csv_path = tmp_path / "family-links.csv"
    _seed(database_path)
    csv_path.write_text(
        "family_username,student_public_id,relationship_label,is_primary\n"
        "family-one,u-91001,мама,true\n"
        "family-one,u-91002,мама,true\n"
        "family-two,u-91003,мама,true\n"
        "family-two,u-91004,мама,true\n",
        encoding="utf-8",
    )
    before = _sha256(database_path)

    report = preview_family_link_import(
        database_path=database_path,
        csv_path=csv_path,
    )

    assert report == {
        "schemaVersion": 1,
        "ready": True,
        "sourceSha256": _sha256(csv_path),
        "rowCount": 4,
        "validRowCount": 4,
        "actions": {"create": 1, "restore": 1, "update": 1, "unchanged": 1},
        "diagnostics": [],
    }
    assert _sha256(database_path) == before


def test_preview_reports_only_row_numbers_and_codes_for_missing_records(tmp_path):
    database_path = tmp_path / "family-links.sqlite3"
    csv_path = tmp_path / "family-links.csv"
    _seed(database_path)
    csv_path.write_text(
        "family_username,student_public_id,relationship_label,is_primary\n"
        "missing-family,u-91001,мама,true\n"
        "family-one,missing-student,мама,false\n",
        encoding="utf-8",
    )

    report = preview_family_link_import(
        database_path=database_path,
        csv_path=csv_path,
    )

    assert report["ready"] is False
    assert report["diagnostics"] == [
        {"rowNumber": 2, "code": "family_account_not_found"},
        {"rowNumber": 3, "code": "student_not_found"},
    ]
    rendered = json.dumps(report, ensure_ascii=False)
    assert "missing-family" not in rendered
    assert "missing-student" not in rendered


def test_cli_writes_the_same_redacted_report(tmp_path):
    database_path = tmp_path / "family-links.sqlite3"
    csv_path = tmp_path / "family-links.csv"
    report_path = tmp_path / "reports" / "preview.json"
    _seed(database_path)
    csv_path.write_text(
        "family_username,student_public_id,relationship_label,is_primary\n"
        "family-one,u-91001,мама,true\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "vmshpwa.scripts.family_link_import",
            "--database",
            str(database_path),
            "--csv",
            str(csv_path),
            "--report",
            str(report_path),
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    stdout_report = json.loads(completed.stdout)
    assert stdout_report == json.loads(report_path.read_text(encoding="utf-8"))
    assert stdout_report["actions"] == {
        "create": 1,
        "restore": 0,
        "update": 0,
        "unchanged": 0,
    }
    assert "family-one" not in completed.stdout
    assert "u-91001" not in completed.stdout

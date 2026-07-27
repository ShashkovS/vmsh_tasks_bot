"""Privacy and classification tests for the Phase-0 auth preflight."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from vmshpwa.scripts import auth_preflight
from vmshpwa.scripts.auth_preflight import (
    AuthPreflightError,
    analyze_database,
    render_json,
    render_markdown,
)


def _auth_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                type INTEGER,
                surname TEXT,
                birthday TEXT,
                token TEXT,
                chat_id INTEGER
            );
            CREATE TABLE kv_logins (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                kv_login TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (
                (1, 1, "Иванов", "2012-01-02", "safeA7x9", 900001),
                (2, 1, "  ИВАНОВ ", "2012-01-02", "123456", 900002),
                (3, 1, "   ", "not-a-date", "aaaaaaaa", 900003),
                (4, 1, "Петров", None, "12345678", 12345678),
                (10, 2, "PrivateTeacher", "1980-01-01", "teacher-secret", 910000),
                (11, -4, "UnknownPerson", None, "unknown-secret", 920000),
            ),
        )
        connection.executemany(
            "INSERT INTO kv_logins VALUES (?, ?, ?)",
            (
                (1, 1, "SameLogin"),
                (2, 2, " samelogin "),
                (3, 3, None),
            ),
        )


def test_auth_preflight_is_aggregate_deterministic_and_read_only(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    _auth_fixture(database_path)
    before = database_path.read_bytes()

    first = analyze_database(database_path)
    second = analyze_database(database_path)

    assert first == second
    assert database_path.read_bytes() == before
    assert first["sourceAccess"] == (
        "secure pre-open fd with strongest available nofollow flag; exact bytes "
        "read+SHA-256 on that fd; in-memory sqlite deserialize; PRAGMA "
        "query_only=ON; explicit read transaction; source path/fingerprint "
        "rechecked; WAL/journal sidecars refused"
    )
    assert first["sourceUnchanged"] is True
    assert first["cohort"]["studentRows"] == 4
    assert first["cohort"]["excludedNonStudentRows"] == 2
    assert first["cohort"]["explicitTestFlagAvailable"] is False
    assert first["cohort"]["explicitTestRows"] is None

    students = first["students"]
    assert students["birthday"] == {
        "null": 1,
        "blank": 0,
        "validIsoDate": 2,
        "invalidIsoDate": 1,
        "futureDate": 0,
    }
    assert students["surname"] == {"present": 3, "emptyAfterTrim": 1}
    assert students["tokenLengthBuckets"] == {
        "0": 0,
        "1-5": 0,
        "6-7": 1,
        "8-11": 3,
        "12-15": 0,
        "16-31": 0,
        "32+": 0,
    }
    assert students["guessableTokenShapes"] == {
        "shorterThan8": 1,
        "digitsOnly": 2,
        "singleRepeatedCharacter": 1,
        "commonPlaceholder": 2,
        "sameAsChatId": 1,
        "anyGuessableShape": 3,
    }
    assert students["activation"] == {
        "blockedByFieldOrTokenCondition": 3,
        "eligibleByFieldAndTokenConditions": 1,
        "sourceKeyCollisionRows": 2,
        "blockedByMeasuredLowerBound": 4,
        "provisionallyEligibleAfterMeasuredLowerBound": 0,
        "finalEligibilityUnknown": True,
    }

    collisions = first["loginCollisions"]
    assert collisions["futureCanonicalGeneratorAvailable"] is False
    assert collisions["normalizedSurnameBirthdaySourceKey"]["collisionGroups"] == 1
    assert collisions["normalizedSurnameBirthdaySourceKey"]["affectedRows"] == 2
    assert collisions["legacyKvLogin"] == {
        "tablePresent": True,
        "studentRows": 3,
        "nullOrBlank": 1,
        "collisionGroups": 1,
        "affectedRows": 2,
    }


def test_auth_reports_never_serialize_source_values(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    _auth_fixture(database_path)
    report = analyze_database(database_path)
    serialized = render_json(report) + render_markdown(report)

    for private_value in (
        "Иванов",
        "PrivateTeacher",
        "SameLogin",
        "safeA7x9",
        "teacher-secret",
        "900001",
        "12345678",
    ):
        assert private_value not in serialized
    assert json.loads(render_json(report)) == report


def test_unknown_user_types_are_aggregated_without_serializing_raw_value(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    _auth_fixture(database_path)
    private_type = 987_654_321_012_345
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (99, private_type, "Private", None, "private-token", 930000),
        )

    report = analyze_database(database_path)
    serialized = render_json(report) + render_markdown(report)

    assert str(private_type) not in serialized
    assert report["cohort"]["otherTypeRows"] == 1
    assert all(
        row["type"] in auth_preflight._TYPE_LABELS
        for row in report["cohort"]["rowsByKnownType"]
    )


def test_auth_preflight_refuses_a_snapshot_with_sqlite_sidecars(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    _auth_fixture(database_path)
    wal_path = Path(str(database_path) + "-wal")
    wal_path.touch()

    with pytest.raises(AuthPreflightError, match="quiescent SQLite snapshot"):
        analyze_database(database_path)

    assert wal_path.exists()


def test_auth_preflight_refuses_symlink_source(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    alias_path = tmp_path / "auth-alias.sqlite3"
    _auth_fixture(database_path)
    alias_path.symlink_to(database_path)

    with pytest.raises(AuthPreflightError, match="regular SQLite source"):
        analyze_database(alias_path)


def test_auth_preflight_refuses_hard_linked_source(tmp_path):
    database_path = tmp_path / "auth.sqlite3"
    alias_path = tmp_path / "auth-hardlink.sqlite3"
    _auth_fixture(database_path)
    os.link(database_path, alias_path)

    with pytest.raises(AuthPreflightError, match="hard-linked aliases"):
        analyze_database(alias_path)


def test_auth_preflight_detects_source_change(tmp_path, monkeypatch):
    database_path = tmp_path / "auth.sqlite3"
    _auth_fixture(database_path)
    open_snapshot = auth_preflight._open_read_only_snapshot

    def open_then_touch(content):
        connection = open_snapshot(content)
        stat = database_path.stat()
        os.utime(
            database_path,
            ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000),
        )
        return connection

    monkeypatch.setattr(auth_preflight, "_open_read_only_snapshot", open_then_touch)

    with pytest.raises(AuthPreflightError, match="no longer matches"):
        analyze_database(database_path)


def test_auth_preflight_fails_closed_without_sqlite_deserialize():
    with pytest.raises(AuthPreflightError, match="deserialize support is required"):
        auth_preflight._deserialize_snapshot(object(), b"sqlite bytes")


def test_auth_preflight_fails_closed_when_sqlite_deserialize_rejects_bytes():
    class BrokenConnection:
        def deserialize(self, _content):
            raise sqlite3.DatabaseError("synthetic deserialize failure")

    with pytest.raises(AuthPreflightError, match="could not be deserialized safely"):
        auth_preflight._deserialize_snapshot(BrokenConnection(), b"not sqlite")


def test_auth_validate_requires_both_report_members_and_rejects_stale(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "auth.sqlite3"
    json_report = tmp_path / "auth-preflight.json"
    markdown_report = tmp_path / "auth-preflight.md"
    _auth_fixture(database_path)
    monkeypatch.setattr(auth_preflight, "JSON_REPORT", json_report)
    monkeypatch.setattr(auth_preflight, "MARKDOWN_REPORT", markdown_report)
    auth_preflight.write_reports(database_path)

    for path in (json_report, markdown_report):
        expected = path.read_text(encoding="utf-8")
        path.unlink()
        with pytest.raises(AuthPreflightError, match="pwa-auth-preflight-update"):
            auth_preflight.validate_reports(database_path)
        path.write_text(expected, encoding="utf-8")
        path.write_text("stale\n", encoding="utf-8")
        with pytest.raises(AuthPreflightError, match="pwa-auth-preflight-update"):
            auth_preflight.validate_reports(database_path)
        path.write_text(expected, encoding="utf-8")

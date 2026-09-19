from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path

import pytest

from helpers.pwa.storage_config import StorageConfig
from vmshpwa.scripts import media_inventory
from vmshpwa.scripts.media_inventory import (
    DatabaseReference,
    MediaInventoryError,
    StoredObject,
    build_inventory,
    list_s3_objects,
    read_database_references,
    reconcile_media,
    write_owner_manifest,
)


def _database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE media_assets (
                object_key TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                storage_namespace TEXT NOT NULL,
                deleted_at TEXT
            );
            CREATE TABLE news_media (
                storage_key TEXT,
                storage_status TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO media_assets VALUES (?, ?, ?, ?)",
            (
                ("submission/active.webp", 3, "submission", None),
                ("submission/missing.webp", 9, "submission", None),
                (
                    "submission/deleted.webp",
                    4,
                    "submission",
                    "2026-08-03T10:00:00Z",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO news_media VALUES (?, ?)",
            (
                ("news/stored.jpg", "stored"),
                ("news/pending.jpg", "pending"),
            ),
        )
    return path


def test_migration_head_database_is_supported(isolated_pwa_database):
    assert read_database_references(isolated_pwa_database) == []


@pytest.mark.asyncio
async def test_filesystem_inventory_classifies_without_mutating_database(tmp_path):
    database = _database(tmp_path / "database.sqlite3")
    storage_root = tmp_path / "media"
    for key, payload in (
        ("submission/active.webp", b"bad-size"),
        ("submission/deleted.webp", b"gone"),
        ("news/stored.jpg", b"news"),
        ("news/pending.jpg", b"pending"),
        ("unknown/orphan.bin", b"orphan"),
    ):
        target = storage_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    database_before = database.read_bytes()

    report = await build_inventory(
        database_path=database,
        storage_config=StorageConfig.filesystem(storage_root),
        generated_at="2026-08-03T12:00:00Z",
    )

    assert database.read_bytes() == database_before
    assert report["readOnly"] is True
    assert report["deletionSupported"] is False
    assert report["summary"] == {
        "storageObjects": 5,
        "storageBytes": 29,
        "activeReferences": 3,
        "activeObjectsPresent": 2,
        "activeBytesPresent": 12,
        "missingActiveObjects": 1,
        "sizeMismatches": 1,
        "retainedDeletedObjects": 1,
        "retainedDeletedBytes": 4,
        "unconfirmedObjects": 1,
        "unconfirmedBytes": 7,
        "unreferencedObjects": 1,
        "unreferencedBytes": 6,
        "invalidDatabaseKeys": 0,
        "duplicateStorageKeys": 0,
        "activeReferencesByNamespace": {"news": 1, "submission": 2},
    }
    assert report["details"] == {
        "missingActiveKeys": ["submission/missing.webp"],
        "sizeMismatches": [
            {
                "key": "submission/active.webp",
                "databaseByteSizes": [3],
                "storageByteSize": 8,
            }
        ],
        "retainedDeletedKeys": ["submission/deleted.webp"],
        "unconfirmedKeys": ["news/pending.jpg"],
        "unreferencedKeys": ["unknown/orphan.bin"],
        "invalidDatabaseKeys": [],
        "duplicateStorageKeys": [],
    }


def test_active_reference_wins_when_the_same_key_has_other_states():
    report = reconcile_media(
        (
            DatabaseReference("shared/a.webp", 3, "submission", "active"),
            DatabaseReference("shared/a.webp", None, "news", "unconfirmed"),
        ),
        (StoredObject("shared/a.webp", 3),),
        generated_at="2026-08-03T12:00:00Z",
        storage_report={"adapter": "filesystem"},
    )
    assert report["summary"]["activeReferences"] == 1
    assert report["summary"]["unconfirmedObjects"] == 0
    assert report["details"]["unconfirmedKeys"] == []


class _FakeS3Client:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    async def list_objects_v2(self, **arguments):
        self.calls.append(arguments)
        return self.pages.pop(0)


class _FakeContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *_args):
        return None


class _FakeS3Session:
    def __init__(self, client):
        self.fake_client = client
        self.client_arguments = None

    def client(self, *arguments, **keywords):
        self.client_arguments = (arguments, keywords)
        return _FakeContext(self.fake_client)


@pytest.mark.asyncio
async def test_s3_inventory_paginates_and_strips_only_the_configured_prefix():
    client = _FakeS3Client(
        (
            {
                "Contents": [{"Key": "media/content/a.svg", "Size": 17}],
                "IsTruncated": True,
                "NextContinuationToken": "page-2",
            },
            {
                "Contents": [{"Key": "media/submission/b.webp", "Size": 31}],
                "IsTruncated": False,
            },
        )
    )
    session = _FakeS3Session(client)
    config = StorageConfig.s3(
        endpoint_url="https://nbg1.your-objectstorage.com",
        bucket_name="vmsh-media",
        region="nbg1",
        access_key="access-do-not-report",
        secret_key="secret-do-not-report",
        prefix="media",
        secret_source="production",
    )

    objects = await list_s3_objects(config, session=session)

    assert objects == [
        StoredObject("content/a.svg", 17),
        StoredObject("submission/b.webp", 31),
    ]
    assert client.calls == [
        {"Bucket": "vmsh-media", "Prefix": "media/"},
        {
            "Bucket": "vmsh-media",
            "Prefix": "media/",
            "ContinuationToken": "page-2",
        },
    ]


def test_owner_manifest_is_mode_0600_and_never_overwrites(tmp_path):
    report_root = tmp_path / ".runtime/vmshpwa/media-inventory"
    output = report_root / "run.json"
    report = {"schemaVersion": 1, "details": {"unreferencedKeys": ["x/a"]}}

    write_owner_manifest(report, output, report_root=report_root)

    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_owner_manifest(report, output, report_root=report_root)
    with pytest.raises(MediaInventoryError, match="below .runtime"):
        write_owner_manifest(
            report,
            tmp_path / "outside.json",
            report_root=report_root,
        )


def test_cli_prints_only_aggregates_and_writes_details_locally(
    tmp_path, monkeypatch, capsys
):
    database = _database(tmp_path / "database.sqlite3")
    media_root = tmp_path / "media"
    media_root.mkdir()
    report_root = tmp_path / ".runtime/vmshpwa/media-inventory"
    monkeypatch.setattr(media_inventory, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(media_inventory, "REPORT_ROOT", report_root)

    exit_code = media_inventory.main(
        [
            "--database",
            str(database),
            "--runtime-profile",
            "pwa-agent",
            "--media-root",
            str(media_root),
            "--output",
            ".runtime/vmshpwa/media-inventory/cli.json",
        ]
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "submission/missing.webp" not in stdout
    assert json.loads(stdout)["summary"]["missingActiveObjects"] == 3
    local_report = json.loads((report_root / "cli.json").read_text(encoding="utf-8"))
    assert local_report["details"]["missingActiveKeys"] == [
        "news/stored.jpg",
        "submission/active.webp",
        "submission/missing.webp",
    ]

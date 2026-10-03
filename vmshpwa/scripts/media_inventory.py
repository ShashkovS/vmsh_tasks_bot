"""Create a read-only SQLite/object-storage reconciliation manifest.

The command never deletes objects. Exact keys are written only to an owner-local
file below ``.runtime/vmshpwa/media-inventory``; stdout contains aggregate
counts. See Phase 11 retention rules in
``vmshpwa/dev/development-plan/15-phase-11-hardening-and-rollout.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import stat
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from helpers.object_storage import canonical_object_key
from helpers.pwa.storage_config import StorageConfig, load_storage_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = REPOSITORY_ROOT / ".runtime/vmshpwa/media-inventory"
S3_OPT_IN = "VMSH_ENABLE_MEDIA_INVENTORY"


class MediaInventoryError(RuntimeError):
    """The inventory could not be completed without guessing."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class DatabaseReference:
    key: str
    byte_size: int | None
    namespace: str
    state: str


def read_database_references(database_path: Path) -> list[DatabaseReference]:
    """Read the two canonical object-key sources from a migration-head DB."""

    if not database_path.is_file() or database_path.is_symlink():
        raise MediaInventoryError("Database must be an existing regular file")
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, autocommit=True) as connection:
            media_rows = connection.execute(
                "SELECT object_key, byte_size, storage_namespace, deleted_at "
                "FROM media_assets ORDER BY object_key"
            ).fetchall()
            news_rows = connection.execute(
                "SELECT storage_key, storage_status FROM news_media "
                "WHERE storage_key IS NOT NULL ORDER BY storage_key"
            ).fetchall()
    except sqlite3.Error as error:
        raise MediaInventoryError(
            "Database is not at a schema version supported by media inventory"
        ) from error

    references = [
        DatabaseReference(
            key=str(key),
            byte_size=int(byte_size),
            namespace=str(namespace),
            state="active" if deleted_at is None else "retained_deleted",
        )
        for key, byte_size, namespace, deleted_at in media_rows
    ]
    references.extend(
        DatabaseReference(
            key=str(key),
            byte_size=None,
            namespace="news",
            state="active" if status == "stored" else "unconfirmed",
        )
        for key, status in news_rows
    )
    return references


def list_filesystem_objects(root: Path) -> list[StoredObject]:
    """List regular files without following links outside the media root."""

    if not root.is_dir() or root.is_symlink():
        raise MediaInventoryError("Filesystem media root must be an existing directory")
    objects: list[StoredObject] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in tuple(directory_names):
            candidate = parent / name
            if candidate.is_symlink():
                raise MediaInventoryError("Filesystem media root contains a symlink")
        for name in file_names:
            candidate = parent / name
            metadata = candidate.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise MediaInventoryError(
                    "Filesystem media root contains a non-regular object"
                )
            key = candidate.relative_to(root).as_posix()
            objects.append(StoredObject(canonical_object_key(key), metadata.st_size))
    return sorted(objects, key=lambda item: item.key)


async def list_s3_objects(
    config: StorageConfig,
    *,
    session: object | None = None,
) -> list[StoredObject]:
    """List only the configured S3 prefix and return domain-relative keys."""

    if config.adapter != "s3":
        raise MediaInventoryError("S3 inventory requires an S3 storage profile")
    if session is None:
        import aioboto3

        session = aioboto3.Session()
    from aiobotocore.config import AioConfig

    prefix = f"{config.prefix}/" if config.prefix else ""
    client_factory = getattr(session, "client", None)
    if not callable(client_factory):
        raise MediaInventoryError("S3 session does not provide a client")
    objects: list[StoredObject] = []
    continuation_token: str | None = None
    seen_tokens: set[str] = set()
    try:
        async with client_factory(
            "s3",
            endpoint_url=config.endpoint_url,
            region_name=config.region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            config=AioConfig(
                signature_version="s3v4",
                retries={"mode": "standard", "max_attempts": 3},
                s3={"addressing_style": "virtual"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        ) as client:
            while True:
                arguments: dict[str, object] = {
                    "Bucket": config.bucket_name,
                    "Prefix": prefix,
                }
                if continuation_token is not None:
                    arguments["ContinuationToken"] = continuation_token
                response = await client.list_objects_v2(**arguments)
                contents = response.get("Contents", [])
                if not isinstance(contents, list):
                    raise MediaInventoryError("S3 list response is malformed")
                for item in contents:
                    if not isinstance(item, Mapping):
                        raise MediaInventoryError("S3 list response is malformed")
                    provider_key = item.get("Key")
                    byte_size = item.get("Size")
                    if not isinstance(provider_key, str) or not isinstance(
                        byte_size, int
                    ):
                        raise MediaInventoryError("S3 list response is malformed")
                    if prefix and not provider_key.startswith(prefix):
                        raise MediaInventoryError(
                            "S3 returned an object outside its prefix"
                        )
                    relative_key = (
                        provider_key[len(prefix) :] if prefix else provider_key
                    )
                    objects.append(
                        StoredObject(canonical_object_key(relative_key), byte_size)
                    )
                if not response.get("IsTruncated"):
                    break
                token = response.get("NextContinuationToken")
                if not isinstance(token, str) or not token or token in seen_tokens:
                    raise MediaInventoryError(
                        "S3 pagination token is missing or repeated"
                    )
                seen_tokens.add(token)
                continuation_token = token
    except MediaInventoryError:
        raise
    except Exception as error:
        # Provider messages can contain bucket names and full keys. Keep only
        # the exception type in the normal operator surface.
        raise MediaInventoryError(
            f"S3 inventory failed ({type(error).__name__})"
        ) from None
    return sorted(objects, key=lambda item: item.key)


def reconcile_media(
    references: Sequence[DatabaseReference],
    objects: Sequence[StoredObject],
    *,
    generated_at: str,
    storage_report: Mapping[str, object],
) -> dict[str, object]:
    """Classify storage without turning a diagnostic into deletion policy."""

    database_by_key: dict[str, list[DatabaseReference]] = defaultdict(list)
    invalid_database_keys: list[str] = []
    for reference in references:
        try:
            key = canonical_object_key(reference.key)
        except ValueError:
            invalid_database_keys.append(reference.key)
            continue
        database_by_key[key].append(reference)

    storage_by_key: dict[str, StoredObject] = {}
    duplicate_storage_keys: list[str] = []
    for item in objects:
        key = canonical_object_key(item.key)
        if key in storage_by_key:
            duplicate_storage_keys.append(key)
        storage_by_key[key] = item

    active_keys = {
        key
        for key, items in database_by_key.items()
        if any(item.state == "active" for item in items)
    }
    retained_deleted_keys = {
        key
        for key, items in database_by_key.items()
        if key not in active_keys
        and any(item.state == "retained_deleted" for item in items)
    }
    unconfirmed_keys = {
        key
        for key, items in database_by_key.items()
        if key not in active_keys
        and key not in retained_deleted_keys
        and any(item.state == "unconfirmed" for item in items)
    }
    storage_keys = set(storage_by_key)
    known_database_keys = set(database_by_key)
    unreferenced_keys = storage_keys - known_database_keys
    missing_active_keys = active_keys - storage_keys

    size_mismatches: list[dict[str, object]] = []
    for key in sorted(active_keys & storage_keys):
        expected_sizes = {
            item.byte_size
            for item in database_by_key[key]
            if item.state == "active" and item.byte_size is not None
        }
        if expected_sizes and expected_sizes != {storage_by_key[key].byte_size}:
            size_mismatches.append(
                {
                    "key": key,
                    "databaseByteSizes": sorted(expected_sizes),
                    "storageByteSize": storage_by_key[key].byte_size,
                }
            )

    namespace_counts: dict[str, int] = defaultdict(int)
    for items in database_by_key.values():
        for namespace in {item.namespace for item in items if item.state == "active"}:
            namespace_counts[namespace] += 1

    def stored_bytes(keys: set[str]) -> int:
        return sum(storage_by_key[key].byte_size for key in keys & storage_keys)

    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "readOnly": True,
        "deletionSupported": False,
        "storage": dict(storage_report),
        "summary": {
            "storageObjects": len(storage_keys),
            "storageBytes": stored_bytes(storage_keys),
            "activeReferences": len(active_keys),
            "activeObjectsPresent": len(active_keys & storage_keys),
            "activeBytesPresent": stored_bytes(active_keys),
            "missingActiveObjects": len(missing_active_keys),
            "sizeMismatches": len(size_mismatches),
            "retainedDeletedObjects": len(retained_deleted_keys & storage_keys),
            "retainedDeletedBytes": stored_bytes(retained_deleted_keys),
            "unconfirmedObjects": len(unconfirmed_keys & storage_keys),
            "unconfirmedBytes": stored_bytes(unconfirmed_keys),
            "unreferencedObjects": len(unreferenced_keys),
            "unreferencedBytes": stored_bytes(unreferenced_keys),
            "invalidDatabaseKeys": len(invalid_database_keys),
            "duplicateStorageKeys": len(duplicate_storage_keys),
            "activeReferencesByNamespace": dict(sorted(namespace_counts.items())),
        },
        "details": {
            "missingActiveKeys": sorted(missing_active_keys),
            "sizeMismatches": size_mismatches,
            "retainedDeletedKeys": sorted(retained_deleted_keys & storage_keys),
            "unconfirmedKeys": sorted(unconfirmed_keys & storage_keys),
            "unreferencedKeys": sorted(unreferenced_keys),
            "invalidDatabaseKeys": sorted(invalid_database_keys),
            "duplicateStorageKeys": sorted(set(duplicate_storage_keys)),
        },
    }


async def build_inventory(
    *,
    database_path: Path,
    storage_config: StorageConfig,
    generated_at: str,
    s3_session: object | None = None,
) -> dict[str, object]:
    references = await asyncio.to_thread(read_database_references, database_path)
    if storage_config.adapter == "filesystem":
        if storage_config.filesystem_root is None:
            raise MediaInventoryError("Filesystem storage root is missing")
        objects = await asyncio.to_thread(
            list_filesystem_objects, storage_config.filesystem_root
        )
    else:
        objects = await list_s3_objects(storage_config, session=s3_session)
    return reconcile_media(
        references,
        objects,
        generated_at=generated_at,
        storage_report=storage_config.safe_report(),
    )


def write_owner_manifest(
    report: Mapping[str, object],
    output_path: Path,
    *,
    report_root: Path | None = None,
) -> None:
    """Create one non-overwritable mode-0600 owner-local manifest."""

    report_root = REPORT_ROOT if report_root is None else report_root
    report_root.mkdir(parents=True, exist_ok=True)
    root = report_root.resolve(strict=True)
    candidate = (
        output_path if output_path.is_absolute() else REPOSITORY_ROOT / output_path
    )
    candidate_parent = candidate.parent.resolve(strict=False)
    if candidate_parent != root and root not in candidate_parent.parents:
        raise MediaInventoryError("Media inventory output must stay below .runtime")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.is_symlink():
        raise MediaInventoryError("Media inventory output cannot be a symlink")
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(
        candidate,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("VMSH_DB_FILENAME"))
    parser.add_argument(
        "--runtime-profile", default=os.environ.get("VMSH_RUNTIME_PROFILE")
    )
    parser.add_argument("--media-root", default=os.environ.get("VMSH_MEDIA_ROOT"))
    parser.add_argument("--output", required=True)
    return parser


async def _main_async(arguments: argparse.Namespace) -> dict[str, object]:
    if (
        not arguments.database
        or not arguments.runtime_profile
        or not arguments.media_root
    ):
        raise MediaInventoryError(
            "Runtime profile, database and media root are required"
        )
    config = load_storage_config(
        runtime_profile=arguments.runtime_profile,
        media_root=arguments.media_root,
        repository_root=REPOSITORY_ROOT,
    )
    if config.adapter == "s3" and os.environ.get(S3_OPT_IN) != "true":
        raise MediaInventoryError(f"S3 inventory requires explicit {S3_OPT_IN}=true")
    generated_at = (
        datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    return await build_inventory(
        database_path=Path(arguments.database),
        storage_config=config,
        generated_at=generated_at,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        report = asyncio.run(_main_async(arguments))
        write_owner_manifest(report, Path(arguments.output))
    except (MediaInventoryError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {"ok": True, "summary": report["summary"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DatabaseReference",
    "MediaInventoryError",
    "StoredObject",
    "build_inventory",
    "list_filesystem_objects",
    "list_s3_objects",
    "main",
    "read_database_references",
    "reconcile_media",
    "write_owner_manifest",
]

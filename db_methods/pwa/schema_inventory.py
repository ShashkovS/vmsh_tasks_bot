"""Deterministic, schema-only SQLite inventory for the PWA migration baseline.

The inventory deliberately reads ``sqlite_schema`` and PRAGMA metadata only. It
must never grow into a general database dumper: the agreed live database contains
personal data and legacy credentials. See Phase 0 in
``vmshpwa/dev/development-plan/04-phase-0-baseline.md``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import yoyo

from .migrations import MIGRATIONS_ROOT


SCHEMA_INVENTORY_FORMAT = "vmsh.sqlite-schema-inventory/v1"
SCHEMA_DRIFT_FORMAT = "vmsh.sqlite-schema-drift/v1"
MERGED_MIGRATION_BOUNDARY = 30

# Infrastructure tables are covered by a dedicated safe structural fingerprint,
# not by the product schema hash. SQLite-owned objects (sqlite_*) are filtered
# separately. Keeping the structure here matters: migration rows alone cannot
# detect an accidentally altered ``_yoyo_log`` table.
YOYO_SCHEMA_OBJECTS = frozenset(
    {"_yoyo_log", "_yoyo_migration", "_yoyo_version", "yoyo_lock"}
)

# These are persistent scratch objects created by the legacy analytics scripts,
# despite their temp_* names. Keep the allowlist explicit: silently ignoring a
# new prefix match would make the drift check fail open.
KNOWN_LEGACY_DERIVED_OBJECTS = frozenset(
    {
        "temp_7_window",
        "temp_7_window_3",
        "temp_from_excel",
        "temp_lesson_scores",
        "temp_problem_scores",
        "temp_real_problem_scores",
        "temp_result_rolling_window_scores",
        "temp_result_rolling_window_scores_3",
        "temp_student_visits",
        "temp_students_ids",
        "temp_user_decoder",
        "temp_zoom_teacher_work",
    }
)

OBJECT_TYPE_ORDER = {"table": 0, "index": 1, "view": 2, "trigger": 3}


class SchemaInventoryError(RuntimeError):
    """Raised when an inventory cannot be produced without guessing."""


class UnknownDerivedObjectError(SchemaInventoryError):
    """Raised for an unreviewed persistent temp_* object."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def inventory_json(inventory: Mapping[str, Any]) -> str:
    """Render a committed inventory with stable formatting and one final LF."""

    return (
        json.dumps(
            inventory,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def validate_inventory(inventory: Mapping[str, Any]) -> None:
    """Validate hashes, ordering and classification before trusting a fixture."""

    if inventory.get("format") != SCHEMA_INVENTORY_FORMAT:
        raise SchemaInventoryError("unsupported inventory format")
    try:
        migration = inventory["migration"]
        repository_head = migration["repository_head"]
        repository_head_status = migration["repository_head_status"]
        infrastructure = migration["infrastructure"]
        infrastructure_objects = infrastructure["objects"]
        product = inventory["product"]
        product_objects = product["objects"]
        derived = inventory["legacy_derived"]
        derived_objects = derived["objects"]
    except (KeyError, TypeError) as error:
        raise SchemaInventoryError("incomplete schema inventory") from error
    if (
        not isinstance(repository_head, list)
        or not isinstance(repository_head_status, dict)
        or set(repository_head_status)
        != {"is_current", "missing", "changed", "unexpected"}
        or not isinstance(repository_head_status["is_current"], bool)
        or any(
            not isinstance(repository_head_status[key], list)
            or not all(
                isinstance(value, str) and value
                for value in repository_head_status[key]
            )
            for key in ("missing", "changed", "unexpected")
        )
        or not isinstance(infrastructure_objects, list)
        or not isinstance(product_objects, list)
        or not isinstance(derived_objects, list)
    ):
        raise SchemaInventoryError("schema inventory object collections must be lists")
    repository_ids: list[str] = []
    for record in repository_head:
        if not isinstance(record, dict) or set(record) != {"id", "sha256"}:
            raise SchemaInventoryError("invalid repository migration record")
        migration_id = record["id"]
        migration_hash = record["sha256"]
        if (
            not isinstance(migration_id, str)
            or not migration_id
            or not isinstance(migration_hash, str)
            or len(migration_hash) != 64
            or any(character not in "0123456789abcdef" for character in migration_hash)
        ):
            raise SchemaInventoryError("invalid repository migration record")
        repository_ids.append(migration_id)
    if repository_ids != sorted(repository_ids) or len(repository_ids) != len(
        set(repository_ids)
    ):
        raise SchemaInventoryError("repository migrations are not uniquely ordered")
    status_sets = {
        key: set(repository_head_status[key])
        for key in ("missing", "changed", "unexpected")
    }
    if (
        status_sets["missing"] - set(repository_ids)
        or status_sets["changed"] - set(repository_ids)
        or status_sets["missing"] & status_sets["changed"]
        or status_sets["unexpected"] & set(repository_ids)
        or any(
            len(repository_head_status[key]) != len(status_sets[key])
            for key in status_sets
        )
        or repository_head_status["is_current"] != (not any(status_sets.values()))
    ):
        raise SchemaInventoryError("invalid repository migration-head status")
    _validate_safe_fingerprints(
        infrastructure_objects,
        allowed_names=YOYO_SCHEMA_OBJECTS,
        label="yoyo infrastructure",
    )
    if product_objects != sorted(product_objects, key=_object_sort_key):
        raise SchemaInventoryError("product objects are not deterministically ordered")
    _validate_safe_fingerprints(
        derived_objects,
        allowed_names=KNOWN_LEGACY_DERIVED_OBJECTS,
        label="legacy-derived",
    )

    for record in product_objects:
        try:
            object_type = str(record["type"])
            name = str(record["name"])
            sql = str(record["sql"])
            stored_hash = str(record["object_sha256"])
        except (KeyError, TypeError) as error:
            raise SchemaInventoryError("incomplete schema object record") from error
        if object_type not in OBJECT_TYPE_ORDER:
            raise SchemaInventoryError(f"unsupported schema object type: {object_type}")
        if _normalize_sql(sql) != sql:
            raise SchemaInventoryError(f"schema SQL is not normalized: {name}")
        expected_hash = hashlib.sha256(
            object_type.encode("utf-8")
            + b"\0"
            + name.encode("utf-8")
            + b"\0"
            + sql.encode("utf-8")
        ).hexdigest()
        if stored_hash != expected_hash:
            raise SchemaInventoryError(f"schema object hash mismatch: {name}")

    product_names = {str(record["name"]) for record in product_objects}
    derived_names = {str(record["name"]) for record in derived_objects}
    if product_names & YOYO_SCHEMA_OBJECTS:
        raise SchemaInventoryError("yoyo object leaked into the product inventory")
    if product_names & KNOWN_LEGACY_DERIVED_OBJECTS:
        raise SchemaInventoryError(
            "legacy-derived object leaked into product inventory"
        )
    if not derived_names <= KNOWN_LEGACY_DERIVED_OBJECTS:
        raise SchemaInventoryError("unreviewed legacy-derived object in inventory")
    if int(product.get("object_count", -1)) != len(product_objects):
        raise SchemaInventoryError("product object count mismatch")
    if int(derived.get("object_count", -1)) != len(derived_objects):
        raise SchemaInventoryError("legacy-derived object count mismatch")
    if derived.get("sha256") != _json_sha256(derived_objects):
        raise SchemaInventoryError("legacy-derived structure hash mismatch")
    if int(infrastructure.get("object_count", -1)) != len(infrastructure_objects):
        raise SchemaInventoryError("yoyo infrastructure object count mismatch")
    if infrastructure.get("sha256") != _json_sha256(infrastructure_objects):
        raise SchemaInventoryError("yoyo infrastructure structure hash mismatch")

    expected_product_hash = _json_sha256(
        {"format": SCHEMA_INVENTORY_FORMAT, "objects": product_objects}
    )
    if product.get("sha256") != expected_product_hash:
        raise SchemaInventoryError("product schema hash mismatch")
    expected_pragma_hash = _json_sha256(
        [_pragma_structure(record) for record in product_objects]
    )
    if product.get("pragma_structure_sha256") != expected_pragma_hash:
        raise SchemaInventoryError("PRAGMA structure hash mismatch")


def _validate_safe_fingerprints(
    records: list[dict[str, Any]],
    *,
    allowed_names: frozenset[str],
    label: str,
) -> None:
    if records != sorted(records, key=_object_sort_key):
        raise SchemaInventoryError(f"{label} objects are not deterministically ordered")
    for record in records:
        try:
            object_type = str(record["type"])
            name = str(record["name"])
            table_name = str(record["table_name"])
            definition_hash = str(record["definition_sha256"])
            structure_hash = str(record["structure_sha256"])
        except (KeyError, TypeError) as error:
            raise SchemaInventoryError(
                f"incomplete {label} object fingerprint"
            ) from error
        if object_type not in OBJECT_TYPE_ORDER:
            raise SchemaInventoryError(f"unsupported schema object type: {object_type}")
        if name not in allowed_names:
            raise SchemaInventoryError(f"unreviewed {label} object: {name}")
        if not table_name:
            raise SchemaInventoryError(f"missing table name for {label} object: {name}")
        for digest in (definition_hash, structure_hash):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise SchemaInventoryError(
                    f"invalid {label} object fingerprint: {name}"
                )


def _normalize_sql(sql: str) -> str:
    # Interior whitespace, quoting and case are intentionally preserved. Blind
    # SQL pretty-printing can change literals and conceal CHECK/collation drift.
    normalized = sql.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines()).strip()
    normalized = normalized.rstrip("; \t\n")
    return normalized + ";"


def _object_sort_key(record: Mapping[str, Any]) -> tuple[int, str, bytes]:
    name = str(record["name"])
    return (
        OBJECT_TYPE_ORDER[str(record["type"])],
        name.casefold(),
        name.encode("utf-8"),
    )


def _migration_number(migration_id: str) -> int | None:
    prefix = migration_id.partition(".")[0]
    return int(prefix) if prefix.isdigit() else None


@contextmanager
def _read_only_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    if not database_path.is_file():
        raise SchemaInventoryError(f"SQLite database does not exist: {database_path}")

    # Do not use immutable=1: an agreed live snapshot may legitimately have a
    # WAL file that a read-only connection still needs to observe.
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, autocommit=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise SchemaInventoryError("SQLite refused query_only mode")
        connection.execute("BEGIN")
        yield connection
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def _expected_migrations() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                (migration.id, migration.hash)
                for migration in yoyo.read_migrations(str(MIGRATIONS_ROOT))
            ),
            key=lambda pair: pair[0],
        )
    )


def _migration_summary(
    connection: sqlite3.Connection, *, require_migration_head: bool
) -> dict[str, Any]:
    expected = _expected_migrations()
    migration_table = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = '_yoyo_migration'"
    ).fetchone()
    if migration_table is None:
        if require_migration_head:
            raise SchemaInventoryError("_yoyo_migration is missing")
        return {
            "merged_boundary": f"{MERGED_MIGRATION_BOUNDARY:04d}",
            "repository_head": [
                {"id": migration_id, "sha256": migration_hash}
                for migration_id, migration_hash in expected
            ],
            "repository_head_status": {
                "is_current": False,
                "missing": [migration_id for migration_id, _ in expected],
                "changed": [],
                "unexpected": [],
            },
            "legacy_history": {
                "count": 0,
                "sha256": _json_sha256([]),
            },
        }

    applied_rows = connection.execute(
        "SELECT migration_id, migration_hash FROM _yoyo_migration "
        "ORDER BY migration_id, migration_hash"
    ).fetchall()
    applied = [(str(row[0]), str(row[1])) for row in applied_rows]
    applied_by_id: dict[str, str] = {}
    for migration_id, migration_hash in applied:
        if migration_id in applied_by_id:
            raise SchemaInventoryError(f"duplicate yoyo migration id: {migration_id}")
        applied_by_id[migration_id] = migration_hash

    expected_by_id = dict(expected)
    missing = [
        migration_id
        for migration_id, _ in expected
        if migration_id not in applied_by_id
    ]
    changed = [
        migration_id
        for migration_id, migration_hash in expected
        if migration_id in applied_by_id
        and applied_by_id[migration_id] != migration_hash
    ]
    unexpected = [
        migration_id
        for migration_id, _ in applied
        if migration_id not in expected_by_id
        and (
            (number := _migration_number(migration_id)) is None
            or number >= MERGED_MIGRATION_BOUNDARY
        )
    ]
    if require_migration_head and (missing or changed or unexpected):
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if changed:
            details.append("changed=" + ",".join(changed))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise SchemaInventoryError(
            "SQLite migration history is not at the repository head: "
            + "; ".join(details)
        )

    legacy = sorted(
        [
            [migration_id, migration_hash]
            for migration_id, migration_hash in applied
            if (number := _migration_number(migration_id)) is not None
            and number < MERGED_MIGRATION_BOUNDARY
        ]
    )
    return {
        "merged_boundary": f"{MERGED_MIGRATION_BOUNDARY:04d}",
        "repository_head": [
            {"id": migration_id, "sha256": migration_hash}
            for migration_id, migration_hash in expected
        ],
        # A committed live report is an acknowledged drift snapshot, not the
        # runtime readiness gate. It must be able to record that production is
        # still behind newly authored migrations without applying them to the
        # operator's database; ordinary PWA startup continues to require head.
        # See development-plan/04-phase-0-baseline.md and Phase 1 migration proof.
        "repository_head_status": {
            "is_current": not (missing or changed or unexpected),
            "missing": missing,
            "changed": changed,
            "unexpected": unexpected,
        },
        # Old source files are intentionally not reconstructed. Their aggregate
        # proves which agreed history was observed without making it authoritative.
        "legacy_history": {
            "count": len(legacy),
            "sha256": _json_sha256(legacy),
        },
    }


def _columns(connection: sqlite3.Connection, object_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        'SELECT cid, name, type, "notnull", dflt_value, pk, hidden '
        "FROM pragma_table_xinfo(?, 'main') ORDER BY cid",
        (object_name,),
    ).fetchall()
    return [
        {
            "cid": int(row["cid"]),
            "name": str(row["name"]),
            "declared_type": str(row["type"] or "").strip().upper(),
            "not_null": bool(row["notnull"]),
            "default_sql": row["dflt_value"],
            "primary_key_ordinal": int(row["pk"]),
            "hidden": int(row["hidden"]),
        }
        for row in rows
    ]


def _primary_key_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [
        column["name"]
        for column in sorted(
            (
                column
                for column in _columns(connection, table_name)
                if column["primary_key_ordinal"] > 0
            ),
            key=lambda column: column["primary_key_ordinal"],
        )
    ]


def _foreign_keys(
    connection: sqlite3.Connection, table_name: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        'SELECT id, seq, "table", "from", "to", on_update, on_delete, match '
        "FROM pragma_foreign_key_list(?, 'main') ORDER BY id, seq",
        (table_name,),
    ).fetchall()
    grouped: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[int(row["id"])].append(row)

    foreign_keys: list[dict[str, Any]] = []
    for group in grouped.values():
        group.sort(key=lambda row: int(row["seq"]))
        target_table = str(group[0]["table"])
        implicit_flags = {row["to"] is None for row in group}
        if len(implicit_flags) != 1:
            raise SchemaInventoryError(
                f"foreign key mixes implicit and explicit targets: {table_name}"
            )
        implicit_target = implicit_flags == {True}
        if implicit_target:
            target_columns = _primary_key_columns(connection, target_table)
            if len(target_columns) != len(group):
                target_columns = ["<implicit-unresolved>"] * len(group)
        else:
            target_columns = [str(row["to"]) for row in group]
        foreign_keys.append(
            {
                "from_columns": [str(row["from"]) for row in group],
                "target_table": target_table,
                "target_columns": target_columns,
                "on_update": str(group[0]["on_update"]),
                "on_delete": str(group[0]["on_delete"]),
                "match": str(group[0]["match"]),
            }
        )
    return sorted(
        foreign_keys,
        key=lambda item: _canonical_json_bytes(item),
    )


def _indexes(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        'SELECT seq, name, "unique", origin, partial '
        "FROM pragma_index_list(?, 'main')",
        (table_name,),
    ).fetchall()
    indexes: list[dict[str, Any]] = []
    for row in rows:
        index_name = str(row["name"])
        column_rows = connection.execute(
            "SELECT seqno, cid, name, desc, coll, key "
            "FROM pragma_index_xinfo(?, 'main') ORDER BY seqno",
            (index_name,),
        ).fetchall()
        indexes.append(
            {
                "name": index_name,
                "unique": bool(row["unique"]),
                "origin": str(row["origin"]),
                "partial": bool(row["partial"]),
                "columns": [
                    {
                        "seqno": int(column["seqno"]),
                        "cid": int(column["cid"]),
                        "name": column["name"],
                        "descending": bool(column["desc"]),
                        "collation": column["coll"],
                        "key": bool(column["key"]),
                    }
                    for column in column_rows
                ],
            }
        )
    return sorted(
        indexes,
        key=lambda item: (
            str(item["name"]).casefold(),
            str(item["name"]).encode("utf-8"),
        ),
    )


def _schema_object(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    object_type = str(row["type"])
    name = str(row["name"])
    if object_type not in OBJECT_TYPE_ORDER:
        raise SchemaInventoryError(f"unsupported sqlite_schema type: {object_type}")
    if row["sql"] is None:
        raise SchemaInventoryError(f"schema object has no DDL: {object_type} {name}")

    normalized_sql = _normalize_sql(str(row["sql"]))
    record: dict[str, Any] = {
        "type": object_type,
        "name": name,
        "table_name": str(row["tbl_name"]),
        "sql": normalized_sql,
    }
    if object_type == "table":
        record["columns"] = _columns(connection, name)
        record["foreign_keys"] = _foreign_keys(connection, name)
        record["indexes"] = _indexes(connection, name)
    record["object_sha256"] = hashlib.sha256(
        object_type.encode("utf-8")
        + b"\0"
        + name.encode("utf-8")
        + b"\0"
        + normalized_sql.encode("utf-8")
    ).hexdigest()
    return record


def _redacted_default(default_sql: Any) -> dict[str, Any]:
    """Describe a DEFAULT expression without serializing its literal text.

    Defaults are part of structural drift, but a live database can contain a
    credential-like literal in DDL. A digest lets ``check-live`` detect a change
    while keeping the committed report free of the value itself.
    """

    if default_sql is None:
        return {"present": False}
    encoded = str(default_sql).encode("utf-8")
    return {
        "present": True,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _safe_pragma_structure(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return schema metadata safe to persist for an agreed live database."""

    structure: dict[str, Any] = {
        "type": record["type"],
        "name": record["name"],
        "table_name": record["table_name"],
    }
    if record["type"] == "table":
        structure.update(
            {
                "columns": [
                    {
                        **{
                            key: value
                            for key, value in column.items()
                            if key != "default_sql"
                        },
                        "default": _redacted_default(column.get("default_sql")),
                    }
                    for column in record["columns"]
                ],
                "foreign_keys": record["foreign_keys"],
                "indexes": record["indexes"],
            }
        )
    # CHECK expressions, partial-index predicates and view/trigger bodies do not
    # have complete PRAGMA representations. Their digest closes that gap without
    # placing potentially sensitive SQL literals in the report.
    structure["definition_sha256"] = record["object_sha256"]
    return structure


def _safe_object_fingerprint(record: Mapping[str, Any]) -> dict[str, Any]:
    safe_structure = _safe_pragma_structure(record)
    return {
        "type": record["type"],
        "name": record["name"],
        "table_name": record["table_name"],
        "definition_sha256": record["object_sha256"],
        "structure_sha256": _json_sha256(safe_structure),
    }


def _pragma_structure(record: Mapping[str, Any]) -> dict[str, Any]:
    structure: dict[str, Any] = {
        "type": record["type"],
        "name": record["name"],
        "table_name": record["table_name"],
    }
    if record["type"] == "table":
        structure.update(
            {
                "columns": record["columns"],
                "foreign_keys": record["foreign_keys"],
                "indexes": record["indexes"],
            }
        )
    elif record["type"] in {"view", "trigger"}:
        # SQLite exposes no equivalent structural PRAGMA for view/trigger bodies.
        structure["sql"] = record["sql"]
    # Explicit indexes are represented in their owning table's pragma_index_*
    # metadata. Their exact SQL (including a partial predicate or expression)
    # remains covered by object_sha256 without turning whitespace into a false
    # PRAGMA-structure difference.
    return structure


def capture_schema_inventory(
    database_path: str | Path,
    *,
    source_kind: str,
    require_migration_head: bool = True,
) -> dict[str, Any]:
    """Capture deterministic schema metadata without reading product rows."""

    if not source_kind or "/" in source_kind or "\\" in source_kind:
        raise SchemaInventoryError("source_kind must be a stable label, not a path")
    path = Path(database_path)
    with _read_only_connection(path) as connection:
        migration = _migration_summary(
            connection, require_migration_head=require_migration_head
        )
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        infrastructure_objects: list[dict[str, Any]] = []
        product_objects: list[dict[str, Any]] = []
        legacy_derived_objects: list[dict[str, Any]] = []
        for row in rows:
            name = str(row["name"])
            if name in YOYO_SCHEMA_OBJECTS:
                infrastructure_objects.append(
                    _safe_object_fingerprint(_schema_object(connection, row))
                )
                continue
            if name.startswith("temp_") and name not in KNOWN_LEGACY_DERIVED_OBJECTS:
                raise UnknownDerivedObjectError(
                    f"unreviewed persistent legacy-derived object: {name}"
                )
            record = _schema_object(connection, row)
            if name in KNOWN_LEGACY_DERIVED_OBJECTS:
                legacy_derived_objects.append(_safe_object_fingerprint(record))
            else:
                product_objects.append(record)

    infrastructure_objects.sort(key=_object_sort_key)
    product_objects.sort(key=_object_sort_key)
    legacy_derived_objects.sort(key=_object_sort_key)
    product_hash_payload = {
        "format": SCHEMA_INVENTORY_FORMAT,
        "objects": product_objects,
    }
    pragma_payload = [_pragma_structure(record) for record in product_objects]
    migration["infrastructure"] = {
        "object_count": len(infrastructure_objects),
        "sha256": _json_sha256(infrastructure_objects),
        "objects": infrastructure_objects,
    }
    inventory = {
        "format": SCHEMA_INVENTORY_FORMAT,
        "source_kind": source_kind,
        "migration": migration,
        "product": {
            "object_count": len(product_objects),
            "sha256": _json_sha256(product_hash_payload),
            "pragma_structure_sha256": _json_sha256(pragma_payload),
            "objects": product_objects,
        },
        "legacy_derived": {
            "object_count": len(legacy_derived_objects),
            "sha256": _json_sha256(legacy_derived_objects),
            "objects": legacy_derived_objects,
        },
    }
    validate_inventory(inventory)
    return inventory


def render_schema_snapshot(inventory: Mapping[str, Any]) -> str:
    """Render product DDL only; the result is documentation, not a bootstrap."""

    validate_inventory(inventory)
    objects = inventory["product"]["objects"]
    if list(objects) != sorted(objects, key=_object_sort_key):
        raise SchemaInventoryError(
            "inventory objects are not deterministically ordered"
        )
    header = [
        "-- GENERATED FILE. DO NOT EDIT BY HAND.",
        "-- Authoritative source: repository yoyo migrations plus schema inventory.",
        "-- Schema-only: contains no product row values; DDL is migration-authored.",
        "-- Reference only: apply migrations rather than using this as a bootstrap.",
        f"-- Product schema SHA-256: {inventory['product']['sha256']}",
        "",
    ]
    statements = [str(record["sql"]) for record in objects]
    return "\n".join(header) + "\n" + "\n\n".join(statements) + "\n"


def _known_defects(
    actual_by_name: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    defects: list[dict[str, str]] = []
    reaction_enum = actual_by_name.get("reaction_enum")
    if reaction_enum is not None and not any(
        foreign_key["target_table"] == "reaction_type_enum"
        and foreign_key["from_columns"] == ["reaction_type_id"]
        and foreign_key["target_columns"] == ["reaction_type_id"]
        for foreign_key in reaction_enum.get("foreign_keys", [])
    ):
        defects.append(
            {
                "code": "LIVE_REACTION_ENUM_TYPE_FK_MISSING",
                "object": "reaction_enum",
                "summary": "reaction_type_id has no foreign key to reaction_type_enum",
            }
        )
    reactions = actual_by_name.get("reactions")
    if reactions is not None and any(
        foreign_key["target_table"] == "zoom_conversation"
        and foreign_key["from_columns"] == ["zoom_conversation_id"]
        and foreign_key["target_columns"] == ["zoom_conversation_id"]
        for foreign_key in reactions.get("foreign_keys", [])
    ):
        defects.append(
            {
                "code": "LIVE_REACTIONS_ZOOM_FK_TARGET_INVALID",
                "object": "reactions",
                "summary": (
                    "zoom_conversation_id targets the absent "
                    "zoom_conversation.zoom_conversation_id column"
                ),
            }
        )
    return defects


def compare_schema_inventories(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> dict[str, Any]:
    """Produce a deterministic schema-only drift report."""

    validate_inventory(expected)
    validate_inventory(actual)

    expected_objects = {
        (record["type"], record["name"]): record
        for record in expected["product"]["objects"]
    }
    actual_objects = {
        (record["type"], record["name"]): record
        for record in actual["product"]["objects"]
    }

    def identity_sort_key(key: tuple[str, str]) -> tuple[int, str, bytes]:
        return (
            OBJECT_TYPE_ORDER[key[0]],
            key[1].casefold(),
            key[1].encode("utf-8"),
        )

    missing = sorted(
        expected_objects.keys() - actual_objects.keys(), key=identity_sort_key
    )
    unexpected = sorted(
        actual_objects.keys() - expected_objects.keys(), key=identity_sort_key
    )
    common = sorted(
        expected_objects.keys() & actual_objects.keys(), key=identity_sort_key
    )
    ddl_differences = [
        {"type": key[0], "name": key[1]}
        for key in common
        if expected_objects[key]["object_sha256"]
        != actual_objects[key]["object_sha256"]
    ]
    pragma_differences = [
        {
            "type": key[0],
            "name": key[1],
            "expected": _safe_pragma_structure(expected_objects[key]),
            "actual": _safe_pragma_structure(actual_objects[key]),
        }
        for key in common
        if _pragma_structure(expected_objects[key])
        != _pragma_structure(actual_objects[key])
    ]
    actual_by_name = {record["name"]: record for record in actual_objects.values()}
    legacy_derived = list(actual["legacy_derived"]["objects"])
    return {
        "format": SCHEMA_DRIFT_FORMAT,
        "expected_product_sha256": expected["product"]["sha256"],
        "actual_product_sha256": actual["product"]["sha256"],
        "expected_pragma_structure_sha256": expected["product"][
            "pragma_structure_sha256"
        ],
        "actual_pragma_structure_sha256": actual["product"]["pragma_structure_sha256"],
        "migration": actual["migration"],
        "missing_product_objects": [
            {"type": object_type, "name": name} for object_type, name in missing
        ],
        "unexpected_product_objects": [
            {"type": object_type, "name": name} for object_type, name in unexpected
        ],
        "ddl_text_differences": ddl_differences,
        "pragma_structure_differences": pragma_differences,
        "legacy_derived_objects": legacy_derived,
        "known_schema_defects": _known_defects(actual_by_name),
        "known_out_of_scope_data_risks": [
            {
                "code": "MIGRATION_0038_LEGACY_KV_LOGIN_ROWS",
                "migration_id": "0038.kv_logins",
                "summary": (
                    "The migration contains legacy kv_login rows; this schema-only "
                    "command deliberately does not inspect or export their values"
                ),
            }
        ],
    }


def render_drift_markdown(report: Mapping[str, Any]) -> str:
    """Render a compact, safe human review of a drift report."""

    if report.get("format") != SCHEMA_DRIFT_FORMAT:
        raise SchemaInventoryError("unsupported drift report format")
    defects = report["known_schema_defects"]
    derived = report["legacy_derived_objects"]
    lines = [
        "# Read-only live schema drift report",
        "",
        "This report contains schema metadata only. Product row values were not selected",
        "or stored. Live DDL/default literals were read transiently but are represented",
        "only by safe structural metadata and fingerprints; paths and timestamps are omitted.",
        "",
        "## Summary",
        "",
        f"- Expected product hash: `{report['expected_product_sha256']}`.",
        f"- Observed product hash: `{report['actual_product_sha256']}`.",
        f"- DDL text differences: {len(report['ddl_text_differences'])}.",
        f"- PRAGMA-structure differences: {len(report['pragma_structure_differences'])}.",
        "- Yoyo infrastructure hash: "
        f"`{report['migration']['infrastructure']['sha256']}`.",
        "- Repository migration head current: "
        f"{str(report['migration']['repository_head_status']['is_current']).lower()}.",
        f"- Known legacy-derived objects: {len(derived)}.",
        "",
        "## Migration-head drift",
        "",
    ]
    migration_status = report["migration"]["repository_head_status"]
    for label in ("missing", "changed", "unexpected"):
        values = migration_status[label]
        rendered = ", ".join(f"`{value}`" for value in values) if values else "none"
        lines.append(f"- {label.capitalize()}: {rendered}.")
    lines.extend(
        [
            "",
            "## Known schema defects",
            "",
        ]
    )
    if defects:
        lines.extend(
            f"- `{defect['code']}` — {defect['summary']}." for defect in defects
        )
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Legacy-derived objects", ""])
    if derived:
        lines.extend(
            f"- `{record['type']} {record['name']}` — structure "
            f"`{record['structure_sha256']}`."
            for record in derived
        )
    else:
        lines.append("- None detected.")
    lines.extend(
        [
            "",
            "## Data deliberately outside this check",
            "",
            "- `0038.kv_logins` contains legacy rows. The schema inventory never",
            "  selects, hashes or exports their values; synthetic test seeding must",
            "  sanitize them in its own isolated database.",
            "- Live DDL/default literals are never serialized. Persisted fingerprints",
            "  detect drift in product, yoyo and allowlisted derived objects.",
            "",
            "The exact JSON evidence is stored beside this document.",
            "",
        ]
    )
    return "\n".join(lines)


def load_inventory(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a committed inventory."""

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SchemaInventoryError(
            f"cannot load schema inventory {path}: {error}"
        ) from error
    if not isinstance(value, dict) or value.get("format") != SCHEMA_INVENTORY_FORMAT:
        raise SchemaInventoryError(f"unsupported schema inventory: {path}")
    validate_inventory(value)
    return value

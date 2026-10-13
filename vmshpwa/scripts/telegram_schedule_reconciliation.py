"""Validate the manual Telegram scheduled-queue cutover inventory.

The Bot API cannot list messages scheduled by a human in Telegram clients;
MTProto's ``messages.getScheduledHistory`` is explicitly user-only.  Phase 8
therefore uses a reviewed local hash inventory instead of adding a user-account
session to the bot.  See development-plan/12-phase-8-news-and-notifications.md.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from vmshpwa.scripts.report_io import atomic_write_text


SCHEMA_VERSION = 1
MAX_INVENTORY_BYTES = 1024 * 1024
MAX_ITEMS = 10_000
DECISIONS = {
    "retain_in_telegram",
    "cancel_and_recreate_in_staff",
    "cancel_as_obsolete",
}
ITEM_FIELDS = {
    "itemKey",
    "destinationKey",
    "scheduledFor",
    "currentRevisionSha256",
    "reviewedRevisionSha256",
    "currentMediaManifestSha256",
    "reviewedMediaManifestSha256",
    "decision",
    "staffDraftKey",
}
_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class InvalidScheduledQueueInventory(ValueError):
    """A stable, payload-free reason why an inventory cannot be evaluated."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_key(value: object) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise InvalidScheduledQueueInventory("invalid_key")
    return value


def _require_sha256(value: object, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InvalidScheduledQueueInventory("invalid_sha256")
    return value


def _require_timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidScheduledQueueInventory("invalid_scheduled_time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidScheduledQueueInventory("invalid_scheduled_time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidScheduledQueueInventory("scheduled_time_requires_timezone")
    return value


def build_report(document: object) -> dict[str, object]:
    """Return an aggregate report that never echoes destinations or content hashes."""

    if not isinstance(document, dict) or set(document) != {"schemaVersion", "items"}:
        raise InvalidScheduledQueueInventory("invalid_document_fields")
    if document["schemaVersion"] != SCHEMA_VERSION:
        raise InvalidScheduledQueueInventory("unsupported_schema_version")
    items = document["items"]
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise InvalidScheduledQueueInventory("invalid_items")

    decision_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    issues: list[dict[str, object]] = []
    seen_item_keys: set[str] = set()
    seen_staff_drafts: set[str] = set()
    seen_active_intents: set[tuple[str, str, str, str | None]] = set()

    def issue(row_number: int, code: str) -> None:
        issue_counts[code] += 1
        issues.append({"rowNumber": row_number, "code": code})

    for row_number, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict) or set(raw_item) != ITEM_FIELDS:
            raise InvalidScheduledQueueInventory("invalid_item_fields")

        item_key = _require_key(raw_item["itemKey"])
        destination_key = _require_key(raw_item["destinationKey"])
        scheduled_for = _require_timestamp(raw_item["scheduledFor"])
        current_revision = _require_sha256(raw_item["currentRevisionSha256"])
        reviewed_revision = _require_sha256(raw_item["reviewedRevisionSha256"])
        current_media = _require_sha256(
            raw_item["currentMediaManifestSha256"], nullable=True
        )
        reviewed_media = _require_sha256(
            raw_item["reviewedMediaManifestSha256"], nullable=True
        )
        decision = raw_item["decision"]
        if not isinstance(decision, str) or decision not in DECISIONS:
            raise InvalidScheduledQueueInventory("invalid_decision")
        decision_counts[decision] += 1

        staff_draft_raw = raw_item["staffDraftKey"]
        staff_draft = None if staff_draft_raw is None else _require_key(staff_draft_raw)

        if item_key in seen_item_keys:
            issue(row_number, "duplicate_item_key")
        seen_item_keys.add(item_key)

        if current_revision != reviewed_revision or current_media != reviewed_media:
            issue(row_number, "changed_after_review")

        if decision == "cancel_and_recreate_in_staff":
            if staff_draft is None:
                issue(row_number, "staff_draft_required")
            elif staff_draft in seen_staff_drafts:
                issue(row_number, "duplicate_staff_draft")
            else:
                seen_staff_drafts.add(staff_draft)
        elif staff_draft is not None:
            issue(row_number, "staff_draft_not_allowed")

        if decision != "cancel_as_obsolete":
            intent = (
                destination_key,
                scheduled_for,
                current_revision,
                current_media,
            )
            if intent in seen_active_intents:
                issue(row_number, "duplicate_active_intent")
            else:
                seen_active_intents.add(intent)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "ready" if not issues else "blocked",
        "inventoryCount": len(items),
        "decisions": {name: decision_counts[name] for name in sorted(DECISIONS)},
        "blockerCount": len(issues),
        "blockersByCode": dict(sorted(issue_counts.items())),
        "issues": issues,
        "privacy": {
            "containsPayload": False,
            "containsTelegramIds": False,
            "containsDestinationKeys": False,
            "containsContentHashes": False,
        },
    }


def invalid_report(code: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "invalid",
        "inventoryCount": 0,
        "decisions": {name: 0 for name in sorted(DECISIONS)},
        "blockerCount": 1,
        "blockersByCode": {code: 1},
        "issues": [{"rowNumber": None, "code": code}],
        "privacy": {
            "containsPayload": False,
            "containsTelegramIds": False,
            "containsDestinationKeys": False,
            "containsContentHashes": False,
        },
    }


def load_inventory(path: Path) -> object:
    if path.stat().st_size > MAX_INVENTORY_BYTES:
        raise InvalidScheduledQueueInventory("inventory_too_large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidScheduledQueueInventory("invalid_json") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a manually reviewed Telegram scheduled-post inventory"
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = build_report(load_inventory(arguments.inventory))
    except (OSError, InvalidScheduledQueueInventory) as error:
        code = (
            error.code
            if isinstance(error, InvalidScheduledQueueInventory)
            else "inventory_unavailable"
        )
        report = invalid_report(code)

    atomic_write_text(
        arguments.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        mode=0o600,
    )
    print(
        "Telegram scheduled-queue reconciliation: "
        f"{report['status']} ({report['inventoryCount']} items, "
        f"{report['blockerCount']} blockers)"
    )
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())

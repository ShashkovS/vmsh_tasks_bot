from __future__ import annotations

import json
import stat
from copy import deepcopy
from pathlib import Path

import pytest

from vmshpwa.scripts.telegram_schedule_reconciliation import (
    InvalidScheduledQueueInventory,
    build_report,
    main,
)


FIXTURE = Path(__file__).parent / "fixtures" / "telegram-scheduled-queue-v1.json"


def _inventory() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ready_inventory_allows_same_content_for_different_destinations():
    report = build_report(_inventory())

    assert report["status"] == "ready"
    assert report["inventoryCount"] == 4
    assert report["decisions"] == {
        "cancel_and_recreate_in_staff": 1,
        "cancel_as_obsolete": 1,
        "retain_in_telegram": 2,
    }
    assert report["blockerCount"] == 0


def test_changed_review_and_duplicate_intent_block_cutover_without_echoing_data():
    inventory = _inventory()
    items = inventory["items"]
    assert isinstance(items, list)
    changed = items[0]
    assert isinstance(changed, dict)
    changed["currentRevisionSha256"] = "e" * 64

    duplicate = deepcopy(items[1])
    duplicate["itemKey"] = "pending-005"
    items.append(duplicate)

    report = build_report(inventory)
    serialized = json.dumps(report)

    assert report["status"] == "blocked"
    assert report["blockersByCode"] == {
        "changed_after_review": 1,
        "duplicate_active_intent": 1,
    }
    assert "course-math-news" not in serialized
    assert "group-beginners-news" not in serialized
    assert "e" * 64 not in serialized


def test_duplicate_item_and_staff_draft_are_explicit_blockers():
    inventory = _inventory()
    items = inventory["items"]
    assert isinstance(items, list)
    duplicate = deepcopy(items[2])
    assert isinstance(duplicate, dict)
    duplicate["destinationKey"] = "another-destination"
    duplicate["scheduledFor"] = "2026-09-09T12:00:00Z"
    items.append(duplicate)

    report = build_report(inventory)

    assert report["blockersByCode"] == {
        "duplicate_item_key": 1,
        "duplicate_staff_draft": 1,
    }


@pytest.mark.parametrize(
    ("decision", "staff_draft", "expected_code"),
    [
        ("cancel_and_recreate_in_staff", None, "staff_draft_required"),
        ("retain_in_telegram", "staff-draft-002", "staff_draft_not_allowed"),
    ],
)
def test_staff_draft_ownership_matches_the_selected_decision(
    decision, staff_draft, expected_code
):
    inventory = _inventory()
    items = inventory["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first["decision"] = decision
    first["staffDraftKey"] = staff_draft

    report = build_report(inventory)

    assert report["blockersByCode"] == {expected_code: 1}


def test_scheduled_time_must_name_its_timezone():
    inventory = _inventory()
    items = inventory["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first["scheduledFor"] = "2026-09-07T13:00:00"

    with pytest.raises(InvalidScheduledQueueInventory) as raised:
        build_report(inventory)

    assert raised.value.code == "scheduled_time_requires_timezone"


def test_unknown_payload_field_is_rejected_before_it_can_enter_report():
    inventory = _inventory()
    items = inventory["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first["payload"] = "private scheduled message"

    with pytest.raises(InvalidScheduledQueueInventory) as raised:
        build_report(inventory)

    assert raised.value.code == "invalid_item_fields"


def test_cli_writes_private_aggregate_report_and_fails_closed(tmp_path, capsys):
    report_path = tmp_path / "report.json"
    assert main(["--inventory", str(FIXTURE), "--report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ready"
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
    assert "ready (4 items, 0 blockers)" in capsys.readouterr().out

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"payload":"secret"}', encoding="utf-8")
    assert main(["--inventory", str(invalid_path), "--report", str(report_path)]) == 2
    invalid_report = report_path.read_text(encoding="utf-8")
    assert '"status": "invalid"' in invalid_report
    assert "secret" not in invalid_report

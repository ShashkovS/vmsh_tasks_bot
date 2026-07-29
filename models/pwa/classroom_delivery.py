"""Business rules for explicitly announcing confirmed classroom assignments."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from db_methods.pwa.classroom_delivery import (
    find_batch,
    find_batch_by_idempotency_key,
    find_confirmed_plan,
    find_latest_batch_for_event,
    find_retry_by_idempotency_key,
    insert_batch,
    insert_recipients,
    insert_delivery_retry,
    list_batch_recipients,
    list_previous_recipient_rooms,
    list_recipients,
    queue_failed_telegram_recipients,
    reopen_delivery_batch,
)
from db_methods.pwa.notifications import insert_event


class ClassroomDeliveryNotFound(Exception):
    pass


class ClassroomDeliveryConflict(Exception):
    pass


class InvalidClassroomDelivery(Exception):
    pass


def _delivery_source(
    connection: sqlite3.Connection,
    *,
    plan_public_id: str,
    expected_version: int | None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    plan = find_confirmed_plan(connection, plan_public_id)
    if plan is None:
        raise ClassroomDeliveryNotFound
    if plan["state"] != "confirmed":
        raise InvalidClassroomDelivery("plan_not_confirmed")
    if expected_version is not None and int(plan["version"]) != expected_version:
        raise ClassroomDeliveryConflict("plan_version_changed")

    recipients = list_recipients(connection, int(plan["id"]))
    for recipient in recipients:
        valid = (
            recipient["status"] == "assigned"
            and recipient["classroom_id"] is not None
            and recipient["classroom_status"] == "active"
            and recipient["enrollment_status"] == "active"
            and recipient["attendance_mode"] == "in_person"
            and recipient["active_group_id"] == recipient["group_id"]
        )
        if not valid:
            raise InvalidClassroomDelivery("plan_has_unavailable_recipient")
    return plan, recipients


def _snapshot_hash(plan: dict[str, object], recipients: list[dict[str, object]]) -> str:
    # Destination IDs stay server-side, but are hashed into the preview version so a
    # changed Telegram binding cannot silently reuse an older administrator preview.
    snapshot = {
        "plan": [plan["public_id"], plan["version"]],
        "recipients": [
            [
                item["course_enrollment_id"],
                item["student_user_id"],
                item["group_lesson_id"],
                item["classroom_id"],
                item["student_account_id"],
                item["telegram_chat_id"],
            ]
            for item in recipients
        ],
    }
    encoded = json.dumps(
        snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _changed_enrollments(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    recipients: list[dict[str, object]],
) -> set[int]:
    previous: dict[int, int] = {}
    for row in list_previous_recipient_rooms(connection, event_id):
        enrollment_id = int(row["course_enrollment_id"])
        previous.setdefault(enrollment_id, int(row["classroom_id"]))
    return {
        int(item["course_enrollment_id"])
        for item in recipients
        if previous.get(int(item["course_enrollment_id"])) != int(item["classroom_id"])
    }


def preview_classroom_delivery(
    connection: sqlite3.Connection,
    *,
    plan_public_id: str,
    expected_version: int | None = None,
) -> dict[str, object]:
    plan, recipients = _delivery_source(
        connection,
        plan_public_id=plan_public_id,
        expected_version=expected_version,
    )
    changed = _changed_enrollments(
        connection,
        event_id=int(plan["in_person_event_id"]),
        recipients=recipients,
    )
    return {
        "plan_public_id": plan["public_id"],
        "plan_version": plan["version"],
        "snapshot_hash": _snapshot_hash(plan, recipients),
        "recipient_count": len(recipients),
        "changed_count": len(changed),
        "pwa_unavailable_count": sum(
            item["student_account_id"] is None for item in recipients
        ),
        "telegram_unavailable_count": sum(
            item["telegram_chat_id"] is None for item in recipients
        ),
        "recipients": [
            {
                "student_public_id": item["student_public_id"],
                "student_display_name": f"{item['surname']} {item['name']}",
                "course_public_id": item["course_public_id"],
                "course_name": item["course_name"],
                "group_public_id": item["group_public_id"],
                "group_name": item["group_name"],
                "classroom_public_id": item["classroom_public_id"],
                "classroom_name": item["classroom_name"],
                "changed": int(item["course_enrollment_id"]) in changed,
                "pwa_available": item["student_account_id"] is not None,
                "telegram_available": item["telegram_chat_id"] is not None,
            }
            for item in recipients
        ],
    }


def read_classroom_delivery_batch(
    connection: sqlite3.Connection, batch_public_id: str
) -> dict[str, object]:
    batch = find_batch(connection, batch_public_id)
    if batch is None:
        raise ClassroomDeliveryNotFound
    recipients = list_batch_recipients(connection, int(batch["id"]))
    return {"batch": batch, "recipients": recipients}


def read_latest_classroom_delivery_batch(
    connection: sqlite3.Connection, plan_public_id: str
) -> dict[str, object] | None:
    batch = find_latest_batch_for_event(connection, plan_public_id)
    if batch is None:
        return None
    recipients = list_batch_recipients(connection, int(batch["id"]))
    return {"batch": batch, "recipients": recipients}


def create_classroom_delivery_batch(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    plan_public_id: str,
    expected_plan_version: int,
    expected_snapshot_hash: str,
    actor_user_id: int,
    pwa_selected: bool,
    telegram_selected: bool,
    idempotency_key: str,
    now: str,
) -> dict[str, object]:
    if not pwa_selected and not telegram_selected:
        raise InvalidClassroomDelivery("channel_required")

    existing = find_batch_by_idempotency_key(
        connection,
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        stored = read_classroom_delivery_batch(connection, str(existing["public_id"]))
        stored_batch = stored["batch"]
        same_request = (
            stored_batch["plan_public_id"] == plan_public_id
            and int(stored_batch["assignment_plan_version"]) == expected_plan_version
            and stored_batch["recipient_snapshot_hash"] == expected_snapshot_hash
            and bool(stored_batch["pwa_selected"]) is pwa_selected
            and bool(stored_batch["telegram_selected"]) is telegram_selected
        )
        if not same_request:
            raise ClassroomDeliveryConflict("idempotency_key_reused")
        return stored

    plan, recipients = _delivery_source(
        connection,
        plan_public_id=plan_public_id,
        expected_version=expected_plan_version,
    )
    actual_hash = _snapshot_hash(plan, recipients)
    if actual_hash != expected_snapshot_hash:
        raise ClassroomDeliveryConflict("preview_changed")
    changed = _changed_enrollments(
        connection,
        event_id=int(plan["in_person_event_id"]),
        recipients=recipients,
    )
    telegram_queued = telegram_selected and any(
        item["telegram_chat_id"] is not None for item in recipients
    )
    state = "queued" if telegram_queued else "completed"

    batch_id = insert_batch(
        connection,
        public_id=public_id,
        plan_id=int(plan["id"]),
        plan_version=int(plan["version"]),
        actor_user_id=actor_user_id,
        pwa_selected=pwa_selected,
        telegram_selected=telegram_selected,
        snapshot_hash=actual_hash,
        recipient_count=len(recipients),
        changed_count=len(changed),
        state=state,
        idempotency_key=idempotency_key,
        now=now,
    )
    insert_recipients(
        connection,
        (
            (
                batch_id,
                item["student_user_id"],
                item["course_enrollment_id"],
                item["group_lesson_id"],
                item["classroom_id"],
                item["student_public_id"],
                f"{item['surname']} {item['name']}",
                item["event_public_id"],
                item["event_name"],
                item["course_public_id"],
                item["course_name"],
                item["group_public_id"],
                item["group_name"],
                item["classroom_public_id"],
                item["classroom_name"],
                item["student_account_id"],
                item["telegram_chat_id"],
                (
                    "sent"
                    if pwa_selected and item["student_account_id"] is not None
                    else "suppressed"
                    if pwa_selected
                    else "not_requested"
                ),
                (
                    "student_account_unavailable"
                    if pwa_selected and item["student_account_id"] is None
                    else None
                ),
                now
                if pwa_selected and item["student_account_id"] is not None
                else None,
                (
                    "queued"
                    if telegram_selected and item["telegram_chat_id"] is not None
                    else "suppressed"
                    if telegram_selected
                    else "not_requested"
                ),
                (
                    "telegram_unavailable"
                    if telegram_selected and item["telegram_chat_id"] is None
                    else None
                ),
                None,
            )
            for item in recipients
        ),
    )
    if pwa_selected:
        for item in recipients:
            account_id = item["student_account_id"]
            if account_id is None:
                continue
            event_key = (
                f"classroom-assignment:{public_id}:{item['course_enrollment_id']}"
            )
            event_hash = hashlib.sha256(event_key.encode()).hexdigest()
            insert_event(
                connection,
                public_id=f"notification.{event_hash}",
                account_id=int(account_id),
                category="classroom_assignment",
                dedupe_key=event_key,
                route="/student/",
                payload_json=json.dumps(
                    {
                        "eventPublicId": item["event_public_id"],
                        "eventName": item["event_name"],
                        "coursePublicId": item["course_public_id"],
                        "courseName": item["course_name"],
                        "groupPublicId": item["group_public_id"],
                        "groupName": item["group_name"],
                        "classroomPublicId": item["classroom_public_id"],
                        "classroomName": item["classroom_name"],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                occurred_at=now,
                deliver_after=now,
                created_at=now,
            )
    result = read_classroom_delivery_batch(connection, public_id)
    result["student_user_ids"] = tuple(
        int(item["student_user_id"])
        for item in recipients
        if pwa_selected and item["student_account_id"] is not None
    )
    return result


def retry_failed_classroom_delivery(
    connection: sqlite3.Connection,
    *,
    batch_public_id: str,
    expected_batch_version: int,
    actor_user_id: int,
    idempotency_key: str,
    now: str,
) -> dict[str, object]:
    existing = find_retry_by_idempotency_key(
        connection,
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if existing["batch_public_id"] != batch_public_id:
            raise ClassroomDeliveryConflict("idempotency_key_reused")
        return read_classroom_delivery_batch(connection, batch_public_id)

    batch = find_batch(connection, batch_public_id)
    if batch is None:
        raise ClassroomDeliveryNotFound
    if int(batch["version"]) != expected_batch_version:
        raise ClassroomDeliveryConflict("batch_version_changed")

    recipient_count = queue_failed_telegram_recipients(connection, int(batch["id"]))
    if recipient_count == 0:
        raise InvalidClassroomDelivery("no_failed_recipients")
    insert_delivery_retry(
        connection,
        batch_id=int(batch["id"]),
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key,
        expected_batch_version=expected_batch_version,
        recipient_count=recipient_count,
        now=now,
    )
    reopen_delivery_batch(connection, int(batch["id"]))
    return read_classroom_delivery_batch(connection, batch_public_id)


__all__ = [
    "ClassroomDeliveryConflict",
    "ClassroomDeliveryNotFound",
    "InvalidClassroomDelivery",
    "create_classroom_delivery_batch",
    "preview_classroom_delivery",
    "read_classroom_delivery_batch",
    "read_latest_classroom_delivery_batch",
    "retry_failed_classroom_delivery",
]

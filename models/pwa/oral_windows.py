"""Small rules for configured oral-admission windows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse

from db_methods.pwa.notifications import (
    active_online_student_accounts_for_group,
    insert_event,
)
from db_methods.pwa.oral_windows import (
    due_notification_windows,
    group_lesson_scope,
    insert_window,
    list_windows,
    student_group_lesson_scope,
    student_join_window,
    update_window_row,
    window_by_public_id,
)


class OralWindowNotFound(Exception):
    pass


class OralWindowInvalid(Exception):
    pass


class OralWindowConflict(Exception):
    pass


class OralWindowClosed(Exception):
    pass


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _values(
    *,
    sequence_number: int,
    opens_at: datetime,
    closes_at: datetime,
    join_label: str,
    join_url: str,
    join_code: str | None,
    status: str,
) -> dict[str, object]:
    label = join_label.strip()
    url = join_url.strip()
    code = None if join_code is None else join_code.strip()
    parsed_url = urlparse(url)
    if (
        sequence_number < 1
        or opens_at >= closes_at
        or not label
        or parsed_url.scheme != "https"
        or not parsed_url.netloc
        or code == ""
        or status not in {"active", "cancelled"}
    ):
        raise OralWindowInvalid
    return {
        "sequence_number": sequence_number,
        "opens_at": _timestamp(opens_at),
        "closes_at": _timestamp(closes_at),
        "join_label": label,
        "join_url": url,
        "join_code": code,
        "status": status,
    }


def state_at(window: dict[str, object], now: datetime) -> str:
    if window["status"] == "cancelled":
        return "cancelled"
    current = _timestamp(now)
    if current < str(window["opens_at"]):
        return "upcoming"
    if current >= str(window["closes_at"]):
        return "closed"
    return "open"


def public_window(window: dict[str, object], now: datetime) -> dict[str, object]:
    state = state_at(window, now)
    return {
        "public_id": window["public_id"],
        "sequence_number": window["sequence_number"],
        "opens_at": window["opens_at"],
        "closes_at": window["closes_at"],
        "join_label": window["join_label"],
        "state": state,
        "join_available": state == "open",
        "version": window["version"],
    }


def create_due_window_notifications(
    connection: sqlite3.Connection,
    *,
    after: str | None,
    through: str,
) -> tuple[str, ...]:
    """Create Student events when configured oral windows actually open.

    Recipients are resolved at opening time, not when an admin edits the
    schedule. This keeps late attendance/group changes authoritative and avoids
    notifying in-person students. Zoom secrets never enter the event payload.
    See development-plan Phase 8 notification semantics.
    """

    notified_accounts: list[str] = []
    for window in due_notification_windows(connection, after=after, through=through):
        route = "/student/tasks?" + urlencode(
            {
                "course": str(window["course_public_id"]),
                "group": str(window["group_public_id"]),
                "lesson": int(window["lesson_number"]),
            }
        )
        payload = json.dumps(
            {
                "windowId": window["public_id"],
                "courseId": window["course_public_id"],
                "groupId": window["group_public_id"],
                "groupLessonId": window["group_lesson_public_id"],
                "lessonNumber": window["lesson_number"],
                "opensAt": window["opens_at"],
                "closesAt": window["closes_at"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for account in active_online_student_accounts_for_group(
            connection,
            course_id=int(window["course_id"]),
            group_id=str(window["group_id"]),
        ):
            if insert_event(
                connection,
                public_id=f"notification.oral.{uuid.uuid4().hex}",
                account_id=int(account["id"]),
                category="oral_window",
                dedupe_key=str(window["public_id"]),
                route=route,
                payload_json=payload,
                occurred_at=str(window["opens_at"]),
                deliver_after=str(window["opens_at"]),
                created_at=through,
            ):
                notified_accounts.append(str(account["public_id"]))
    return tuple(notified_accounts)


def create_window(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
    actor_user_id: int,
    now: datetime,
    sequence_number: int,
    opens_at: datetime,
    closes_at: datetime,
    join_label: str,
    join_url: str,
    join_code: str | None,
    status: str,
) -> dict[str, object]:
    scope = group_lesson_scope(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )
    if scope is None:
        raise OralWindowNotFound
    values = _values(
        sequence_number=sequence_number,
        opens_at=opens_at,
        closes_at=closes_at,
        join_label=join_label,
        join_url=join_url,
        join_code=join_code,
        status=status,
    )
    public_id = f"oral-window.{uuid.uuid4().hex}"
    try:
        insert_window(
            connection,
            public_id=public_id,
            group_lesson_id=int(scope["group_lesson_id"]),
            actor_user_id=actor_user_id,
            now=_timestamp(now),
            **values,
        )
    except sqlite3.IntegrityError as error:
        raise OralWindowConflict from error
    window = window_by_public_id(connection, public_id=public_id)
    if window is None:
        raise RuntimeError("created oral window is missing")
    return window


def update_window(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: datetime,
    sequence_number: int,
    opens_at: datetime,
    closes_at: datetime,
    join_label: str,
    join_url: str,
    join_code: str | None,
    status: str,
) -> dict[str, object]:
    if window_by_public_id(connection, public_id=public_id) is None:
        raise OralWindowNotFound
    values = _values(
        sequence_number=sequence_number,
        opens_at=opens_at,
        closes_at=closes_at,
        join_label=join_label,
        join_url=join_url,
        join_code=join_code,
        status=status,
    )
    try:
        updated = update_window_row(
            connection,
            public_id=public_id,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
            now=_timestamp(now),
            **values,
        )
    except sqlite3.IntegrityError as error:
        raise OralWindowConflict from error
    if not updated:
        raise OralWindowConflict
    window = window_by_public_id(connection, public_id=public_id)
    if window is None:
        raise RuntimeError("updated oral window is missing")
    return window


def student_windows(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
    group_lesson_public_id: str,
    now: datetime,
) -> list[dict[str, object]]:
    scope = student_group_lesson_scope(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
        group_lesson_public_id=group_lesson_public_id,
        at=_timestamp(now),
    )
    if scope is None:
        raise OralWindowNotFound
    return [
        public_window(window, now)
        for window in list_windows(
            connection,
            group_lesson_id=int(scope["group_lesson_id"]),
        )
    ]


def student_join_details(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    course_public_id: str,
    group_lesson_public_id: str,
    window_public_id: str,
    now: datetime,
) -> dict[str, object]:
    window = student_join_window(
        connection,
        account_id=account_id,
        course_public_id=course_public_id,
        group_lesson_public_id=group_lesson_public_id,
        window_public_id=window_public_id,
        at=_timestamp(now),
    )
    if window is None:
        raise OralWindowNotFound
    if state_at(window, now) != "open":
        raise OralWindowClosed
    return {
        "public_id": window["public_id"],
        "join_label": window["join_label"],
        "join_url": window["join_url"],
        "join_code": window["join_code"],
        "closes_at": window["closes_at"],
    }


__all__ = [
    "OralWindowClosed",
    "OralWindowConflict",
    "OralWindowInvalid",
    "OralWindowNotFound",
    "create_due_window_notifications",
    "create_window",
    "public_window",
    "state_at",
    "student_join_details",
    "student_windows",
    "update_window",
]

"""Explicit one-per-group-lesson notification for linked Family accounts."""

from __future__ import annotations

import json
import sqlite3

from db_methods.pwa.audit import insert_audit_event
from db_methods.pwa.family_digest import (
    find_group_lesson,
    list_group_family_accounts,
    list_group_students,
)
from db_methods.pwa.notifications import insert_event


class FamilyDigestLessonNotFound(Exception):
    pass


class FamilyDigestLessonNotActive(Exception):
    pass


def _dedupe_key(group_lesson_public_id: str) -> str:
    return f"family-digest:{group_lesson_public_id}"


def _preview(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object]:
    lesson = find_group_lesson(connection, public_id=group_lesson_public_id)
    if lesson is None:
        raise FamilyDigestLessonNotFound
    if lesson["status"] != "active":
        raise FamilyDigestLessonNotActive

    students = list_group_students(
        connection,
        course_id=int(lesson["course_id"]),
        group_id=str(lesson["group_id"]),
    )
    family_rows = list_group_family_accounts(
        connection,
        course_id=int(lesson["course_id"]),
        group_id=str(lesson["group_id"]),
        dedupe_key=_dedupe_key(group_lesson_public_id),
    )

    families: dict[int, dict[str, object]] = {}
    linked_student_ids: set[str] = set()
    for row in family_rows:
        student_public_id = str(row["student_public_id"])
        linked_student_ids.add(student_public_id)
        account_id = int(row["account_id"])
        family = families.setdefault(
            account_id,
            {
                "account_id": account_id,
                "account_public_id": str(row["account_public_id"]),
                "display_name": str(row["display_name"]),
                "student_ids": [],
                "sent_at": row["sent_at"],
            },
        )
        student_ids = family["student_ids"]
        assert isinstance(student_ids, list)
        if student_public_id not in student_ids:
            student_ids.append(student_public_id)

    unlinked_students = [
        {
            "studentId": str(student["public_id"]),
            "displayName": str(student["display_name"]),
        }
        for student in students
        if str(student["public_id"]) not in linked_student_ids
    ]
    sent_count = sum(family["sent_at"] is not None for family in families.values())
    return {
        "groupLessonId": lesson["public_id"],
        "courseId": lesson["course_public_id"],
        "courseName": lesson["course_name"],
        "groupId": lesson["group_public_id"],
        "groupName": lesson["group_name"],
        "lessonNumber": lesson["lesson_number"],
        "studentCount": len(students),
        "familyCount": len(families),
        "alreadySentFamilyCount": sent_count,
        "pendingFamilyCount": len(families) - sent_count,
        "unlinkedStudents": unlinked_students,
        "families": list(families.values()),
    }


def preview_family_digest(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object]:
    """Return current recipients without writing any notification state."""

    return _preview(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )


def send_family_digest(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
    actor_user_id: int,
    actor_account_public_id: str,
    request_id: str,
    now: str,
) -> dict[str, object]:
    """Create only missing Family events for one explicit admin action.

    The per-account notification uniqueness is the durable send marker.  A
    later explicit retry can therefore reach a newly linked Family account
    without repeating the digest for accounts that already received it.  See
    development-plan/12-phase-8-news-and-notifications.md.
    """

    preview = _preview(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )
    created_account_ids: list[str] = []
    dedupe_key = _dedupe_key(group_lesson_public_id)
    payload_base = {
        "kind": "family_lesson_digest",
        "courseId": preview["courseId"],
        "courseName": preview["courseName"],
        "groupId": preview["groupId"],
        "groupName": preview["groupName"],
        "groupLessonId": preview["groupLessonId"],
        "lessonNumber": preview["lessonNumber"],
    }
    families = preview.pop("families")
    assert isinstance(families, list)
    for family in families:
        assert isinstance(family, dict)
        if family["sent_at"] is not None:
            continue
        student_ids = family["student_ids"]
        assert isinstance(student_ids, list) and student_ids
        if insert_event(
            connection,
            account_id=int(family["account_id"]),
            category="review_completed",
            dedupe_key=dedupe_key,
            route=f"/family/children/{student_ids[0]}",
            payload_json=json.dumps(
                {**payload_base, "studentIds": student_ids},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=now,
            deliver_after=now,
            created_at=now,
        ):
            created_account_ids.append(str(family["account_public_id"]))

    if created_account_ids:
        insert_audit_event(
            connection,
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_public_id,
            audience="staff",
            action="family_digest.sent",
            object_type="group_lesson",
            object_id=group_lesson_public_id,
            request_id=request_id,
            before_json=None,
            after_json=json.dumps(
                {
                    "createdFamilyCount": len(created_account_ids),
                    "eligibleFamilyCount": preview["familyCount"],
                    "groupId": preview["groupId"],
                    "lessonNumber": preview["lessonNumber"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=now,
        )

    current = _preview(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )
    current.pop("families")
    return {
        "digest": current,
        "createdFamilyCount": len(created_account_ids),
        "createdAccountPublicIds": tuple(created_account_ids),
    }


__all__ = [
    "FamilyDigestLessonNotActive",
    "FamilyDigestLessonNotFound",
    "preview_family_digest",
    "send_family_digest",
]

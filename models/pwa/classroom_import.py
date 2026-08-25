"""Validate and apply the one-time classroom Excel export."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from collections import Counter, defaultdict

from db_methods.pwa.classroom_assignments import (
    find_plan,
    insert_plan,
    replace_assignments,
)
from db_methods.pwa.classroom_imports import (
    existing_user_ids,
    find_import_receipt,
    insert_import_receipt,
)
from db_methods.pwa.classroom_layouts import (
    find_event_layout,
    get_in_person_event,
    list_event_group_lessons,
)
from db_methods.pwa.classrooms import (
    create_classroom,
    find_classroom_by_normalized_name,
    get_classroom,
)
from db_methods.pwa.classroom_assignments import list_eligible_students
from models.pwa.classroom_assignments import confirm_assignment_plan
from models.pwa.classroom_layouts import (
    confirm_layout,
    materialize_layout,
    replace_draft_layout,
)


class ClassroomImportRejected(ValueError):
    pass


def _key(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value).strip()).casefold()


def _preview_hash(report: dict[str, object], plan: dict[str, object]) -> str:
    payload = json.dumps(
        {"report": report, "plan": plan},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def analyze_classroom_import(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    source_sha256: str,
    source_sheet: str,
    header_row: int,
    rows: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    event = get_in_person_event(connection, event_public_id)
    if event is None:
        raise ClassroomImportRejected("Unknown in-person event")
    event_id = int(event["id"])
    group_lessons = list_event_group_lessons(connection, event_id)
    eligible = list_eligible_students(connection, event_id)
    receipt = find_import_receipt(connection, event_id)

    aliases: dict[str, list[dict[str, object]]] = defaultdict(list)
    for group in group_lessons:
        for value in (
            group["group_id"],
            group["group_public_id"],
            group["group_name"],
            group["short_code"],
        ):
            normalized = _key(value)
            if group not in aliases[normalized]:
                aliases[normalized].append(group)

    eligible_by_user: dict[int, list[dict[str, object]]] = defaultdict(list)
    for student in eligible:
        eligible_by_user[int(student["student_user_id"])].append(student)

    parsed_ids = {
        int(row["user_id"]) for row in rows if isinstance(row["user_id"], int)
    }
    known_ids = existing_user_ids(connection, parsed_ids)
    duplicate_ids = sorted(
        user_id
        for user_id, count in Counter(
            int(row["user_id"]) for row in rows if isinstance(row["user_id"], int)
        ).items()
        if count > 1
    )
    ambiguous_eligible_ids = sorted(
        user_id for user_id, matches in eligible_by_user.items() if len(matches) > 1
    )

    invalid_student_rows: list[int] = []
    unknown_student_ids: set[int] = set()
    ineligible_student_ids: set[int] = set()
    empty_room_student_ids: set[int] = set()
    unknown_group_labels: set[str] = set()
    ambiguous_group_labels: set[str] = set()
    student_group_mismatches: set[int] = set()
    room_names: dict[str, set[str]] = defaultdict(set)
    room_groups: dict[str, set[int]] = defaultdict(set)
    room_display: dict[str, str] = {}
    assignments: list[dict[str, object]] = []

    for row in rows:
        group_label = str(row["group_label"])
        group_matches = aliases.get(_key(group_label), [])
        if not group_matches:
            unknown_group_labels.add(group_label)
        elif len(group_matches) != 1:
            ambiguous_group_labels.add(group_label)

        room_key = str(row["room_key"])
        if room_key:
            room_name = str(row["room_name"])
            room_names[room_key].add(room_name)
            room_display.setdefault(room_key, room_name)
            if len(group_matches) == 1:
                room_groups[room_key].add(int(group_matches[0]["group_lesson_id"]))

        user_id = row["user_id"]
        if not isinstance(user_id, int):
            invalid_student_rows.append(int(row["row_number"]))
            continue
        if user_id not in known_ids:
            unknown_student_ids.add(user_id)
            continue
        matches = eligible_by_user.get(user_id, [])
        if len(matches) != 1:
            ineligible_student_ids.add(user_id)
            continue
        if not group_matches:
            continue
        if len(group_matches) != 1:
            continue
        group = group_matches[0]
        student = matches[0]
        if int(group["group_lesson_id"]) != int(student["group_lesson_id"]):
            student_group_mismatches.add(user_id)
            continue

        if not room_key:
            empty_room_student_ids.add(user_id)
            continue
        assignments.append(
            {
                "user_id": user_id,
                "enrollment_id": int(student["enrollment_id"]),
                "group_lesson_id": int(group["group_lesson_id"]),
                "group_lesson_public_id": str(group["group_lesson_public_id"]),
                "group_id": str(group["group_id"]),
                "room_key": room_key,
            }
        )

    normalized_room_aliases = sorted(
        room_display[key] for key, names in room_names.items() if len(names) > 1
    )
    mixed_group_rooms = sorted(
        room_display[key] for key, groups in room_groups.items() if len(groups) > 1
    )
    archived_rooms = sorted(
        room_display[key]
        for key in room_display
        if (existing := find_classroom_by_normalized_name(connection, key)) is not None
        and existing["status"] != "active"
    )
    assigned_ids = {int(item["user_id"]) for item in assignments}
    missing_eligible_ids = sorted(set(eligible_by_user) - assigned_ids)

    has_event_data = (
        find_event_layout(connection, event_id, "draft") is not None
        or find_event_layout(connection, event_id, "confirmed") is not None
        or find_plan(connection, event_id, ("draft", "stale", "confirmed")) is not None
    )
    blockers = {
        "invalidStudentRows": sorted(invalid_student_rows),
        "duplicateStudentIds": duplicate_ids,
        "unknownStudentIds": sorted(unknown_student_ids),
        "ineligibleStudentIds": sorted(ineligible_student_ids),
        "ambiguousEligibleStudentIds": ambiguous_eligible_ids,
        "unknownGroupLabels": sorted(unknown_group_labels),
        "ambiguousGroupLabels": sorted(ambiguous_group_labels),
        "studentGroupMismatches": sorted(student_group_mismatches),
        "emptyRoomStudentIds": sorted(empty_room_student_ids),
        "normalizedRoomAliases": normalized_room_aliases,
        "mixedGroupRooms": mixed_group_rooms,
        "archivedRooms": archived_rooms,
        "missingEligibleStudentIds": missing_eligible_ids,
    }
    has_blockers = any(blockers.values()) or not rows
    event_already_initialized = has_event_data and receipt is None

    rooms = [
        {
            "name": room_display[room_key],
            "key": room_key,
            "group_lesson_id": next(iter(room_groups[room_key])),
        }
        for room_key in sorted(room_display)
        if len(room_names[room_key]) == 1 and len(room_groups[room_key]) == 1
    ]
    assignments.sort(key=lambda item: (int(item["user_id"]), str(item["room_key"])))
    plan = {"rooms": rooms, "assignments": assignments}
    report: dict[str, object] = {
        "schemaVersion": 1,
        "purpose": "phase7-classroom-excel-import",
        "eventPublicId": event_public_id,
        "sourceSheet": source_sheet,
        "sourceSha256": source_sha256,
        "headerRow": header_row,
        "counts": {
            "sourceRows": len(rows),
            "uniqueValidStudentIds": len(parsed_ids),
            "eligibleStudents": len(eligible),
            "proposedClassrooms": len(rooms),
            "proposedAssignments": len(assignments),
        },
        "issues": blockers,
        "eventAlreadyInitialized": event_already_initialized,
        "alreadyApplied": receipt is not None,
        "canApply": not has_blockers and not event_already_initialized,
    }
    report["previewSha256"] = _preview_hash(report, plan)
    return report, plan


def apply_classroom_import(
    connection: sqlite3.Connection,
    *,
    event_public_id: str,
    source_sha256: str,
    source_sheet: str,
    header_row: int,
    rows: list[dict[str, object]],
    confirmed_source_sha256: str,
    confirmed_preview_sha256: str,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    event = get_in_person_event(connection, event_public_id)
    if event is None:
        raise ClassroomImportRejected("Unknown in-person event")
    event_id = int(event["id"])
    receipt = find_import_receipt(connection, event_id)
    if receipt is not None:
        if (
            receipt["source_sha256"] == source_sha256
            and receipt["source_sha256"] == confirmed_source_sha256
            and receipt["preview_sha256"] == confirmed_preview_sha256
        ):
            return {**receipt, "replayed": True}
        raise ClassroomImportRejected("This event already has a different import")

    report, plan = analyze_classroom_import(
        connection,
        event_public_id=event_public_id,
        source_sha256=source_sha256,
        source_sheet=source_sheet,
        header_row=header_row,
        rows=rows,
    )
    if source_sha256 != confirmed_source_sha256:
        raise ClassroomImportRejected("The Excel source hash was not confirmed")
    if report["previewSha256"] != confirmed_preview_sha256:
        raise ClassroomImportRejected("The dry-run preview hash was not confirmed")

    if not report["canApply"]:
        raise ClassroomImportRejected("The dry-run contains blocking issues")

    request_id = f"classroom-import:{source_sha256[:16]}"
    room_ids: dict[str, int] = {}
    room_public_ids: dict[str, str] = {}
    for room in plan["rooms"]:
        room_key = str(room["key"])
        existing = find_classroom_by_normalized_name(connection, room_key)
        if existing is None:
            created = create_classroom(
                connection,
                name=str(room["name"]),
                normalized_name=room_key,
                actor_user_id=actor_user_id,
                request_id=request_id,
                now=now,
            )
            public_id = str(created["public_id"])
        else:
            public_id = str(existing["public_id"])
        stored = get_classroom(connection, public_id)
        assert stored is not None
        room_ids[room_key] = int(stored["id"])
        room_public_ids[room_key] = public_id

    draft_layout = materialize_layout(
        connection,
        event_public_id=event_public_id,
        actor_user_id=actor_user_id,
        now=now,
    )
    layout_public_id = str(draft_layout["layout_public_id"])
    group_public_ids = {
        int(group["group_lesson_id"]): str(group["group_lesson_public_id"])
        for group in list_event_group_lessons(connection, event_id)
    }
    replaced_layout = replace_draft_layout(
        connection,
        event_public_id=event_public_id,
        layout_public_id=layout_public_id,
        expected_version=1,
        mappings=[
            (
                room_public_ids[str(room["key"])],
                group_public_ids[int(room["group_lesson_id"])],
            )
            for room in plan["rooms"]
        ],
        now=now,
    )
    confirm_layout(
        connection,
        event_public_id=event_public_id,
        layout_public_id=layout_public_id,
        expected_version=int(replaced_layout["version"]),
        actor_user_id=actor_user_id,
        now=now,
    )
    layout = find_event_layout(connection, event_id, "confirmed")
    assert layout is not None

    plan_id, plan_public_id = insert_plan(
        connection,
        event_id=event_id,
        layout_id=int(layout["id"]),
        base_plan_id=None,
        actor_user_id=actor_user_id,
        now=now,
    )
    replace_assignments(
        connection,
        plan_id=plan_id,
        rows=(
            (
                int(item["enrollment_id"]),
                int(item["group_lesson_id"]),
                str(item["group_id"]),
                room_ids[str(item["room_key"])],
                "assigned",
                "import",
            )
            for item in plan["assignments"]
        ),
        now=now,
    )
    confirmed_plan = confirm_assignment_plan(
        connection,
        event_public_id=event_public_id,
        plan_public_id=plan_public_id,
        expected_version=1,
        actor_user_id=actor_user_id,
        now=now,
    )
    plan_row = find_plan(connection, event_id, ("confirmed",))
    assert plan_row is not None

    insert_import_receipt(
        connection,
        event_id=event_id,
        source_sha256=source_sha256,
        preview_sha256=confirmed_preview_sha256,
        source_sheet=source_sheet,
        source_row_count=len(rows),
        classroom_count=len(plan["rooms"]),
        assignment_count=len(plan["assignments"]),
        layout_id=int(layout["id"]),
        plan_id=int(plan_row["id"]),
        actor_user_id=actor_user_id,
        applied_at=now,
    )
    receipt = find_import_receipt(connection, event_id)
    assert receipt is not None
    return {**receipt, "replayed": False, "planState": confirmed_plan["plan"]["state"]}


__all__ = [
    "ClassroomImportRejected",
    "analyze_classroom_import",
    "apply_classroom_import",
]

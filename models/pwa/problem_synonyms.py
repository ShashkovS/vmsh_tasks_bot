"""Business rules for logical problem synonym merge and split.

Product rules: ``vmshpwa/docs/courses-groups-and-lessons.md``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

from db_methods.pwa.problem_synonyms import (
    course_lesson_exists,
    find_problems,
    find_synonym_group,
    insert_synonym_group,
    insert_synonym_member,
    list_course_lesson_problems,
    list_synonym_problem_ids,
    remove_synonym_member,
    update_synonym_group,
)


class ProblemSynonymError(ValueError):
    pass


def _fail(code: str) -> None:
    raise ProblemSynonymError(code)


def _load_problems(
    connection: sqlite3.Connection, public_ids: tuple[str, ...]
) -> list[dict[str, object]]:
    if not 1 <= len(public_ids) <= 50 or len(set(public_ids)) != len(public_ids):
        _fail("problem_selection_invalid")
    found = {
        str(row["problem_public_id"]): row
        for row in find_problems(connection, public_ids)
    }
    if len(found) != len(public_ids):
        _fail("problem_not_found")
    return [found[public_id] for public_id in public_ids]


def _structural_hash(
    *,
    mode: str,
    selected_ids: tuple[str, ...],
    rows: list[dict[str, object]],
    synonym: dict[str, object] | None,
) -> str:
    payload = {
        "mode": mode,
        "selected": selected_ids,
        "synonym": None
        if synonym is None
        else {
            "publicId": synonym["public_id"],
            "status": synonym["status"],
            "version": synonym["version"],
        },
        "problems": [
            {
                "problemId": row["problem_public_id"],
                "courseLessonId": row["course_lesson_public_id"],
                "groupLessonId": row["group_lesson_public_id"],
                "synonymId": row["synonym_public_id"],
                "membershipVersion": row["membership_version"],
            }
            for row in rows
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_one_course_lesson(rows: list[dict[str, object]]) -> None:
    if len({row["course_lesson_id"] for row in rows}) != 1:
        _fail("course_lesson_mismatch")


def synonym_candidates(
    connection: sqlite3.Connection, *, course_lesson_public_id: str
) -> list[dict[str, object]]:
    rows = list_course_lesson_problems(
        connection, course_lesson_public_id=course_lesson_public_id
    )
    if not rows and not course_lesson_exists(
        connection, course_lesson_public_id=course_lesson_public_id
    ):
        _fail("course_lesson_not_found")
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["normalized_title"]), []).append(row)
    candidates: list[dict[str, object]] = []
    for normalized_title, members in sorted(grouped.items()):
        if len({member["group_lesson_id"] for member in members}) < 2:
            continue
        active_groups = {member["synonym_public_id"] for member in members}
        if len(active_groups) == 1 and None not in active_groups:
            continue
        candidates.append(
            {
                "normalized_title": normalized_title,
                "display_title": members[0]["title"],
                "has_group_conflict": len(members)
                != len({member["group_lesson_id"] for member in members}),
                "problems": members,
            }
        )
    return candidates


def active_synonym_groups(
    connection: sqlite3.Connection, *, course_lesson_public_id: str
) -> list[dict[str, object]]:
    rows = list_course_lesson_problems(
        connection, course_lesson_public_id=course_lesson_public_id
    )
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if row["synonym_status"] == "active":
            grouped.setdefault(str(row["synonym_public_id"]), []).append(row)
    return [
        {
            "synonym_public_id": synonym_id,
            "display_title": members[0]["synonym_display_title"],
            "version": members[0]["synonym_version"],
            "problems": members,
        }
        for synonym_id, members in sorted(grouped.items())
    ]


def preview_synonym_merge(
    connection: sqlite3.Connection, *, problem_public_ids: tuple[str, ...]
) -> dict[str, object]:
    if len(problem_public_ids) < 2:
        _fail("problem_selection_invalid")
    selected = _load_problems(connection, problem_public_ids)
    _require_one_course_lesson(selected)
    if any(
        row["synonym_member_id"] is not None and row["synonym_status"] != "active"
        for row in selected
    ):
        _fail("synonym_state_invalid")
    active_ids = {
        str(row["synonym_public_id"])
        for row in selected
        if row["synonym_public_id"] is not None
    }
    if len(active_ids) > 1:
        _fail("different_synonym_groups")

    synonym = None
    effective = selected
    if active_ids:
        synonym = find_synonym_group(connection, public_id=next(iter(active_ids)))
        if synonym is None or synonym["status"] != "active":
            _fail("synonym_state_invalid")
        existing_ids = list_synonym_problem_ids(
            connection, synonym_group_id=int(synonym["id"])
        )
        combined_ids = tuple(dict.fromkeys((*existing_ids, *problem_public_ids)))
        effective = _load_problems(connection, combined_ids)

    _require_one_course_lesson(effective)
    if len({row["group_lesson_id"] for row in effective}) != len(effective):
        _fail("group_lesson_duplicate")
    additions = [row for row in effective if row["synonym_public_id"] is None]
    preview_sha256 = _structural_hash(
        mode="merge",
        selected_ids=problem_public_ids,
        rows=effective,
        synonym=synonym,
    )
    return {
        "mode": "merge",
        "synonym": synonym,
        "selected_problem_ids": problem_public_ids,
        "problems": effective,
        "additions": additions,
        "removals": [],
        "preview_sha256": preview_sha256,
    }


def merge_problem_synonyms(
    connection: sqlite3.Connection,
    *,
    problem_public_ids: tuple[str, ...],
    preview_sha256: str,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    plan = preview_synonym_merge(connection, problem_public_ids=problem_public_ids)
    if plan["preview_sha256"] != preview_sha256:
        _fail("preview_changed")
    synonym = plan["synonym"]
    additions = plan["additions"]
    assert isinstance(additions, list)
    if synonym is None:
        public_id = f"problem-synonym.{uuid.uuid4().hex}"
        group_id = insert_synonym_group(
            connection,
            public_id=public_id,
            course_lesson_id=int(plan["problems"][0]["course_lesson_id"]),
            group_key=public_id,
            display_title=str(plan["problems"][0]["title"]),
            actor_user_id=actor_user_id,
            now=now,
        )
        version = 1
        additions = plan["problems"]
        changed = True
    else:
        public_id = str(synonym["public_id"])
        group_id = int(synonym["id"])
        version = int(synonym["version"])
        changed = bool(additions)

    for row in additions:
        insert_synonym_member(
            connection,
            synonym_group_id=group_id,
            group_lesson_id=int(row["group_lesson_id"]),
            problem_id=int(row["problem_id"]),
            actor_user_id=actor_user_id,
            now=now,
        )
    if synonym is not None and additions:
        if not update_synonym_group(
            connection,
            group_id=group_id,
            expected_version=version,
            status="active",
            now=now,
        ):
            _fail("version_conflict")
        version += 1
    return {
        **plan,
        "synonym_public_id": public_id,
        "synonym_version": version,
        "synonym_status": "active",
        "changed": changed,
    }


def preview_synonym_split(
    connection: sqlite3.Connection,
    *,
    synonym_public_id: str,
    problem_public_ids: tuple[str, ...],
) -> dict[str, object]:
    synonym = find_synonym_group(connection, public_id=synonym_public_id)
    if synonym is None:
        _fail("synonym_not_found")
    if synonym["status"] != "active":
        _fail("synonym_state_invalid")
    selected_ids = tuple(dict.fromkeys(problem_public_ids))
    if not selected_ids or len(selected_ids) != len(problem_public_ids):
        _fail("problem_selection_invalid")
    active_ids = list_synonym_problem_ids(
        connection, synonym_group_id=int(synonym["id"])
    )
    if not set(selected_ids).issubset(active_ids):
        _fail("problem_not_in_synonym")
    rows = _load_problems(connection, active_ids)
    remaining_ids = [
        public_id for public_id in active_ids if public_id not in selected_ids
    ]
    removal_ids = set(selected_ids)
    if len(remaining_ids) == 1:
        removal_ids.add(remaining_ids[0])
        remaining_ids = []
    removals = [row for row in rows if row["problem_public_id"] in removal_ids]
    preview_sha256 = _structural_hash(
        mode="split",
        selected_ids=selected_ids,
        rows=rows,
        synonym=synonym,
    )
    return {
        "mode": "split",
        "synonym": synonym,
        "selected_problem_ids": selected_ids,
        "problems": rows,
        "additions": [],
        "removals": removals,
        "remaining_problem_ids": tuple(remaining_ids),
        "preview_sha256": preview_sha256,
    }


def split_problem_synonyms(
    connection: sqlite3.Connection,
    *,
    synonym_public_id: str,
    problem_public_ids: tuple[str, ...],
    preview_sha256: str,
    reason: str,
    actor_user_id: int,
    now: str,
) -> dict[str, object]:
    plan = preview_synonym_split(
        connection,
        synonym_public_id=synonym_public_id,
        problem_public_ids=problem_public_ids,
    )
    if plan["preview_sha256"] != preview_sha256:
        _fail("preview_changed")
    removals = plan["removals"]
    assert isinstance(removals, list)
    for row in removals:
        remove_synonym_member(
            connection,
            member_id=int(row["synonym_member_id"]),
            actor_user_id=actor_user_id,
            reason=reason,
            now=now,
        )
    synonym = plan["synonym"]
    assert isinstance(synonym, dict)
    status = "active" if plan["remaining_problem_ids"] else "split"
    if not update_synonym_group(
        connection,
        group_id=int(synonym["id"]),
        expected_version=int(synonym["version"]),
        status=status,
        now=now,
    ):
        _fail("version_conflict")
    return {
        **plan,
        "synonym_public_id": synonym_public_id,
        "synonym_version": int(synonym["version"]) + 1,
        "synonym_status": status,
        "changed": True,
    }


__all__ = [
    "ProblemSynonymError",
    "active_synonym_groups",
    "merge_problem_synonyms",
    "preview_synonym_merge",
    "preview_synonym_split",
    "split_problem_synonyms",
    "synonym_candidates",
]

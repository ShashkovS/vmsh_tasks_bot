"""Apply and roll back a reviewed problem-workbook preview."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections import Counter

from db_methods.pwa.problem_imports import (
    PROBLEM_FIELDS,
    delete_problem,
    find_course,
    find_import_receipt_by_preview,
    find_problem,
    get_import_receipt,
    insert_import_receipt,
    insert_problem,
    list_course_groups,
    list_course_problems,
    mark_import_rolled_back,
    update_problem,
)
from db_methods.pwa.audit import insert_audit_event
from models.pwa.problem_import import compare_problem_rows, problem_import_preview_hash


def _problem_values(row: dict[str, object]) -> dict[str, object]:
    return {
        "group_id": row["group_id"],
        "lesson": row["lesson"],
        "prob": row["problem"],
        "item": row["item"],
        "title": row["title"],
        "prob_text": row["problem_text"],
        "prob_type": row["problem_type"],
        "ans_type": row["answer_type"],
        "ans_validation": row["answer_validation"],
        "validation_error": row["validation_error"],
        "cor_ans": row["correct_answer"],
        "cor_ans_checker": row["correct_answer_checker"],
        "wrong_ans": row["wrong_answer"],
        "congrat": row["congratulation"],
    }


def _snapshot(row: dict[str, object]) -> dict[str, object]:
    return {
        "public_id": row["public_id"],
        **{field: row[field] for field in PROBLEM_FIELDS},
    }


def _receipt_payload(
    receipt: dict[str, object], *, replayed: bool
) -> dict[str, object]:
    return {
        "public_id": receipt["public_id"],
        "state": receipt["state"],
        "source_filename": receipt["source_filename"],
        "source_sha256": receipt["source_sha256"],
        "preview_sha256": receipt["preview_sha256"],
        "summary": json.loads(str(receipt["summary_json"])),
        "applied_at": receipt["applied_at"],
        "rolled_back_at": receipt["rolled_back_at"],
        "version": receipt["version"],
        "replayed": replayed,
    }


def apply_problem_import(
    connection: sqlite3.Connection,
    *,
    course_public_id: str,
    parsed_rows: list[dict[str, object]],
    source_filename: str,
    source_sha256: str,
    confirmed_source_sha256: str,
    confirmed_preview_sha256: str,
    actor_user_id: int,
    now: str,
    request_id: str | None = None,
    actor_account_public_id: str | None = None,
) -> dict[str, object]:
    course = find_course(connection, public_id=course_public_id)
    if course is None:
        raise ValueError("course_not_found")
    course_id = int(course["id"])
    if source_sha256 != confirmed_source_sha256:
        raise ValueError("source_changed")
    previous_receipt = find_import_receipt_by_preview(
        connection,
        course_id=course_id,
        source_sha256=source_sha256,
        preview_sha256=confirmed_preview_sha256,
    )
    if previous_receipt is not None:
        if previous_receipt["state"] != "applied":
            raise ValueError("import_already_rolled_back")
        return _receipt_payload(previous_receipt, replayed=True)

    compared = compare_problem_rows(
        parsed_rows,
        list_course_groups(connection, course_id=course_id),
        list_course_problems(connection, course_id=course_id),
    )
    preview_sha256 = problem_import_preview_hash(
        course_public_id, source_sha256, compared
    )
    if preview_sha256 != confirmed_preview_sha256:
        raise ValueError("preview_changed")

    changes: list[dict[str, object]] = []
    for row in compared:
        if row["action"] == "create":
            stored = insert_problem(connection, _problem_values(row))
            changes.append(
                {"action": "create", "before": None, "after": _snapshot(stored)}
            )
        elif row["action"] == "update":
            public_id = str(row["problem_public_id"])
            stored = find_problem(connection, public_id=public_id)
            if stored is None:
                raise ValueError("preview_changed")
            before = _snapshot(stored)
            update_problem(
                connection,
                problem_id=int(stored["id"]),
                values=_problem_values(row),
            )
            changed = find_problem(connection, public_id=public_id)
            assert changed is not None
            changes.append(
                {"action": "update", "before": before, "after": _snapshot(changed)}
            )

    counts = Counter(str(row["action"]) for row in compared)
    summary = {
        "rows": len(compared),
        "created": counts["create"],
        "updated": counts["update"],
        "unchanged": counts["unchanged"],
        "skippedInvalid": counts["invalid"],
    }
    public_id = f"problem-import.{uuid.uuid4().hex}"
    insert_import_receipt(
        connection,
        public_id=public_id,
        course_id=course_id,
        source_filename=source_filename,
        source_sha256=source_sha256,
        preview_sha256=preview_sha256,
        summary_json=json.dumps(summary, separators=(",", ":")),
        changes_json=json.dumps(changes, ensure_ascii=False, separators=(",", ":")),
        actor_user_id=actor_user_id,
        applied_at=now,
    )
    receipt = get_import_receipt(connection, public_id=public_id)
    assert receipt is not None
    if request_id is not None and actor_account_public_id is not None:
        insert_audit_event(
            connection,
            public_id=f"audit.{uuid.uuid4().hex}",
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_public_id,
            audience="staff",
            action="problem_import.applied",
            object_type="problem_import",
            object_id=public_id,
            request_id=request_id,
            before_json=None,
            after_json=json.dumps(
                {
                    "courseId": course_public_id,
                    "created": summary["created"],
                    "rows": summary["rows"],
                    "sourceFilename": source_filename,
                    "state": "applied",
                    "updated": summary["updated"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            occurred_at=now,
        )
    return _receipt_payload(receipt, replayed=False)


def rollback_problem_import(
    connection: sqlite3.Connection,
    *,
    receipt_public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: str,
    request_id: str | None = None,
    actor_account_public_id: str | None = None,
) -> dict[str, object]:
    receipt = get_import_receipt(connection, public_id=receipt_public_id)
    if receipt is None:
        raise ValueError("import_not_found")
    if receipt["state"] == "rolled_back":
        if expected_version in {int(receipt["version"]) - 1, int(receipt["version"])}:
            return _receipt_payload(receipt, replayed=True)
        raise ValueError("import_version_changed")
    if int(receipt["version"]) != expected_version:
        raise ValueError("import_version_changed")

    changes = json.loads(str(receipt["changes_json"]))
    if not isinstance(changes, list):
        raise ValueError("invalid_import_receipt")
    for change in reversed(changes):
        after = change["after"]
        current = find_problem(connection, public_id=str(after["public_id"]))
        if current is None or _snapshot(current) != after:
            raise ValueError("import_result_changed")
        if change["action"] == "create":
            try:
                delete_problem(connection, problem_id=int(current["id"]))
            except sqlite3.IntegrityError as error:
                raise ValueError("import_result_in_use") from error
        else:
            before = change["before"]
            update_problem(
                connection,
                problem_id=int(current["id"]),
                values={field: before[field] for field in PROBLEM_FIELDS},
            )

    if not mark_import_rolled_back(
        connection,
        receipt_id=int(receipt["id"]),
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        rolled_back_at=now,
    ):
        raise ValueError("import_version_changed")
    rolled_back = get_import_receipt(connection, public_id=receipt_public_id)
    assert rolled_back is not None
    if request_id is not None and actor_account_public_id is not None:
        insert_audit_event(
            connection,
            public_id=f"audit.{uuid.uuid4().hex}",
            actor_user_id=actor_user_id,
            actor_account_public_id=actor_account_public_id,
            audience="staff",
            action="problem_import.rolled_back",
            object_type="problem_import",
            object_id=receipt_public_id,
            request_id=request_id,
            before_json=json.dumps(
                {"state": "applied", "version": expected_version},
                separators=(",", ":"),
            ),
            after_json=json.dumps(
                {"state": "rolled_back", "version": rolled_back["version"]},
                separators=(",", ":"),
            ),
            occurred_at=now,
        )
    return _receipt_payload(rolled_back, replayed=False)


__all__ = ["apply_problem_import", "rollback_problem_import"]

"""Rules for writing online oral marks into the legacy result tables."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from db_methods.pwa.oral_results import (
    conversation_marks,
    conversation_reaction_id,
    existing_conversation,
    insert_conversation,
    insert_result,
    insert_teacher_reaction,
    online_student,
    online_students,
    oral_lesson,
    oral_problems,
    reject_prior_positive_oral_result,
    remove_written_queue_entry,
)
from helpers.consts import VERDICT


class OralResultNotFound(Exception):
    pass


class OralResultInvalid(Exception):
    pass


class OralResultConflict(Exception):
    pass


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def roster(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
) -> dict[str, object]:
    lesson = oral_lesson(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )
    if lesson is None:
        raise OralResultNotFound
    students = online_students(
        connection,
        course_public_id=str(lesson["course_public_id"]),
        group_public_id=str(lesson["group_public_id"]),
    )
    for student in students:
        student["display_name"] = " ".join(
            str(student[field]).strip()
            for field in ("surname", "name", "middlename")
            if student[field] is not None and str(student[field]).strip()
        )
    return {
        "lesson": lesson,
        "students": students,
        "problems": oral_problems(
            connection,
            group_lesson_id=int(lesson["group_lesson_id"]),
        ),
    }


def _verdict(outcome: str) -> int:
    if outcome == "accepted":
        return int(VERDICT.SOLVED)
    if outcome == "rejected":
        return int(VERDICT.WRONG_ANSWER)
    raise OralResultInvalid


def _replay(
    connection: sqlite3.Connection,
    *,
    conversation: dict[str, object],
    student_user_id: int,
    teacher_user_id: int,
    lesson_number: int,
    group_id: str,
    requested_marks: dict[str, int],
    reaction_id: int | None,
) -> dict[str, object]:
    stored_marks = {
        str(mark["public_id"]): int(mark["verdict"])
        for mark in conversation_marks(
            connection,
            conversation_id=int(conversation["id"]),
        )
    }
    stored_reaction = conversation_reaction_id(
        connection,
        conversation_id=int(conversation["id"]),
    )
    if (
        int(conversation["student_id"]) != student_user_id
        or int(conversation["teacher_id"]) != teacher_user_id
        or int(conversation["lesson"]) != lesson_number
        or str(conversation["group_id"]) != group_id
        or stored_marks != requested_marks
        or stored_reaction != reaction_id
    ):
        raise OralResultConflict
    return {
        "conversation_id": int(conversation["id"]),
        "marks": stored_marks,
        "reaction_id": stored_reaction,
        "replayed": True,
    }


def record_round(
    connection: sqlite3.Connection,
    *,
    group_lesson_public_id: str,
    student_public_id: str,
    teacher_user_id: int,
    idempotency_key: str,
    marks: tuple[tuple[str, str], ...],
    reaction_id: int | None,
    now: datetime,
) -> dict[str, object]:
    if not idempotency_key or not 1 <= len(marks) <= 50:
        raise OralResultInvalid
    requested_marks = {problem_id: _verdict(outcome) for problem_id, outcome in marks}
    if len(requested_marks) != len(marks):
        raise OralResultInvalid

    lesson = oral_lesson(
        connection,
        group_lesson_public_id=group_lesson_public_id,
    )
    if lesson is None:
        raise OralResultNotFound
    student = online_student(
        connection,
        student_public_id=student_public_id,
        course_public_id=str(lesson["course_public_id"]),
        group_public_id=str(lesson["group_public_id"]),
    )
    if student is None:
        raise OralResultNotFound
    available_problems = {
        str(problem["public_id"]): problem
        for problem in oral_problems(
            connection,
            group_lesson_id=int(lesson["group_lesson_id"]),
        )
    }
    if not set(requested_marks) <= set(available_problems):
        raise OralResultInvalid

    existing = existing_conversation(connection, idempotency_key=idempotency_key)
    if existing is not None:
        replay = _replay(
            connection,
            conversation=existing,
            student_user_id=int(student["student_user_id"]),
            teacher_user_id=teacher_user_id,
            lesson_number=int(lesson["lesson_number"]),
            group_id=str(lesson["group_id"]),
            requested_marks=requested_marks,
            reaction_id=reaction_id,
        )
        return {
            **replay,
            "student_account_public_id": student["account_public_id"],
            "course_public_id": lesson["course_public_id"],
            "group_public_id": lesson["group_public_id"],
        }

    timestamp = _timestamp(now)
    conversation_id = insert_conversation(
        connection,
        student_user_id=int(student["student_user_id"]),
        teacher_user_id=teacher_user_id,
        lesson_number=int(lesson["lesson_number"]),
        group_id=str(lesson["group_id"]),
        idempotency_key=idempotency_key,
        now=timestamp,
    )
    for problem_public_id, verdict in requested_marks.items():
        problem_id = int(available_problems[problem_public_id]["problem_id"])
        if verdict == int(VERDICT.WRONG_ANSWER):
            reject_prior_positive_oral_result(
                connection,
                student_user_id=int(student["student_user_id"]),
                problem_id=problem_id,
            )
        insert_result(
            connection,
            student_user_id=int(student["student_user_id"]),
            teacher_user_id=teacher_user_id,
            problem_id=problem_id,
            lesson_number=int(lesson["lesson_number"]),
            group_id=str(lesson["group_id"]),
            verdict=verdict,
            conversation_id=conversation_id,
            now=timestamp,
        )
        if verdict == int(VERDICT.SOLVED):
            remove_written_queue_entry(
                connection,
                student_user_id=int(student["student_user_id"]),
                problem_id=problem_id,
            )
    if reaction_id is not None and not insert_teacher_reaction(
        connection,
        conversation_id=conversation_id,
        reaction_id=reaction_id,
        now=timestamp,
    ):
        raise OralResultInvalid
    return {
        "conversation_id": conversation_id,
        "marks": requested_marks,
        "reaction_id": reaction_id,
        "replayed": False,
        "student_account_public_id": student["account_public_id"],
        "course_public_id": lesson["course_public_id"],
        "group_public_id": lesson["group_public_id"],
    }


__all__ = [
    "OralResultConflict",
    "OralResultInvalid",
    "OralResultNotFound",
    "record_round",
    "roster",
]

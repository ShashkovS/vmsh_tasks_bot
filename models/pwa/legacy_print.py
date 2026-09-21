"""Excel-shaped export of confirmed plans; docs/printing/legacy-api.md."""

from collections import defaultdict
import sqlite3

from db_methods.pwa.classroom_assignments import find_plan
from db_methods.pwa.course_analytics import (
    list_course_group_access_rows,
    list_course_result_rows,
)
from db_methods.pwa.legacy_print import (
    list_confirmed_plan_print_assignments,
    list_print_course_pupils,
    list_print_identities,
    list_print_lesson_problems,
    list_print_previous_problems,
    list_print_previous_results,
)
from db_methods.pwa.classroom_layouts import get_in_person_event
from models.pwa.classroom_assignments import (
    ClassroomAssignmentNotFound,
    read_assignment_plan,
)
from models.pwa.course_analytics import (
    _best_problem_scores,
    calculate_course_lesson_metrics,
)


class LegacyPrintConflict(Exception):
    """The operator must resolve a plan or compatibility problem first."""


def _validated_print_pupils(connection: sqlite3.Connection, event_id: str, lesson: int):
    event = get_in_person_event(connection, event_id)
    if event is None:
        raise ClassroomAssignmentNotFound
    if event["status"] == "cancelled":
        raise LegacyPrintConflict("event_cancelled")
    # Printing must reproduce the last confirmed plan, rather than the live
    # eligibility/room state or a newer unconfirmed draft.  See
    # docs/printing/legacy-api.md, "Сервер".
    plan = find_plan(connection, int(event["id"]), ("confirmed",))
    if plan is None or plan["state"] != "confirmed":
        raise LegacyPrintConflict("plan_not_confirmed")
    students = list_confirmed_plan_print_assignments(connection, int(plan["id"]))
    if not students:
        raise LegacyPrintConflict("roster_changed")
    groups = {
        int(row["group_lesson_id"]): {
            "course_id": int(row["plan_course_id"]),
            "group_id": str(row["plan_group_id"]),
            "lesson_number": int(row["plan_lesson_number"]),
            "short_code": row["plan_short_code"],
        }
        for row in students
    }
    if {group["lesson_number"] for group in groups.values()} != {lesson}:
        raise LegacyPrintConflict("lesson_mismatch")
    if len({group["course_id"] for group in groups.values()}) != 1:
        raise LegacyPrintConflict("multiple_courses")
    if any(
        group["short_code"] not in {"н", "п", "э"}
        for group in groups.values()
    ):
        raise LegacyPrintConflict("unsupported_level")
    identities = {
        int(row["enrollment_id"]): row["username"]
        for row in list_print_identities(connection, int(plan["id"]))
    }
    pupils, seen_logins, room_groups = [], set(), {}
    for student in students:
        enrollment_id = int(student["course_enrollment_id"])
        group_lesson_id = int(student["group_lesson_id"])
        room_id = student["classroom_id"]
        group = groups[group_lesson_id]
        if (
            student["status"] != "assigned"
            or room_id is None
            or not isinstance(student["classroom_name"], str)
            or not student["classroom_name"].strip()
            or str(student["group_id"]) != group["group_id"]
        ):
            raise LegacyPrintConflict("roster_changed")
        login = identities.get(enrollment_id)
        if not isinstance(login, str) or not login.strip() or login in seen_logins:
            raise LegacyPrintConflict("missing_or_duplicate_login")
        seen_logins.add(login)
        room = str(student["classroom_name"])
        if room in room_groups and room_groups[room] != group_lesson_id:
            raise LegacyPrintConflict("mixed_room")
        room_groups[room] = group_lesson_id
        surname = str(student["surname"] or "").strip()
        name = str(student["name"] or "").strip()
        if not surname or not name:
            raise LegacyPrintConflict("missing_name")
        pupils.append(
            {
                "Фамилия": surname,
                "Имя": name,
                "ID": login,
                "IDd": login,
                "Клс": str(student["grade"]) if student["grade"] is not None else "",
                "Скрыть": None,
                "Уровень": group["short_code"],
                "Аудитория": room,
                "Посещаемость": None,
                "Ср3": "",
                "ФИО": f"{surname} {name}",
                "ФИ.": f"{surname} {name[0]}.",
                "UserID": int(student["student_user_id"]),
                "GroupID": student["group_id"],
            }
        )
    pupils.sort(key=lambda row: (row["ФИО"].casefold().replace("ё", "е"), row["ID"]))
    for index, pupil in enumerate(pupils, start=5):
        pupil["Строчка"] = index
    return event, plan, pupils


def export_print_pupils(connection: sqlite3.Connection, event_id: str, lesson: int):
    # One SQLite read snapshot includes the confirmed plan and mutable names.
    connection.execute("BEGIN")
    try:
        return _validated_print_pupils(connection, event_id, lesson)
    finally:
        connection.execute("ROLLBACK")


def export_print_previous_results(
    connection: sqlite3.Connection, event_id: str, lesson: int
):
    """Export the previous lesson conduit from the same confirmed roster."""

    connection.execute("BEGIN")
    try:
        event, plan, pupils = _validated_print_pupils(connection, event_id, lesson)
        previous_lesson = lesson - 1
        group_ids = tuple(sorted({str(pupil["GroupID"]) for pupil in pupils}))
        problems = list_print_previous_problems(
            connection, group_ids=group_ids, lesson=previous_lesson
        )
        results = list_print_previous_results(
            connection,
            plan_id=int(plan["id"]),
            group_ids=group_ids,
            lesson=previous_lesson,
        )
        return (
            event,
            plan,
            {
                "lesson": previous_lesson,
                "problems": problems,
                "results": results,
            },
        )
    finally:
        connection.execute("ROLLBACK")


def export_print_lesson_results(
    connection: sqlite3.Connection, event_id: str, lesson: int
):
    """Export the post-lesson mail matrix and legacy-site statistics facts."""

    connection.execute("BEGIN")
    try:
        data = read_assignment_plan(connection, event_id)
        event = data["event"]
        if event["status"] == "cancelled":
            raise LegacyPrintConflict("event_cancelled")
        groups = data["groups"]
        if not groups:
            raise LegacyPrintConflict("lesson_mismatch")
        course_ids = {int(group["course_id"]) for group in groups}
        if len(course_ids) != 1:
            raise LegacyPrintConflict("multiple_courses")
        if any(group["short_code"] not in {"н", "п", "э"} for group in groups):
            raise LegacyPrintConflict("unsupported_level")
        plan = find_plan(connection, int(event["id"]), ("confirmed",))
        if plan is None:
            raise LegacyPrintConflict("plan_not_confirmed")

        course_id = course_ids.pop()
        course_public_id = str(groups[0]["course_public_id"])
        group_ids = tuple(sorted(str(group["group_id"]) for group in groups))
        pupils = [
            pupil
            for pupil in list_print_course_pupils(connection, course_id)
            if str(pupil["group_id"]) in group_ids
        ]
        seen_logins: set[str] = set()
        for pupil in pupils:
            login = pupil["login"]
            if (
                not isinstance(login, str)
                or not login.strip()
                or login in seen_logins
                or not str(pupil["surname"] or "").strip()
                or not str(pupil["name"] or "").strip()
            ):
                raise LegacyPrintConflict("missing_or_duplicate_login")
            seen_logins.add(login)

        problems = list_print_lesson_problems(
            connection, course_id=course_id, group_ids=group_ids, lesson=lesson
        )
        if not problems:
            raise LegacyPrintConflict("lesson_has_no_problems")
        target_keys = {str(problem["logical_problem_key"]) for problem in problems}
        all_results = list_course_result_rows(connection, course_id=course_id)
        current_results = [
            row
            for row in all_results
            if int(row["lesson_number"]) == lesson
            and str(row["logical_problem_key"]) in target_keys
        ]
        access = list_course_group_access_rows(connection, course_id=course_id)
        metrics = calculate_course_lesson_metrics(problems, current_results, access)
        active_pupil_ids = {int(pupil["id"]) for pupil in pupils}
        selected_groups = {
            int(metric["student_user_id"]): str(metric["group_id"])
            for metric in metrics
            if int(metric["lesson_number"]) == lesson
            and int(metric["student_user_id"]) in active_pupil_ids
            and str(metric["group_id"]) in group_ids
        }

        raw_weights: dict[tuple[int, int, str], float] = defaultdict(float)
        for row in current_results:
            key = (
                int(row["student_user_id"]),
                lesson,
                str(row["logical_problem_key"]),
            )
            raw_weights[key] = max(raw_weights[key], float(row["verdict_weight"]))
        scores, _ = _best_problem_scores(current_results)
        problems_by_group: dict[str, list[dict]] = defaultdict(list)
        for problem in problems:
            problems_by_group[str(problem["group_id"])].append(problem)

        result_matrix = []
        for student_id, group_id in sorted(selected_groups.items()):
            for problem in problems_by_group[group_id]:
                key = (student_id, lesson, str(problem["logical_problem_key"]))
                result_matrix.append(
                    {
                        "student_id": student_id,
                        "problem_id": int(problem["problem_id"]),
                        "max_verdict": raw_weights.get(key),
                        "score": float(scores.get(key, 0.0)),
                    }
                )

        recent_from = max(1, lesson - 3)
        recent_student_ids = sorted(
            {
                int(row["student_user_id"])
                for row in all_results
                if recent_from <= int(row["lesson_number"]) <= lesson
                and int(row["student_user_id"]) in active_pupil_ids
            }
        )
        return (
            event,
            plan,
            {
                "schemaVersion": 1,
                "courseId": course_public_id,
                "lesson": lesson,
                "pupils": [
                    {
                        "id": int(pupil["id"]),
                        "login": pupil["login"],
                        "surname": pupil["surname"],
                        "name": pupil["name"],
                        "group_id": pupil["group_id"],
                        "level": pupil["level"],
                    }
                    for pupil in pupils
                ],
                "problems": [
                    {
                        "id": int(problem["problem_id"]),
                        "lesson": int(problem["lesson_number"]),
                        "group_id": problem["group_id"],
                        "level": problem["level"],
                        "prob": problem["prob"],
                        "item": problem["item"],
                        "prob_type": int(problem["problem_type"]),
                    }
                    for problem in problems
                ],
                "results": result_matrix,
                "recentStudentIds": recent_student_ids,
            },
        )
    finally:
        connection.execute("ROLLBACK")

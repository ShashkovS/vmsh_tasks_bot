"""Excel-shaped export of confirmed plans; docs/printing/legacy-api.md."""

import sqlite3

from db_methods.pwa.classroom_assignments import list_eligible_students
from db_methods.pwa.legacy_print import list_print_identities
from models.pwa.classroom_assignments import read_assignment_plan


class LegacyPrintConflict(Exception):
    """The operator must resolve a plan or compatibility problem first."""


def export_print_pupils(connection: sqlite3.Connection, event_id: str, lesson: int):
    # One SQLite read snapshot includes plan, eligibility and mutable names.
    connection.execute("BEGIN")
    try:
        data = read_assignment_plan(connection, event_id)
        plan = data["plan"]
        if data["event"]["status"] == "cancelled":
            raise LegacyPrintConflict("event_cancelled")
        if plan is None or plan["state"] != "confirmed":
            raise LegacyPrintConflict("plan_not_confirmed")
        groups = {int(row["group_lesson_id"]): row for row in data["groups"]}
        if not groups or {int(g["lesson_number"]) for g in groups.values()} != {lesson}:
            raise LegacyPrintConflict("lesson_mismatch")
        if len({g["course_id"] for g in groups.values()}) != 1:
            raise LegacyPrintConflict("multiple_courses")
        if any(g["short_code"] not in {"н", "п", "э"} for g in groups.values()):
            raise LegacyPrintConflict("unsupported_level")
        eligible = {
            int(row["enrollment_id"]): row
            for row in list_eligible_students(connection, int(data["event"]["id"]))
        }
        students = data["students"]
        if not students or {int(s["course_enrollment_id"]) for s in students} != set(
            eligible
        ):
            raise LegacyPrintConflict("roster_changed")
        identities = {
            int(row["enrollment_id"]): row["username"]
            for row in list_print_identities(connection, int(plan["id"]))
        }
        valid_rooms = {
            (int(room["classroom_id"]), int(room["group_lesson_id"]))
            for room in data["rooms"]
            if room["classroom_status"] == "active"
        }
        pupils, seen_logins, room_groups = [], set(), {}
        for student in students:
            enrollment_id = int(student["course_enrollment_id"])
            group_lesson_id = int(student["group_lesson_id"])
            room_id = student["classroom_id"]
            if (
                student["status"] != "assigned"
                or room_id is None
                or (int(room_id), group_lesson_id) not in valid_rooms
                or group_lesson_id != int(eligible[enrollment_id]["group_lesson_id"])
                or student["group_id"] != eligible[enrollment_id]["group_id"]
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
                    "Клс": str(student["grade"])
                    if student["grade"] is not None
                    else "",
                    "Скрыть": None,
                    "Уровень": groups[group_lesson_id]["short_code"],
                    "Аудитория": room,
                    "Посещаемость": None,
                    "Ср3": "",
                    "ФИО": f"{surname} {name}",
                    "ФИ.": f"{surname} {name[0]}.",
                    "UserID": int(student["student_user_id"]),
                    "GroupID": student["group_id"],
                }
            )
        pupils.sort(
            key=lambda row: (row["ФИО"].casefold().replace("ё", "е"), row["ID"])
        )
        for index, pupil in enumerate(pupils, start=5):
            pupil["Строчка"] = index
        return data["event"], plan, pupils
    finally:
        connection.execute("ROLLBACK")

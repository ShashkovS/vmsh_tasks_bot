from datetime import date

from helpers.pwa.classroom_assignment import (
    AssignmentRoom,
    StudentToAssign,
    age_in_years,
    distribute_students,
)


def student(
    enrollment_id: int,
    *,
    group_lesson_id: int = 10,
    previous_classroom_id: int | None = None,
) -> StudentToAssign:
    return StudentToAssign(
        enrollment_id=enrollment_id,
        group_lesson_id=group_lesson_id,
        surname=f"Фамилия {enrollment_id:03}",
        name=f"Имя {enrollment_id:03}",
        previous_classroom_id=previous_classroom_id,
    )


def test_previous_room_is_kept_and_other_students_are_balanced():
    decisions = distribute_students(
        [student(1, previous_classroom_id=2), student(2), student(3), student(4)],
        [
            AssignmentRoom(classroom_id=1, group_lesson_id=10, name="10"),
            AssignmentRoom(classroom_id=2, group_lesson_id=10, name="2"),
        ],
    )

    assert decisions[0].classroom_id == 2
    assert decisions[0].source == "previous-room"
    assert [decision.classroom_id for decision in decisions[1:]] == [1, 2, 1]


def test_students_without_a_room_are_explicitly_unassigned():
    decisions = distribute_students(
        [student(1, group_lesson_id=20)],
        [AssignmentRoom(classroom_id=1, group_lesson_id=10, name="201")],
    )

    assert decisions[0].classroom_id is None
    assert decisions[0].source is None


def test_distribution_never_assigns_a_room_from_another_group():
    students = [
        student(index, group_lesson_id=10 if index % 2 else 20)
        for index in range(1, 201)
    ]
    rooms = [
        AssignmentRoom(classroom_id=1, group_lesson_id=10, name="201"),
        AssignmentRoom(classroom_id=2, group_lesson_id=10, name="202"),
        AssignmentRoom(classroom_id=3, group_lesson_id=20, name="301"),
    ]
    room_groups = {room.classroom_id: room.group_lesson_id for room in rooms}
    student_groups = {item.enrollment_id: item.group_lesson_id for item in students}

    decisions = distribute_students(students, rooms)

    assert all(
        decision.classroom_id is not None
        and room_groups[decision.classroom_id] == student_groups[decision.enrollment_id]
        for decision in decisions
    )


def test_age_uses_today_and_handles_missing_or_invalid_dates():
    today = date(2026, 7, 29)
    assert age_in_years("2013-01-01", today=today) == 13.6
    assert age_in_years(None, today=today) is None
    assert age_in_years("not-a-date", today=today) is None
    assert age_in_years("2030-01-01", today=today) is None

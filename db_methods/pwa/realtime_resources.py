"""Public resource dependencies; docs/performance/scoped-reads-20261013.md."""

import json


def course_lesson_dependencies(connection, public_id):
    lessons = connection.execute(
        """SELECT gl.public_id FROM group_lessons gl JOIN course_lessons cl
        ON cl.id=gl.course_lesson_id WHERE cl.public_id=?""", (public_id,)
    ).fetchall()
    return list(dict.fromkeys(
        resource for lesson in lessons for resource in (
            *lesson_resources(connection, lesson["public_id"]),
            f"group-lessons/{lesson['public_id']}/problem-release",
            f"group-lessons/{lesson['public_id']}/work",
        )
    ))


def lesson_resources(connection, public_id):
    row = connection.execute(
        """SELECT c.public_id course, g.public_id level, cl.lesson_number number
        FROM group_lessons gl JOIN courses c ON c.id=gl.course_id
        JOIN groups g ON g.course_id=gl.course_id AND g.group_id=gl.group_id
        JOIN course_lessons cl ON cl.id=gl.course_lesson_id WHERE gl.public_id=?""",
        (public_id,),
    ).fetchone()
    if row is None:
        return []
    return [
        f"group-lessons/{public_id}/card",
        f"courses/{row['course']}/groups/{row['level']}/lessons",
        f"courses/{row['course']}/groups/{row['level']}/lesson-numbers/{row['number']}/content",
    ]


def problem_work_resources(connection, public_ids):
    """Close over logical aliases before locating the public lesson consumers."""
    rows = connection.execute(
        """WITH logical AS (
          SELECT DISTINCT source.logical_key FROM result_problem_groups source
          JOIN problems p ON p.id=source.problem_id
          WHERE p.public_id IN (SELECT value FROM json_each(?))
        )
        SELECT DISTINCT gl.public_id lesson, c.public_id course,
               g.public_id level, cl.lesson_number number
        FROM logical JOIN result_problem_groups member USING(logical_key)
        JOIN problems p ON p.id=member.problem_id
        JOIN groups g ON g.group_id=p.group_id
        JOIN courses c ON c.id=g.course_id
        JOIN course_lessons cl ON cl.course_id=c.id AND cl.lesson_number=p.lesson
        JOIN group_lessons gl ON gl.course_lesson_id=cl.id AND gl.group_id=g.group_id
        ORDER BY course,lesson""",
        (json.dumps(list(public_ids)),),
    ).fetchall()
    return list(dict.fromkeys(
        resource for row in rows for resource in (
            f"group-lessons/{row['lesson']}/work",
            f"live-cells/{row['lesson']}",
            f"courses/{row['course']}/work",
            f"courses/{row['course']}/statistics",
            f"courses/{row['course']}/groups/{row['level']}/lesson-numbers/{row['number']}/work",
        )
    ))

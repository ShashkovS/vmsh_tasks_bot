"""Focused SQLite reads/writes for docs/teacher-work.md and its domain runner."""

import json


def rows(connection, sql, params=()):
    return [dict(row) for row in connection.execute(sql, params)]


def roster_facts(connection, course_id):
    """Import context without the result ledger; docs/teacher-work.md, input correction."""
    return {
        "course": dict(
            connection.execute(
                "SELECT s.timezone,s.starts_on,s.ends_on FROM courses c "
                "JOIN seasons s ON s.id=c.season_id WHERE c.id=?",
                (course_id,),
            ).fetchone()
        ),
        "teachers": rows(
            connection,
            "SELECT id,public_id,surname,name,middlename FROM users "
            "WHERE type IN (2,128) ORDER BY id",
        ),
        "events": rows(
            connection,
            """SELECT DISTINCT e.* FROM in_person_events e
            JOIN in_person_event_group_lessons eg ON eg.in_person_event_id=e.id
            JOIN group_lessons gl ON gl.id=eg.group_lesson_id
            WHERE gl.course_id=? AND e.status!='cancelled' ORDER BY e.starts_at""",
            (course_id,),
        ),
        "settings": settings(connection, course_id),
    }


def input_facts(connection, course_id):
    facts = roster_facts(connection, course_id)
    facts.update({
        "zoom": rows(
            connection,
            "SELECT id,event_ts,event,zoom_user_name,zoom_user_id FROM zoom_events "
            "WHERE substr(event_ts,1,10) BETWEEN ? AND ? ORDER BY id",
            (facts["course"]["starts_on"], facts["course"]["ends_on"]),
        ),
        "aliases": rows(
            connection,
            "SELECT * FROM teacher_work_aliases WHERE course_id=? ORDER BY normalized_name",
            (course_id,),
        ),
        "shifts": rows(
            connection,
            """SELECT sh.* FROM teacher_work_shifts sh JOIN in_person_events e ON e.id=sh.event_id
            WHERE sh.course_id=? AND e.status!='cancelled' ORDER BY sh.event_id,sh.teacher_id""",
            (course_id,),
        ),
    })
    return facts


def source_facts(connection, course_id):
    course = dict(
        connection.execute(
            """SELECT c.id,c.public_id,c.name,c.status,
        s.timezone,s.starts_on,s.ends_on FROM courses c JOIN seasons s ON s.id=c.season_id
        WHERE c.id=?""",
            (course_id,),
        ).fetchone()
    )
    return {
        "course": course,
        "teachers": rows(
            connection,
            "SELECT id,public_id,surname,name,middlename FROM users WHERE type IN (2,128) ORDER BY id",
        ),
        "results": rows(
            connection,
            """SELECT r.id,r.teacher_id,r.problem_id,p.lesson,r.verdict,r.ts,r.res_type,
          sr.public_id AS review_id,sr.source AS review_source FROM results r
          JOIN problems p ON p.id=r.problem_id JOIN groups g ON g.group_id=p.group_id
          JOIN users student ON student.id=r.student_id AND student.type IN (1,-2)
          JOIN users teacher ON teacher.id=r.teacher_id AND teacher.type IN (2,128)
          LEFT JOIN submission_reviews sr ON sr.result_id=r.id
          WHERE g.course_id=? AND r.res_type IN (2,3) AND coalesce(sr.source,'staff')!='ai'
          ORDER BY r.id""",
            (course_id,),
        ),
        "zoom": rows(
            connection,
            """SELECT id,event_ts,event,zoom_user_name,zoom_user_id
          FROM zoom_events WHERE substr(event_ts,1,10) BETWEEN ? AND ? ORDER BY id""",
            (course["starts_on"], course["ends_on"]),
        ),
        "aliases": rows(
            connection,
            "SELECT * FROM teacher_work_aliases WHERE course_id=? ORDER BY normalized_name",
            (course_id,),
        ),
        "shifts": rows(
            connection,
            """SELECT sh.* FROM teacher_work_shifts sh JOIN in_person_events e ON e.id=sh.event_id
          WHERE sh.course_id=? AND e.status!='cancelled' ORDER BY sh.event_id,sh.teacher_id""",
            (course_id,),
        ),
        "settings": settings(connection, course_id),
        "lessons": rows(
            connection,
            """SELECT cl.lesson_number AS number,min(gl.cycle_anchor_date) AS anchor
          FROM course_lessons cl JOIN group_lessons gl ON gl.course_lesson_id=cl.id
          WHERE cl.course_id=? GROUP BY cl.id ORDER BY cl.lesson_number""",
            (course_id,),
        ),
        "events": rows(
            connection,
            """SELECT DISTINCT e.* FROM in_person_events e
          JOIN in_person_event_group_lessons eg ON eg.in_person_event_id=e.id
          JOIN group_lessons gl ON gl.id=eg.group_lesson_id
          WHERE gl.course_id=? AND e.status!='cancelled' ORDER BY e.starts_at""",
            (course_id,),
        ),
        "windows": rows(
            connection,
            """SELECT DISTINCT w.id,w.opens_at,w.closes_at FROM oral_windows w
          LEFT JOIN oral_window_lessons wl ON wl.window_id=w.id
          JOIN group_lessons gl ON gl.id=w.group_lesson_id OR gl.id=wl.group_lesson_id
          WHERE gl.course_id=? AND w.status='active' ORDER BY w.opens_at""",
            (course_id,),
        ),
    }


def settings(connection, course_id):
    row = connection.execute(
        "SELECT norm_hours,version FROM teacher_work_settings WHERE course_id=?",
        (course_id,),
    ).fetchone()
    return dict(row) if row else {"norm_hours": 2.3, "version": 0}


def latest_run(connection, course_id, *, completed=False):
    row = connection.execute(
        "SELECT * FROM teacher_work_runs WHERE course_id=? "
        + ("AND state='completed' AND snapshot_json IS NOT NULL " if completed else "")
        + "ORDER BY id DESC LIMIT 1",
        (course_id,),
    ).fetchone()
    return dict(row) if row else None


def create_run(connection, course_id, actor, key, now):
    return connection.execute(
        """INSERT INTO teacher_work_runs(course_id,actor_id,request_key,state,started_at)
      VALUES(?,?,?,'queued',?)""",
        (course_id, actor, key, now),
    ).lastrowid


def publish(connection, run_id, digest, snapshot, now):
    connection.execute(
        """UPDATE teacher_work_runs SET state='completed',completed_at=?,
      source_fingerprint=?,snapshot_json=?,error_code=NULL WHERE id=?""",
        (now, digest, json.dumps(snapshot, ensure_ascii=False), run_id),
    )
    # Retain two complete payloads; operation/replay/audit records remain durable.
    connection.execute(
        """UPDATE teacher_work_runs SET snapshot_json=NULL
      WHERE course_id=(SELECT course_id FROM teacher_work_runs WHERE id=?)
        AND state='completed' AND id NOT IN (
          SELECT id FROM teacher_work_runs WHERE course_id=(SELECT course_id FROM teacher_work_runs WHERE id=?)
          AND state='completed' ORDER BY id DESC LIMIT 2)""",
        (run_id, run_id),
    )


def fail_run(connection, run_id, now, code):
    connection.execute(
        "UPDATE teacher_work_runs SET state='failed',completed_at=?,error_code=? WHERE id=?",
        (now, code, run_id),
    )


def replay(connection, actor, key):
    row = connection.execute(
        "SELECT * FROM teacher_work_mutations WHERE actor_id=? AND request_key=?",
        (actor, key),
    ).fetchone()
    return dict(row) if row else None


def audit(
    connection, course_id, actor, key, digest, action, entity, before, after, now
):
    connection.execute(
        """INSERT INTO teacher_work_mutations(course_id,actor_id,request_key,payload_sha256,
       action,entity_key,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            course_id,
            actor,
            key,
            digest,
            action,
            entity,
            json.dumps(before, ensure_ascii=False),
            json.dumps(after, ensure_ascii=False),
            now,
        ),
    )

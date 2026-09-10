"""SQLite primitives for vmshpwa/docs/live-marking.md and migration 0087."""

from __future__ import annotations

import json


def rows(connection, query, args=()):
    return [dict(row) for row in connection.execute(query, args)]


def one(connection, query, args=()):
    row = connection.execute(query, args).fetchone()
    return None if row is None else dict(row)


def courses(connection):
    return rows(
        connection,
        "SELECT id, public_id, name FROM courses WHERE status='active' ORDER BY sort_order,id",
    )


def lessons(connection, course_id):
    return rows(
        connection,
        """
        SELECT gl.id, gl.public_id, gl.group_id, g.public_id group_public_id,
               g.public_name group_name, cl.lesson_number, gl.course_id,
               c.public_id course_public_id
        FROM group_lessons gl JOIN course_lessons cl ON cl.id=gl.course_lesson_id
        JOIN groups g ON g.group_id=gl.group_id AND g.course_id=gl.course_id
        JOIN courses c ON c.id=gl.course_id
        WHERE gl.course_id=? AND gl.status='active'
          AND EXISTS (SELECT 1 FROM lesson_publications p WHERE p.group_lesson_id=gl.id
                      AND p.kind='condition' AND p.state='published')
        ORDER BY cl.lesson_number DESC,g.sort_order,gl.id
    """,
        (course_id,),
    )


def lesson(connection, public_id):
    return one(
        connection,
        """
        SELECT gl.*, cl.lesson_number, c.public_id course_public_id,
               g.public_id group_public_id, g.public_name group_name
        FROM group_lessons gl JOIN course_lessons cl ON cl.id=gl.course_lesson_id
        JOIN courses c ON c.id=gl.course_id
        JOIN groups g ON g.course_id=gl.course_id AND g.group_id=gl.group_id
        WHERE gl.public_id=? AND gl.status='active'
    """,
        (public_id,),
    )


def students(connection, course_id):
    return rows(
        connection,
        """
        SELECT u.id student_id,u.public_id student_public_id,u.surname,u.name,u.middlename,
               u.grade,e.id enrollment_id,e.public_id enrollment_public_id,e.version,
               e.attendance_mode,e.active_group_id,e.course_id,g.public_id group_public_id,
               g.public_name group_name
        FROM course_enrollments e JOIN users u ON u.id=e.student_user_id
        JOIN groups g ON g.course_id=e.course_id AND g.group_id=e.active_group_id
        WHERE e.course_id=? AND e.status='active' AND u.public_id IS NOT NULL
        ORDER BY u.surname COLLATE NOCASE,u.name COLLATE NOCASE,u.id
    """,
        (course_id,),
    )


def student(connection, course_id, public_id):
    return next(
        (
            r
            for r in students(connection, course_id)
            if r["student_public_id"] == public_id
        ),
        None,
    )


def events(connection):
    return rows(
        connection,
        "SELECT * FROM in_person_events WHERE status IN ('scheduled','completed') ORDER BY starts_at DESC,id DESC",
    )


def event(connection, public_id):
    return one(
        connection,
        "SELECT * FROM in_person_events WHERE public_id=? AND status IN ('scheduled','completed')",
        (public_id,),
    )


def rooms(connection, event_id):
    return rows(
        connection,
        """
        SELECT r.id,r.public_id,r.name,gl.id group_lesson_id,gl.public_id lesson_public_id,
               gl.group_id,gl.course_id,g.public_id group_public_id,g.public_name group_name,
               c.public_id course_public_id,lv.id layout_id
        FROM classroom_layout_versions lv
        JOIN classroom_layout_rooms lr ON lr.layout_version_id=lv.id
        JOIN classrooms r ON r.id=lr.classroom_id AND r.status='active'
        JOIN group_lessons gl ON gl.id=lr.group_lesson_id
        JOIN groups g ON g.course_id=gl.course_id AND g.group_id=gl.group_id
        JOIN courses c ON c.id=gl.course_id
        WHERE lv.in_person_event_id=? AND lv.state='confirmed'
        ORDER BY g.sort_order,r.name
    """,
        (event_id,),
    )


def plan(connection, event_id):
    return one(
        connection,
        "SELECT * FROM classroom_assignment_plans WHERE in_person_event_id=? AND state='confirmed'",
        (event_id,),
    )


def assignments(connection, plan_id):
    return rows(
        connection, "SELECT * FROM classroom_assignments WHERE plan_id=?", (plan_id,)
    )


def room_history(connection, course_id):
    return rows(
        connection,
        """
        SELECT e.student_user_id,ev.public_id event_id,ev.name event_name,ev.starts_at,
               r.name room_name,p.id plan_id,p.state, a.classroom_id
        FROM classroom_assignments a JOIN classroom_assignment_plans p ON p.id=a.plan_id
        JOIN in_person_events ev ON ev.id=p.in_person_event_id
        JOIN course_enrollments e ON e.id=a.course_enrollment_id
        LEFT JOIN classrooms r ON r.id=a.classroom_id
        WHERE e.course_id=? AND p.state IN ('confirmed','superseded')
        ORDER BY ev.starts_at DESC,p.id DESC
    """,
        (course_id,),
    )


def problems(connection, lesson_id):
    return rows(
        connection,
        """
        SELECT p.id,p.public_id,pr.display_number,pr.title,pr.problem_type,p.prob,p.item
        FROM lesson_publications lp JOIN problem_revisions pr ON pr.content_revision_id=lp.revision_id
        JOIN problems p ON p.id=pr.problem_id
        WHERE lp.group_lesson_id=? AND lp.kind='condition' AND lp.state='published'
          AND p.public_id IS NOT NULL
        ORDER BY pr.source_ordinal,pr.source_item,p.id
    """,
        (lesson_id,),
    )


def cells(connection, student_ids, problem_ids, after=None):
    if not student_ids or not problem_ids:
        return []
    # Bound IN lists come only from server-authorized rosters/publications.
    ss, pp = ",".join("?" for _ in student_ids), ",".join("?" for _ in problem_ids)
    return rows(
        connection,
        f"""
        SELECT c.student_id,c.problem_id,c.version,c.result_id,
               r.verdict,r.teacher_id,r.ts,u.public_id teacher_public_id
        FROM live_mark_cells c LEFT JOIN effective_results r
          ON r.student_id=c.student_id AND r.problem_id=c.problem_id
          AND r.id=(SELECT er.id FROM effective_results er
              JOIN verdicts v ON v.id=er.verdict
              WHERE er.student_id=c.student_id AND er.problem_id=c.problem_id
              ORDER BY v.val DESC,er.ts DESC,er.id DESC LIMIT 1)
        LEFT JOIN users u ON u.id=r.teacher_id
        WHERE c.student_id IN ({ss}) AND c.problem_id IN ({pp})
          AND (? IS NULL OR c.change_seq>?)
        UNION ALL
        SELECT r.student_id,r.problem_id,0,NULL,r.verdict,r.teacher_id,r.ts,u.public_id
        FROM results r LEFT JOIN users u ON u.id=r.teacher_id
        WHERE r.student_id IN ({ss}) AND r.problem_id IN ({pp}) AND ? IS NULL
          AND NOT EXISTS(SELECT 1 FROM live_mark_cells c WHERE c.student_id=r.student_id AND c.problem_id=r.problem_id)
          AND r.id=(SELECT er.id FROM results er JOIN verdicts v ON v.id=er.verdict
             WHERE er.student_id=r.student_id AND er.problem_id=r.problem_id
             ORDER BY v.val DESC,er.ts DESC,er.id DESC LIMIT 1)
    """,
        (*student_ids, *problem_ids, after, after, *student_ids, *problem_ids, after),
    )


def cell(connection, student_id, problem_id):
    found = cells(connection, [student_id], [problem_id])
    return (
        found[0]
        if found
        else dict(
            student_id=student_id,
            problem_id=problem_id,
            version=0,
            result_id=None,
            verdict=None,
            teacher_id=None,
            teacher_public_id=None,
            ts=None,
        )
    )


def append_result(
    connection,
    *,
    student_id,
    problem,
    lesson,
    teacher_id,
    verdict,
    conversation_id,
    now,
):
    result_id = connection.execute(
        """
        INSERT INTO results(student_id,problem_id,lesson,group_id,teacher_id,ts,verdict,res_type,zoom_conversation_id)
        VALUES(?,?,?,?,?,?,?,?,?) RETURNING id
    """,
        (
            student_id,
            problem["id"],
            lesson["lesson_number"],
            lesson["group_id"],
            teacher_id,
            now,
            verdict,
            3 if conversation_id is not None else 4,
            conversation_id,
        ),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO live_mark_results(result_id) VALUES(?)", (result_id,)
    )
    connection.execute(
        "UPDATE live_mark_cells SET result_id=? WHERE student_id=? AND problem_id=?",
        (result_id, student_id, problem["id"]),
    )
    return result_id


def restore_cell(connection, student_id, problem_id, result_id):
    connection.execute(
        "UPDATE live_mark_cells SET result_id=?,version=version+1 WHERE student_id=? AND problem_id=?",
        (result_id, student_id, problem_id),
    )


def attendance(connection, event_id):
    return rows(
        connection, "SELECT * FROM live_attendance WHERE event_id=?", (event_id,)
    )


def attendance_cell(connection, event_id, student_id):
    return one(
        connection,
        "SELECT * FROM live_attendance WHERE event_id=? AND student_id=?",
        (event_id, student_id),
    ) or dict(
        event_id=event_id,
        student_id=student_id,
        state="unmarked",
        version=0,
        teacher_id=None,
    )


def set_attendance(connection, event_id, student_id, state, teacher_id):
    connection.execute(
        """
        INSERT INTO live_attendance(event_id,student_id,state,version,teacher_id) VALUES(?,?,?,1,?)
        ON CONFLICT(event_id,student_id) DO UPDATE SET state=excluded.state,
          version=live_attendance.version+1,teacher_id=excluded.teacher_id
    """,
        (event_id, student_id, state, teacher_id),
    )


def session(connection, session_id):
    return one(
        connection,
        "SELECT s.*,c.public_id course_public_id FROM live_mark_sessions s JOIN courses c ON c.id=s.course_id WHERE s.id=?",
        (session_id,),
    )


def sessions(connection, teacher_id, course_id):
    return rows(
        connection,
        "SELECT * FROM live_mark_sessions WHERE teacher_id=? AND course_id=? ORDER BY created_at DESC",
        (teacher_id, course_id),
    )


def insert_session(connection, session_id, teacher_id, course_id, now):
    connection.execute(
        "INSERT INTO live_mark_sessions(id,teacher_id,course_id,created_at) VALUES(?,?,?,?)",
        (session_id, teacher_id, course_id, now),
    )


def finish_session(connection, session_id, now):
    connection.execute(
        "UPDATE live_mark_sessions SET finished_at=coalesce(finished_at,?) WHERE id=?",
        (now, session_id),
    )


def visit(connection, session_id, student_id, lesson_id):
    return one(
        connection,
        "SELECT * FROM live_mark_visits WHERE session_id=? AND student_id=? AND group_lesson_id=?",
        (session_id, student_id, lesson_id),
    )


def visits(connection, session_id):
    return rows(
        connection,
        """
        SELECT v.*,u.public_id student_public_id,u.surname,u.name,gl.public_id lesson_public_id,
          (SELECT count(*) FROM live_mark_operations op WHERE op.context_id=v.session_id
           AND op.kind='mark' AND op.undone_at IS NULL
           AND json_extract(op.after_json,'$.studentId')=u.public_id
           AND json_extract(op.after_json,'$.lessonId')=gl.public_id) changed_count
        FROM live_mark_visits v JOIN users u ON u.id=v.student_id
        JOIN group_lessons gl ON gl.id=v.group_lesson_id
        WHERE session_id=? ORDER BY updated_at DESC
    """,
        (session_id,),
    )


def insert_visit(connection, session_id, student_id, lesson, teacher_id, now):
    conversation_id = connection.execute(
        """
        INSERT INTO zoom_conversation(ts,student_id,teacher_id,lesson,group_id,pwa_idempotency_key)
        VALUES(?,?,?,?,?,?) RETURNING id
    """,
        (
            now,
            student_id,
            teacher_id,
            lesson["lesson_number"],
            lesson["group_id"],
            f"visit-{session_id}-{student_id}-{lesson['id']}",
        ),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO live_mark_visits(session_id,student_id,group_lesson_id,conversation_id,updated_at) VALUES(?,?,?,?,?)",
        (session_id, student_id, lesson["id"], conversation_id, now),
    )
    return visit(connection, session_id, student_id, lesson["id"])


def touch_visit(
    connection,
    session_id,
    student_id,
    lesson_id,
    now,
    *,
    praised=False,
    advance_version=True,
):
    connection.execute(
        """
        UPDATE live_mark_visits SET updated_at=?,version=version+?,
           praised_at=CASE WHEN ? THEN coalesce(praised_at,?) ELSE praised_at END
        WHERE session_id=? AND student_id=? AND group_lesson_id=?
    """,
        (now, int(advance_version), praised, now, session_id, student_id, lesson_id),
    )


def reactions(connection, conversation_id):
    return [
        r["reaction_id"]
        for r in rows(
            connection,
            "SELECT DISTINCT reaction_id FROM reactions WHERE zoom_conversation_id=? AND reaction_type_id=300",
            (conversation_id,),
        )
    ]


def set_reactions(connection, conversation_id, reaction_ids, now):
    connection.execute(
        "DELETE FROM reactions WHERE zoom_conversation_id=? AND reaction_type_id=300",
        (conversation_id,),
    )
    connection.executemany(
        "INSERT INTO reactions(ts,zoom_conversation_id,reaction_id,reaction_type_id) VALUES(?,?,?,300)",
        [(now, conversation_id, r) for r in reaction_ids],
    )


def operation(connection, operation_id):
    return one(
        connection, "SELECT * FROM live_mark_operations WHERE id=?", (operation_id,)
    )


def history(connection, teacher_id, context_id):
    return rows(
        connection,
        "SELECT * FROM live_mark_operations WHERE teacher_id=? AND context_id=? AND undoable=1 ORDER BY rowid DESC",
        (teacher_id, context_id),
    )


def insert_operation(
    connection,
    operation_id,
    teacher_id,
    context_id,
    kind,
    request,
    before,
    after,
    now,
    *,
    undoable=True,
):
    connection.execute(
        """
        INSERT INTO live_mark_operations(id,teacher_id,context_id,kind,request_json,before_json,after_json,created_at,undoable)
        VALUES(?,?,?,?,?,?,?,?,?)
    """,
        (
            operation_id,
            teacher_id,
            context_id,
            kind,
            json.dumps(request, sort_keys=True),
            json.dumps(before),
            json.dumps(after),
            now,
            undoable,
        ),
    )


def mark_undone(connection, operation_id, now):
    connection.execute(
        "UPDATE live_mark_operations SET undone_at=? WHERE id=?", (now, operation_id)
    )


def previous_operation_version(connection, teacher_id, context_id, target, version):
    # Rebase only the nearest predecessor for the SAME object, making multi-step
    # personal undo possible without undoing interleaved writes from colleagues.
    op = one(
        connection,
        """
        SELECT * FROM live_mark_operations WHERE teacher_id=? AND context_id=? AND undone_at IS NULL
        AND kind=? AND json_extract(after_json,'$.objectKey')=? ORDER BY rowid DESC LIMIT 1
    """,
        (teacher_id, context_id, target["kind"], target["objectKey"]),
    )
    if op is not None:
        state = json.loads(op["after_json"])
        if state.get("version") == target.get("previousVersion"):
            state["version"] = version
            connection.execute(
                "UPDATE live_mark_operations SET after_json=? WHERE id=?",
                (json.dumps(state), op["id"]),
            )


def enrollment(connection, enrollment_id):
    return one(
        connection, "SELECT * FROM course_enrollments WHERE id=?", (enrollment_id,)
    )


def enrollment_access(connection, enrollment_id):
    return rows(
        connection,
        "SELECT group_id,valid_from FROM course_group_access WHERE enrollment_id=? AND valid_to IS NULL",
        (enrollment_id,),
    )


def revoke_transfer_access(connection, enrollment_id, group_id, now, teacher_id):
    connection.execute(
        "UPDATE course_group_access SET valid_to=?,revoked_by=?,updated_at=?,version=version+1 WHERE enrollment_id=? AND group_id=? AND valid_to IS NULL",
        (now, teacher_id, now, enrollment_id, group_id),
    )


def insert_transfer_plan(
    connection, event_record, base_plan, assignment_rows, teacher_id, now
):
    # An unrelated admin draft must never be implicitly published or discarded.
    # Reserve the working slot inside this transaction, then restore the admin
    # draft as stale. No intermediate snapshot is visible to another connection.
    working = one(
        connection,
        "SELECT * FROM classroom_assignment_plans WHERE in_person_event_id=? AND state IN ('draft','stale')",
        (event_record["id"],),
    )
    if working:
        connection.execute(
            "UPDATE classroom_assignment_plans SET state='superseded', confirmed_by_user_id=?, confirmed_at=?, superseded_at=?,updated_at=? WHERE id=?",
            (teacher_id, now, now, now, working["id"]),
        )
    from db_methods.pwa.classroom_assignments import (
        insert_plan,
        replace_assignments,
        supersede_confirmed_plan,
        confirm_plan,
    )

    plan_id, _ = insert_plan(
        connection,
        event_id=event_record["id"],
        layout_id=base_plan["layout_version_id"],
        base_plan_id=base_plan["id"],
        actor_user_id=teacher_id,
        now=now,
    )
    replace_assignments(connection, plan_id=plan_id, rows=assignment_rows, now=now)
    supersede_confirmed_plan(connection, event_id=event_record["id"], now=now)
    confirm_plan(
        connection,
        plan_id=plan_id,
        expected_version=1,
        actor_user_id=teacher_id,
        now=now,
    )
    if working:
        connection.execute(
            "UPDATE classroom_assignment_plans SET state='stale',stale_reason='live_transfer',confirmed_by_user_id=NULL,confirmed_at=NULL,superseded_at=NULL,version=version+1,updated_at=? WHERE id=?",
            (now, working["id"]),
        )
    return plan(connection, event_record["id"])


def account_ids(connection, student_id):
    return [
        r["public_id"]
        for r in rows(
            connection,
            "SELECT public_id FROM auth_accounts WHERE linked_user_id=? AND audience='student' AND status='active'",
            (student_id,),
        )
    ]


def publish_praise(connection, student_id, session_id, lesson_id, now):
    from db_methods.pwa.notifications import insert_event

    for account in rows(
        connection,
        "SELECT id FROM auth_accounts WHERE linked_user_id=? AND audience='student' AND status='active'",
        (student_id,),
    ):
        insert_event(
            connection,
            account_id=account["id"],
            category="review_completed",
            dedupe_key=f"oral-praise:{session_id}:{student_id}:{lesson_id}",
            route="/student/notifications",
            payload_json=json.dumps(
                dict(
                    title="Очень круто!",
                    body="Преподаватель похвалил ваш устный приём.",
                    kind="oral_praise",
                ),
                ensure_ascii=False,
            ),
            occurred_at=now,
            deliver_after=now,
            created_at=now,
        )


def cell_cursor(connection):
    return one(connection, "SELECT seq FROM live_mark_clock WHERE id=1")["seq"]


def owner_accounts(connection, student_public_id):
    from db_methods.pwa.classroom_assignments import list_assignment_owner_accounts

    student = one(
        connection, "SELECT id FROM users WHERE public_id=?", (student_public_id,)
    )
    return (
        []
        if student is None
        else list_assignment_owner_accounts(connection, (student["id"],))
    )


def condition_document(connection, lesson_id, problem_id):
    """Published condition including its shared stem/subparts; live-marking.md."""
    material = connection.execute(
        """SELECT d.content_text,pr.source_ordinal
        FROM lesson_publications lp
        JOIN problem_revisions pr ON pr.content_revision_id=lp.revision_id
        JOIN content_derivatives d ON d.revision_id=lp.revision_id
          AND d.kind='web_ast' AND d.invalidated_at IS NULL
        WHERE lp.group_lesson_id=? AND lp.kind='condition' AND lp.state='published'
          AND pr.problem_id=? ORDER BY d.id DESC LIMIT 1""",
        (lesson_id, problem_id),
    ).fetchone()
    if material is None:
        return None
    document = json.loads(material["content_text"])
    document["problems"] = [
        p for p in document["problems"] if p["ordinal"] == material["source_ordinal"]
    ]
    return document if document["problems"] else None

"""Live marking rules; authoritative decisions: vmshpwa/docs/live-marking.md."""

from __future__ import annotations

import hashlib
import json

from db_methods.pwa import live_marking as db
from db_methods.pwa import admin_enrollments as enrollments
from db_methods.pwa.classroom_assignments import grant_group_access
from db_methods.pwa.family_enrollment import sync_legacy_single_course_user
from helpers.consts import VERDICT_DECODER


class LiveMarkingError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(value, code="not_found"):
    if not value:
        raise LiveMarkingError(code)
    return value


def course_allowed(principal, course):
    require(principal.has_staff_course_access(course["public_id"]), "forbidden")


def course_record(connection, principal, course_id):
    course = require(
        next((c for c in db.courses(connection) if c["public_id"] == course_id), None)
    )
    course_allowed(principal, course)
    return course


def context(connection, principal, spec, *, writable=False):
    if spec["mode"] == "zoom":
        session = require(db.session(connection, spec["contextId"]))
        require(session["teacher_id"] == principal.linked_user_id, "forbidden")
        require(
            principal.has_staff_course_access(session["course_public_id"]), "forbidden"
        )
        if writable:
            require(session["finished_at"] is None, "session_finished")
        return dict(
            session=session,
            course_id=session["course_id"],
            event=None,
            room=None,
            plan=None,
        )
    event = require(db.event(connection, spec["contextId"]))
    room = require(
        next(
            (
                r
                for r in db.rooms(connection, event["id"])
                if r["public_id"] == spec.get("roomId")
            ),
            None,
        )
    )
    require(
        principal.has_staff_group_access(
            course_public_id=room["course_public_id"],
            group_public_id=room["group_public_id"],
        ),
        "forbidden",
    )
    plan = require(db.plan(connection, event["id"]), "plan_unavailable")
    require(plan["layout_version_id"] == room["layout_id"], "plan_unavailable")
    return dict(
        session=None, course_id=room["course_id"], event=event, room=room, plan=plan
    )


def lesson_context(connection, principal, spec, *, writable=False):
    ctx = context(connection, principal, spec, writable=writable)
    lesson = require(db.lesson(connection, spec["lessonId"]))
    require(lesson["course_id"] == ctx["course_id"], "forbidden")
    if ctx["room"]:
        require(lesson["group_id"] == ctx["room"]["group_id"], "forbidden")
    require(db.problems(connection, lesson["id"]), "not_found")
    return ctx, lesson


def student_payload(s):
    return dict(
        studentId=s["student_public_id"],
        displayName=" ".join(filter(None, [s["surname"], s["name"]])),
        middleName=s["middlename"] or None,
        grade=s["grade"],
        groupId=s["group_public_id"],
        groupName=s["group_name"],
        attendanceMode=s["attendance_mode"],
        enrollmentVersion=s["version"],
    )


def lesson_payload(lesson):
    return dict(
        lessonId=lesson["public_id"],
        number=lesson["lesson_number"],
        groupId=lesson["group_public_id"],
        groupName=lesson["group_name"],
    )


def catalog(connection, principal):
    courses = [
        c
        for c in db.courses(connection)
        if principal.has_staff_course_access(c["public_id"])
    ]
    events = []
    for e in db.events(connection):
        rooms = [
            r
            for r in db.rooms(connection, e["id"])
            if principal.has_staff_group_access(
                course_public_id=r["course_public_id"],
                group_public_id=r["group_public_id"],
            )
        ]
        if rooms:
            events.append(
                dict(
                    eventId=e["public_id"],
                    name=e["name"],
                    startsAt=e["starts_at"],
                    status=e["status"],
                    rooms=[
                        dict(
                            roomId=r["public_id"],
                            name=r["name"],
                            courseId=r["course_public_id"],
                            groupId=r["group_public_id"],
                            groupName=r["group_name"],
                            lessonId=r["lesson_public_id"],
                        )
                        for r in rooms
                    ],
                )
            )
    return dict(
        courses=[
            dict(
                courseId=c["public_id"],
                name=c["name"],
                lessons=[
                    lesson_payload(item) for item in db.lessons(connection, c["id"])
                ],
                sessions=[
                    dict(
                        sessionId=s["id"],
                        createdAt=s["created_at"],
                        finishedAt=s["finished_at"],
                    )
                    for s in db.sessions(connection, principal.linked_user_id, c["id"])
                ],
            )
            for c in courses
        ],
        events=events,
    )


def directory(connection, principal, course_id):
    course = course_record(connection, principal, course_id)
    histories = {}
    seen = set()
    for h in db.room_history(connection, course["id"]):
        key = (h["student_user_id"], h["event_id"])
        if key in seen:
            continue
        seen.add(key)
        histories.setdefault(h["student_user_id"], []).append(
            dict(
                eventId=h["event_id"],
                eventName=h["event_name"],
                startsAt=h["starts_at"],
                roomName=h["room_name"],
            )
        )
    return dict(
        students=[
            dict(**student_payload(s), rooms=histories.get(s["student_id"], []))
            for s in db.students(connection, course["id"])
        ]
    )


def board(connection, principal, spec):
    ctx, lesson = lesson_context(connection, principal, spec)
    students = db.students(connection, ctx["course_id"])
    if ctx["room"]:
        ids = {
            a["course_enrollment_id"]
            for a in db.assignments(connection, ctx["plan"]["id"])
            if a["classroom_id"] == ctx["room"]["id"]
        }
        students = [s for s in students if s["enrollment_id"] in ids]
    else:
        students = [
            s for s in students if s["student_public_id"] == spec.get("studentId")
        ]
    attendance = (
        {}
        if not ctx["event"]
        else {a["student_id"]: a for a in db.attendance(connection, ctx["event"]["id"])}
    )
    problems = db.problems(connection, lesson["id"])
    result = dict(
        lesson=lesson_payload(lesson),
        students=[
            dict(
                **student_payload(s),
                attendance=attendance.get(s["student_id"], {}).get("state", "unmarked"),
                attendanceVersion=attendance.get(s["student_id"], {}).get("version", 0),
            )
            for s in students
        ],
        problems=[
            dict(
                problemId=p["public_id"],
                label=p["display_number"],
                title=p["title"],
                oral=p["problem_type"] in (3, 4),
                number=p["prob"],
            )
            for p in problems
        ],
        planId=None if not ctx["plan"] else ctx["plan"]["public_id"],
        readOnly=bool(ctx["session"] and ctx["session"]["finished_at"]),
        visit=None,
    )
    if ctx["session"] and students:
        v = db.visit(
            connection, ctx["session"]["id"], students[0]["student_id"], lesson["id"]
        )
        if v:
            result["visit"] = dict(
                version=v["version"],
                reactions=db.reactions(connection, v["conversation_id"]),
                praisedAt=v["praised_at"],
            )
    return result


def cell_payload(row, student_id, problem_id):
    verdict = row.get("verdict")
    return dict(
        studentId=student_id,
        problemId=problem_id,
        version=row["version"],
        verdict=verdict,
        symbol="" if verdict is None else VERDICT_DECODER.get(verdict, ""),
        teacherId=row.get("teacher_public_id"),
        updatedAt=row.get("ts"),
    )


def read_cells(connection, principal, spec, after=None, scope=None):
    ctx, lesson = lesson_context(connection, principal, spec)
    students = db.students(connection, ctx["course_id"])
    if ctx["room"]:
        ids = {
            a["course_enrollment_id"]
            for a in db.assignments(connection, ctx["plan"]["id"])
            if a["classroom_id"] == ctx["room"]["id"]
        }
        students = [s for s in students if s["enrollment_id"] in ids]
    else:
        students = [
            s for s in students if s["student_public_id"] == spec.get("studentId")
        ]
    problems = db.problems(connection, lesson["id"])
    student_ids = {s["student_id"]: s["student_public_id"] for s in students}
    problem_ids = {p["id"]: p["public_id"] for p in problems}
    cursor = db.cell_cursor(connection)
    current_scope = hashlib.sha256(
        json.dumps([list(student_ids), list(problem_ids)]).encode()
    ).hexdigest()
    reset = after is None or after > cursor or scope != current_scope
    return dict(
        cursor=cursor,
        scope=current_scope,
        reset=reset,
        cells=[
            cell_payload(c, student_ids[c["student_id"]], problem_ids[c["problem_id"]])
            for c in db.cells(
                connection,
                list(student_ids),
                list(problem_ids),
                None if reset else after,
            )
        ],
    )


def session_start(connection, principal, course_id, session_id, now):
    course = course_record(connection, principal, course_id)
    existing = db.session(connection, session_id)
    if existing:
        require(
            existing["teacher_id"] == principal.linked_user_id
            and existing["course_id"] == course["id"],
            "conflict",
        )
        return dict(sessionId=existing["id"])
    active = next(
        (
            s
            for s in db.sessions(connection, principal.linked_user_id, course["id"])
            if s["finished_at"] is None
        ),
        None,
    )
    if active:
        return dict(sessionId=active["id"])
    db.insert_session(
        connection, session_id, principal.linked_user_id, course["id"], now
    )
    return dict(sessionId=session_id)


def session_finish(connection, principal, session_id, now):
    context(connection, principal, dict(mode="zoom", contextId=session_id))
    db.finish_session(connection, session_id, now)
    return dict(sessionId=session_id)


def visit_student(connection, principal, spec, now):
    ctx, lesson = lesson_context(connection, principal, spec)
    require(ctx["session"], "invalid")
    s = require(db.student(connection, ctx["course_id"], spec["studentId"]))
    v = db.visit(connection, spec["contextId"], s["student_id"], lesson["id"])
    if not v:
        require(ctx["session"]["finished_at"] is None, "session_finished")
        v = db.insert_visit(
            connection,
            spec["contextId"],
            s["student_id"],
            lesson,
            principal.linked_user_id,
            now,
        )
    return dict(
        version=v["version"],
        reactions=db.reactions(connection, v["conversation_id"]),
        praisedAt=v["praised_at"],
    )


def session_visits(connection, principal, session_id):
    context(connection, principal, dict(mode="zoom", contextId=session_id))
    return dict(
        visits=[
            dict(
                studentId=v["student_public_id"],
                displayName=" ".join(filter(None, [v["surname"], v["name"]])),
                lessonId=v["lesson_public_id"],
                updatedAt=v["updated_at"],
                changedCount=v["changed_count"],
            )
            for v in db.visits(connection, session_id)
        ]
    )


def operation_history(connection, principal, spec):
    context(connection, principal, spec)
    return dict(
        operations=[
            dict(
                operationId=o["id"],
                kind=o["kind"],
                createdAt=o["created_at"],
                undone=o["undone_at"] is not None,
                state=json.loads(o["after_json"]),
            )
            for o in db.history(connection, principal.linked_user_id, spec["contextId"])
        ]
    )


def transfer_state(connection, ctx, s):
    enrollment = db.enrollment(connection, s["enrollment_id"])
    current_plan = db.plan(connection, ctx["event"]["id"])
    assignment = next(
        (
            a
            for a in db.assignments(connection, current_plan["id"])
            if a["course_enrollment_id"] == s["enrollment_id"]
        ),
        None,
    )
    if assignment:
        assignment = {
            k: assignment[k]
            for k in (
                "course_enrollment_id",
                "group_lesson_id",
                "group_id",
                "classroom_id",
                "status",
                "source",
            )
        }
    attendance = db.attendance_cell(connection, ctx["event"]["id"], s["student_id"])
    state = dict(
        enrollment=enrollment,
        assignment=assignment,
        attendance=attendance,
        access=db.enrollment_access(connection, s["enrollment_id"]),
    )
    state["version"] = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode()
    ).hexdigest()
    return state


def transfer_apply(connection, ctx, s, state, teacher_id, operation_id, now):
    current = db.enrollment(connection, s["enrollment_id"])
    target = state["enrollment"]
    require(
        enrollments.update_enrollment(
            connection,
            enrollment_id=current["id"],
            expected_version=current["version"],
            active_group_id=target["active_group_id"],
            attendance_mode=target["attendance_mode"],
            status=current["status"],
            actor_user_id=teacher_id,
            now=now,
        ),
        "conflict",
    )
    if current["active_group_id"] != target["active_group_id"]:
        enrollments.insert_group_event(
            connection,
            enrollment_id=current["id"],
            course_id=current["course_id"],
            previous_group_id=current["active_group_id"],
            new_group_id=target["active_group_id"],
            actor_user_id=teacher_id,
            request_id=operation_id + ":group",
            now=now,
        )
    if current["attendance_mode"] != target["attendance_mode"]:
        enrollments.insert_mode_event(
            connection,
            enrollment_id=current["id"],
            course_id=current["course_id"],
            previous_mode=current["attendance_mode"],
            new_mode=target["attendance_mode"],
            actor_user_id=teacher_id,
            request_id=operation_id + ":mode",
            now=now,
        )
    grant_group_access(
        connection,
        enrollment_id=current["id"],
        course_id=current["course_id"],
        group_id=target["active_group_id"],
        actor_user_id=teacher_id,
        now=now,
    )
    sync_legacy_single_course_user(
        connection,
        student_user_id=s["student_id"],
        active_group_id=target["active_group_id"],
        attendance_mode=target["attendance_mode"],
        group_changed=current["active_group_id"] != target["active_group_id"],
        mode_changed=current["attendance_mode"] != target["attendance_mode"],
        now=now,
    )
    base = db.plan(connection, ctx["event"]["id"])
    assignments = [
        a
        for a in db.assignments(connection, base["id"])
        if a["course_enrollment_id"] != current["id"]
    ]
    if state["assignment"]:
        assignments.append(state["assignment"])
    keys = (
        "course_enrollment_id",
        "group_lesson_id",
        "group_id",
        "classroom_id",
        "status",
        "source",
    )
    require(
        db.insert_transfer_plan(
            connection,
            ctx["event"],
            base,
            [tuple(a[k] for k in keys) for a in assignments],
            teacher_id,
            now,
        ),
        "admin_draft",
    )
    db.set_attendance(
        connection,
        ctx["event"]["id"],
        s["student_id"],
        state["attendance"]["state"],
        state["attendance"].get("teacher_id") or teacher_id,
    )


def execute(connection, principal, command, now):
    teacher_id = principal.linked_user_id
    spec = command["context"]
    ctx = context(connection, principal, spec)
    operation_id = command["operationId"]
    existing = db.operation(connection, operation_id)
    if existing:
        require(
            existing["teacher_id"] == teacher_id
            and json.loads(existing["request_json"]) == command,
            "conflict",
        )
        return dict(
            operationId=operation_id,
            replayed=True,
            state=json.loads(existing["after_json"]),
        )
    context(connection, principal, spec, writable=True)
    kind = command["kind"]
    if kind == "undo":
        return undo(connection, principal, command, now)
    s = require(db.student(connection, ctx["course_id"], command["studentId"]))
    student_id = s["student_id"]
    before = {}
    after = dict(studentId=s["student_public_id"], kind=kind)
    if kind in ("mark", "reaction", "praise"):
        ctx, lesson = lesson_context(connection, principal, spec, writable=True)
        if ctx["room"]:
            require(
                any(
                    a["course_enrollment_id"] == s["enrollment_id"]
                    and a["classroom_id"] == ctx["room"]["id"]
                    for a in db.assignments(connection, ctx["plan"]["id"])
                ),
                "conflict",
            )
        v = None
        if ctx["session"]:
            v = db.visit(connection, spec["contextId"], student_id, lesson["id"])
            if v is None:
                v = db.insert_visit(
                    connection, spec["contextId"], student_id, lesson, teacher_id, now
                )
        after["lessonId"] = lesson["public_id"]
        if kind == "mark":
            problem = require(
                next(
                    (
                        p
                        for p in db.problems(connection, lesson["id"])
                        if p["public_id"] == command["problemId"]
                    ),
                    None,
                )
            )
            before = db.cell(connection, student_id, problem["id"])
            require(before["version"] == command["expectedVersion"], "conflict")
            verdict = 18 if command["value"] == "plus" else -1
            db.append_result(
                connection,
                student_id=student_id,
                problem=problem,
                lesson=lesson,
                teacher_id=teacher_id,
                verdict=verdict,
                conversation_id=None if v is None else v["conversation_id"],
                now=now,
            )
            current = db.cell(connection, student_id, problem["id"])
            after.update(
                cell_payload(current, s["student_public_id"], problem["public_id"])
            )
            after.update(
                objectKey=f"mark:{student_id}:{problem['id']}",
                previousVersion=before["version"],
            )
        else:
            require(v is not None, "invalid")
            require(v["version"] == command["expectedVersion"], "conflict")
            before = dict(
                visit=v, reactions=db.reactions(connection, v["conversation_id"])
            )
            if kind == "reaction":
                db.set_reactions(
                    connection, v["conversation_id"], command["reactions"], now
                )
            else:
                db.publish_praise(
                    connection, student_id, spec["contextId"], lesson["id"], now
                )
            after.update(
                objectKey=f"visit:{spec['contextId']}:{student_id}:{lesson['id']}",
                previousVersion=v["version"],
            )
        if v:
            db.touch_visit(
                connection,
                spec["contextId"],
                student_id,
                lesson["id"],
                now,
                praised=kind == "praise",
                advance_version=kind != "mark",
            )
            current_visit = db.visit(
                connection, spec["contextId"], student_id, lesson["id"]
            )
            if kind != "mark":
                after.update(
                    version=current_visit["version"],
                    reactions=db.reactions(connection, v["conversation_id"]),
                    praisedAt=current_visit["praised_at"],
                )
    elif kind == "attendance":
        require(ctx["event"], "invalid")
        require(
            any(
                a["course_enrollment_id"] == s["enrollment_id"]
                and a["classroom_id"] == ctx["room"]["id"]
                for a in db.assignments(connection, ctx["plan"]["id"])
            ),
            "conflict",
        )
        before = db.attendance_cell(connection, ctx["event"]["id"], student_id)
        require(before["version"] == command["expectedVersion"], "conflict")
        db.set_attendance(
            connection, ctx["event"]["id"], student_id, command["value"], teacher_id
        )
        after.update(
            version=before["version"] + 1,
            value=command["value"],
            objectKey=f"attendance:{ctx['event']['id']}:{student_id}",
            previousVersion=before["version"],
        )
    elif kind == "transfer":
        require(ctx["event"], "invalid")
        require(
            s["version"] == command["enrollmentVersion"]
            and ctx["plan"]["public_id"] == command["planId"],
            "conflict",
        )
        before = transfer_state(connection, ctx, s)
        target = dict(
            enrollment={
                **before["enrollment"],
                "active_group_id": ctx["room"]["group_id"],
                "attendance_mode": "in_person",
            },
            attendance=dict(state="present", teacher_id=teacher_id),
            assignment=dict(
                course_enrollment_id=s["enrollment_id"],
                group_lesson_id=ctx["room"]["group_lesson_id"],
                group_id=ctx["room"]["group_id"],
                classroom_id=ctx["room"]["id"],
                status="assigned",
                source="manual",
            ),
        )
        transfer_apply(connection, ctx, s, target, teacher_id, operation_id, now)
        after.update(
            version=transfer_state(connection, ctx, s)["version"],
            objectKey=f"transfer:{ctx['event']['id']}:{student_id}",
            previousVersion=before["version"],
        )
    else:
        raise LiveMarkingError("invalid")
    db.insert_operation(
        connection,
        operation_id,
        teacher_id,
        spec["contextId"],
        kind,
        command,
        before,
        after,
        now,
        undoable=kind != "praise",
    )
    return dict(operationId=operation_id, replayed=False, state=after)


def undo(connection, principal, command, now):
    op = require(db.operation(connection, command["targetOperationId"]))
    require(
        op["teacher_id"] == principal.linked_user_id
        and op["context_id"] == command["context"]["contextId"],
        "forbidden",
    )
    require(op["undone_at"] is None and op["undoable"], "conflict")
    original = json.loads(op["request_json"])
    spec = original["context"]
    ctx = context(connection, principal, spec, writable=True)
    before = json.loads(op["before_json"])
    after = json.loads(op["after_json"])
    s = require(db.student(connection, ctx["course_id"], original["studentId"]))
    if op["kind"] == "mark":
        current = db.cell(connection, before["student_id"], before["problem_id"])
        require(current["version"] == after["version"], "conflict")
        db.restore_cell(
            connection, before["student_id"], before["problem_id"], before["result_id"]
        )
        state = cell_payload(
            db.cell(connection, before["student_id"], before["problem_id"]),
            after["studentId"],
            after["problemId"],
        )
    elif op["kind"] == "attendance":
        current = db.attendance_cell(
            connection, before["event_id"], before["student_id"]
        )
        require(current["version"] == after["version"], "conflict")
        db.set_attendance(
            connection,
            before["event_id"],
            before["student_id"],
            before["state"],
            before["teacher_id"] or principal.linked_user_id,
        )
        state = dict(value=before["state"], version=current["version"] + 1)
    elif op["kind"] == "reaction":
        v = before["visit"]
        current = db.visit(
            connection, v["session_id"], v["student_id"], v["group_lesson_id"]
        )
        require(current["version"] == after["version"], "conflict")
        db.set_reactions(connection, v["conversation_id"], before["reactions"], now)
        db.touch_visit(
            connection, v["session_id"], v["student_id"], v["group_lesson_id"], now
        )
        state = dict(version=current["version"] + 1, reactions=before["reactions"])
    elif op["kind"] == "transfer":
        require(
            transfer_state(connection, ctx, s)["version"] == after["version"],
            "conflict",
        )
        transfer_apply(
            connection,
            ctx,
            s,
            before,
            principal.linked_user_id,
            command["operationId"],
            now,
        )
        prior_groups = {a["group_id"] for a in before["access"]}
        if ctx["room"]["group_id"] not in prior_groups:
            db.revoke_transfer_access(
                connection,
                s["enrollment_id"],
                ctx["room"]["group_id"],
                now,
                principal.linked_user_id,
            )
        state = dict(version=transfer_state(connection, ctx, s)["version"])
    else:
        raise LiveMarkingError("invalid")
    db.mark_undone(connection, op["id"], now)
    db.previous_operation_version(
        connection, principal.linked_user_id, op["context_id"], after, state["version"]
    )
    state.update(kind="undo", studentId=after["studentId"], targetOperationId=op["id"])
    if after.get("lessonId"):
        state["lessonId"] = after["lessonId"]
    db.insert_operation(
        connection,
        command["operationId"],
        principal.linked_user_id,
        op["context_id"],
        "undo",
        command,
        after,
        state,
        now,
        undoable=False,
    )
    return dict(operationId=command["operationId"], replayed=False, state=state)


def condition(connection, principal, spec, problem_id):
    _, lesson = lesson_context(connection, principal, spec)
    problem = require(
        next(
            (
                p
                for p in db.problems(connection, lesson["id"])
                if p["public_id"] == problem_id
            ),
            None,
        )
    )
    return dict(document=db.condition_document(connection, lesson["id"], problem["id"]))

"""Admin edits with replay, optimistic versions and audit; docs/teacher-work.md."""

from collections import defaultdict
from datetime import datetime
import json
import math
import re
from zoneinfo import ZoneInfo

from db_methods.pwa import teacher_work as records
from models.pwa.teacher_work import fingerprint, moment, normalize_name
from models.pwa.teacher_work_runner import timestamp


class WorkConflict(ValueError):
    pass


def require_version(actual, expected):
    if (
        isinstance(expected, bool)
        or not isinstance(expected, int)
        or actual != expected
    ):
        raise WorkConflict("version_conflict")


def teacher_id(connection, value):
    row = connection.execute(
        "SELECT id FROM users WHERE public_id=? AND type IN (2,128)", (value,)
    ).fetchone()
    if row is None:
        raise ValueError("teacher_not_found")
    return row["id"]


def hours(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 10000
    ):
        raise ValueError("invalid_hours")
    return float(value)


def execute_command(connection, course_id, actor, body):
    key = body.get("idempotencyKey")
    if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9._:-]{1,128}", key):
        raise ValueError("invalid_key")
    digest = fingerprint([course_id, body])
    replay = records.replay(connection, actor, key)
    if replay:
        if replay["payload_sha256"] != digest:
            raise WorkConflict("idempotency_conflict")
        return json.loads(replay["after_json"])["receipt"]
    action, now = body["action"], timestamp()
    before, after, entity = None, None, ""
    if action == "settings":
        before = records.settings(connection, course_id)
        require_version(before["version"], body.get("expectedVersion"))
        norm = hours(body.get("normHours"))
        if norm > 24:
            raise ValueError("invalid_hours")
        connection.execute(
            """INSERT INTO teacher_work_settings(course_id,norm_hours,version,updated_at,updated_by)
          VALUES(?,?,?,?,?) ON CONFLICT(course_id) DO UPDATE SET norm_hours=excluded.norm_hours,
          version=excluded.version,updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (course_id, norm, before["version"] + 1, now, actor),
        )
        after, entity = {"version": before["version"] + 1}, "settings"
    elif action == "alias":
        name = body.get("name")
        state = body.get("state")
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 500
            or state not in ("mapped", "ignored", "unresolved")
        ):
            raise ValueError("invalid_alias")
        entity = normalize_name(name)
        old = connection.execute(
            "SELECT * FROM teacher_work_aliases WHERE course_id=? AND normalized_name=?",
            (course_id, entity),
        ).fetchone()
        before = dict(old) if old else None
        version = before["version"] if before else 0
        require_version(version, body.get("expectedVersion"))
        teacher = (
            teacher_id(connection, body.get("teacherId")) if state == "mapped" else None
        )
        connection.execute(
            """INSERT INTO teacher_work_aliases VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(course_id,normalized_name) DO UPDATE SET original_name=excluded.original_name,
          teacher_id=excluded.teacher_id,state=excluded.state,version=excluded.version,
          updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (course_id, entity, name, teacher, state, version + 1, now, actor),
        )
        after = {"version": version + 1}
    elif action == "override":
        entity = body.get("cellKey")
        if not isinstance(entity, str) or not re.fullmatch(
            r"(school|zoom|written):\d+:[\d-]+", entity
        ):
            raise ValueError("invalid_cell")
        validate_cell_key(connection, course_id, entity)
        old = connection.execute(
            "SELECT * FROM teacher_work_overrides WHERE course_id=? AND cell_key=?",
            (course_id, entity),
        ).fetchone()
        before = dict(old) if old else None
        require_version(before["version"] if before else 0, body.get("expectedVersion"))
        comment = body.get("comment")
        if not isinstance(comment, str) or not 1 <= len(comment.strip()) <= 2000:
            raise ValueError("comment_required")
        run = records.latest_run(connection, course_id, completed=True)
        cells = json.loads(run["snapshot_json"])["cells"] if run else []
        cell = next((c for c in cells if c["key"] == entity), None)
        source = cell["fingerprint"] if cell else fingerprint([])
        if body.get("sourceFingerprint") != source:
            raise WorkConflict("source_changed")
        version = (before["version"] if before else 0) + 1
        value = None if body.get("hours") is None else hours(body["hours"])
        # A cleared override is a tombstone: versions never reset (avoids ABA writes).
        connection.execute(
            """INSERT INTO teacher_work_overrides VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(course_id,cell_key) DO UPDATE SET hours=excluded.hours,comment=excluded.comment,
            source_fingerprint=excluded.source_fingerprint,version=excluded.version,
            updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (course_id, entity, value, comment.strip(), source, version, now, actor),
        )
        after = {"version": version}
    elif action == "roster":
        event = connection.execute(
            """SELECT DISTINCT e.* FROM in_person_events e
          JOIN in_person_event_group_lessons eg ON eg.in_person_event_id=e.id
          JOIN group_lessons gl ON gl.id=eg.group_lesson_id WHERE gl.course_id=? AND e.public_id=?
          AND e.status!='cancelled' """,
            (course_id, body.get("eventId")),
        ).fetchone()
        if event is None:
            raise ValueError("event_not_found")
        require_version(event["version"], body.get("eventVersion"))
        entity = event["public_id"]
        old = connection.execute(
            "SELECT * FROM teacher_work_rosters WHERE course_id=? AND event_id=?",
            (course_id, event["id"]),
        ).fetchone()
        before = dict(old) if old else None
        version = before["version"] if before else 0
        require_version(version, body.get("expectedVersion"))
        raw, rows, state = body.get("rawText"), body.get("rows"), body.get("state")
        if (
            not isinstance(raw, str)
            or not 1 <= len(raw) <= 100000
            or not isinstance(rows, list)
            or len(rows) > 500
            or state not in ("draft", "confirmed")
        ):
            raise ValueError("invalid_roster")
        zone = connection.execute(
            "SELECT s.timezone FROM courses c JOIN seasons s ON s.id=c.season_id WHERE c.id=?",
            (course_id,),
        ).fetchone()["timezone"]
        grouped = defaultdict(list)
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "teacherId",
                "room",
                "startsTime",
                "endsTime",
                "source",
                "name",
                "rowId",
            }:
                raise ValueError("invalid_row")
            if not all(
                isinstance(row[k], str) and len(row[k]) <= 2000
                for k in ("room", "source", "name", "rowId")
            ):
                raise ValueError("invalid_row")
            for field in ("startsTime", "endsTime"):
                if row[field] is not None and (
                    not isinstance(row[field], str)
                    or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", row[field])
                ):
                    raise ValueError("invalid_time")
            if row["teacherId"]:
                grouped[teacher_id(connection, row["teacherId"])].append(row)
            elif state == "confirmed":
                raise ValueError("unresolved_teacher")
        if state == "confirmed":
            norm = records.settings(connection, course_id)["norm_hours"]
            start = moment(event["starts_at"], zone).astimezone(ZoneInfo(zone))
            end = moment(event["ends_at"], zone).astimezone(ZoneInfo(zone))
            for teacher, matches in grouped.items():
                starts = {r["startsTime"] for r in matches if r["startsTime"]}
                ends = {r["endsTime"] for r in matches if r["endsTime"]}
                if len(starts) > 1 or len(ends) > 1:
                    raise ValueError("conflicting_times")
                actual_start = (
                    datetime.fromisoformat(
                        start.date().isoformat() + "T" + next(iter(starts))
                    ).replace(tzinfo=start.tzinfo)
                    if starts
                    else start
                )
                actual_end = (
                    datetime.fromisoformat(
                        end.date().isoformat() + "T" + next(iter(ends))
                    ).replace(tzinfo=end.tzinfo)
                    if ends
                    else end
                )
                if actual_end <= actual_start:
                    raise ValueError("invalid_interval")
                old_shift = connection.execute(
                    "SELECT * FROM teacher_work_shifts WHERE course_id=? AND event_id=? AND teacher_id=?",
                    (course_id, event["id"], teacher),
                ).fetchone()
                connection.execute(
                    """INSERT INTO teacher_work_shifts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(course_id,event_id,teacher_id) DO UPDATE SET rooms_json=excluded.rooms_json,
                  starts_at=excluded.starts_at,ends_at=excluded.ends_at,raw_json=excluded.raw_json,
                  version=excluded.version,updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                    (
                        course_id,
                        event["id"],
                        teacher,
                        json.dumps(sorted({r["room"] for r in matches})),
                        actual_start.isoformat(),
                        actual_end.isoformat(),
                        old_shift["norm_hours"] if old_shift else norm,
                        old_shift["standard_starts_at"]
                        if old_shift
                        else event["starts_at"],
                        old_shift["standard_ends_at"]
                        if old_shift
                        else event["ends_at"],
                        json.dumps(matches, ensure_ascii=False),
                        old_shift["version"] + 1 if old_shift else 1,
                        now,
                        actor,
                    ),
                )
            if body.get("replace") is True:
                existing = records.rows(
                    connection,
                    "SELECT teacher_id FROM teacher_work_shifts WHERE course_id=? AND event_id=?",
                    (course_id, event["id"]),
                )
                for shift in existing:
                    if shift["teacher_id"] not in grouped:
                        connection.execute(
                            "DELETE FROM teacher_work_shifts WHERE course_id=? AND event_id=? AND teacher_id=?",
                            (course_id, event["id"], shift["teacher_id"]),
                        )
        connection.execute(
            """INSERT INTO teacher_work_rosters(course_id,event_id,raw_text,source_sha256,state,
          rows_json,version,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(course_id,event_id) DO UPDATE SET raw_text=excluded.raw_text,source_sha256=excluded.source_sha256,
          state=excluded.state,rows_json=excluded.rows_json,version=excluded.version,
          updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
            (
                course_id,
                event["id"],
                raw,
                fingerprint(raw),
                state,
                json.dumps(rows, ensure_ascii=False),
                version + 1,
                now,
                actor,
            ),
        )
        after = {"version": version + 1}
    else:
        raise ValueError("invalid_action")
    if action == "settings":
        state = records.settings(connection, course_id)
    elif action == "alias":
        state = dict(
            connection.execute(
                "SELECT * FROM teacher_work_aliases WHERE course_id=? AND normalized_name=?",
                (course_id, entity),
            ).fetchone()
        )
        # docs/teacher-work.md: canonical receipt updates all equivalent signatures.
        after["alias"] = {
            key: state[key]
            for key in ("normalized_name", "teacher_id", "state", "version")
        }
    elif action == "override":
        row = connection.execute(
            "SELECT * FROM teacher_work_overrides WHERE course_id=? AND cell_key=?",
            (course_id, entity),
        ).fetchone()
        state = dict(row) if row else None
    else:
        state = {
            "roster": dict(
                connection.execute(
                    "SELECT * FROM teacher_work_rosters WHERE course_id=? AND event_id=?",
                    (course_id, event["id"]),
                ).fetchone()
            ),
            "shifts": records.rows(
                connection,
                "SELECT * FROM teacher_work_shifts WHERE course_id=? AND event_id=?",
                (course_id, event["id"]),
            ),
        }
    records.audit(
        connection,
        course_id,
        actor,
        key,
        digest,
        action,
        entity,
        before,
        {"receipt": after, "state": state},
        now,
    )
    return after


def validate_cell_key(connection, course_id, value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(school|zoom|written):\d+:[\d-]+", value
    ):
        raise ValueError("invalid_cell")
    kind, teacher, slot = value.split(":")
    teacher_id(connection, "u-" + teacher)
    if kind == "written":
        if (
            not re.fullmatch(r"0|[1-9]\d*", slot)
            or connection.execute(
                "SELECT 1 FROM course_lessons WHERE course_id=? AND lesson_number=?",
                (course_id, int(slot)),
            ).fetchone()
            is None
        ):
            raise ValueError("invalid_lesson")
    else:
        from datetime import date

        day = date.fromisoformat(slot)
        season = connection.execute(
            "SELECT starts_on,ends_on FROM courses c JOIN seasons s ON s.id=c.season_id WHERE c.id=?",
            (course_id,),
        ).fetchone()
        if (
            day.isoformat() != slot
            or not season["starts_on"] <= slot <= season["ends_on"]
        ):
            raise ValueError("invalid_date")

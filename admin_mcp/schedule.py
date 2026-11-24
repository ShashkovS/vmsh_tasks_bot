"""Publication-bound hide timers; see vmshpwa/docs/admin-mcp/schedule.md."""

from datetime import UTC, datetime

from apps.pwa_api.errors import PwaApiError


def change(c, lesson, actor, target, object_id, object_version, event_version, due):
    if target in {"before", "after"}:
        obj = c.execute(
            """SELECT b.id,b.public_id,b.version,b.published_at || '/' || coalesce((SELECT max(e.id) FROM lesson_block_events e
                         WHERE e.block_id=b.id AND e.action IN ('published','schedule_activated')),0) stamp,b.published_revision_id rev
                         FROM lesson_blocks b WHERE b.group_lesson_id=? AND b.position=?""",
            (lesson, target),
        ).fetchone()
    else:
        obj = c.execute(
            """SELECT id,public_id,version,published_at stamp,revision_id rev
                         FROM lesson_publications WHERE group_lesson_id=? AND kind=? AND state='published'""",
            (lesson, target),
        ).fetchone()
    existing = c.execute(
        "SELECT version FROM lesson_hide_events WHERE lesson=? AND target=?",
        (lesson, target),
    ).fetchone()
    version = existing["version"] if existing else 0
    if version != event_version or (
        due is not None
        and (
            not obj
            or obj["public_id"] != object_id
            or obj["version"] != object_version
            or not obj["stamp"]
        )
    ):
        raise PwaApiError(
            status=409, code="schedule_changed", message="Перечитайте состояние занятия"
        )
    if due is None:
        if not existing:
            raise ValueError("no_hide_event")
        c.execute(
            "UPDATE lesson_hide_events SET state='cancelled',version=version+1 WHERE lesson=? AND target=?",
            (lesson, target),
        )
    else:
        instant = datetime.fromisoformat(due)
        if instant.tzinfo is None or instant <= datetime.now(UTC):
            raise ValueError("future_timestamp_with_timezone_required")
        c.execute(
            """INSERT INTO lesson_hide_events(lesson,target,object_id,revision,stamp,due,actor,state,version)
            VALUES(?,?,?,?,?,?,?,'scheduled',?) ON CONFLICT(lesson,target) DO UPDATE SET object_id=excluded.object_id,
            revision=excluded.revision,stamp=excluded.stamp,due=excluded.due,actor=excluded.actor,
            state='scheduled',version=excluded.version""",
            (
                lesson,
                target,
                obj["id"],
                obj["rev"],
                obj["stamp"],
                instant.astimezone(UTC).isoformat(),
                actor,
                version + 1,
            ),
        )
    return events(c, lesson)


def events(c, lesson):
    return [
        dict(r)
        for r in c.execute(
            "SELECT target,due,state,version FROM lesson_hide_events WHERE lesson=? ORDER BY target",
            (lesson,),
        )
    ]


def activate(c, now, limit):
    applied = []
    for event in c.execute(
        "SELECT * FROM lesson_hide_events WHERE state='scheduled' AND due<=? ORDER BY due,lesson,target LIMIT ?",
        (now, limit),
    ).fetchall():
        target = event["target"]
        if target in {"before", "after"}:
            changed = c.execute(
                """UPDATE lesson_blocks SET published_revision_id=NULL,published_at=NULL,
                updated_at=?,updated_by_user_id=?,version=version+1 WHERE id=? AND published_revision_id=? AND
                published_at || '/' || coalesce((SELECT max(e.id) FROM lesson_block_events e
                WHERE e.block_id=lesson_blocks.id AND e.action IN ('published','schedule_activated')),0)=?""",
                (
                    now,
                    event["actor"],
                    event["object_id"],
                    event["revision"],
                    event["stamp"],
                ),
            ).rowcount
            if changed:
                c.execute(
                    """INSERT INTO lesson_block_events(block_id,revision_id,action,actor_user_id,created_at,block_version)
                    SELECT id,?,'hidden',?,?,version FROM lesson_blocks WHERE id=?""",
                    (event["revision"], event["actor"], now, event["object_id"]),
                )
        else:
            changed = c.execute(
                """UPDATE lesson_publications SET state='hidden',hidden_at=?,terminal_at=?,terminal_by_user_id=?,
                updated_at=?,version=version+1 WHERE id=? AND revision_id=? AND published_at=? AND state='published'""",
                (
                    now,
                    now,
                    event["actor"],
                    now,
                    event["object_id"],
                    event["revision"],
                    event["stamp"],
                ),
            ).rowcount
        c.execute(
            "UPDATE lesson_hide_events SET state=?,version=version+1 WHERE lesson=? AND target=?",
            ("hidden" if changed else "superseded", event["lesson"], target),
        )
        if changed:
            applied.append(
                (
                    c.execute(
                        "SELECT public_id FROM group_lessons WHERE id=?",
                        (event["lesson"],),
                    ).fetchone()["public_id"],
                    target,
                )
            )
    return applied

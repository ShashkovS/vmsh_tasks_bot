from __future__ import annotations

from datetime import datetime, timedelta, timezone

import db_methods as db


def test_zoom_conversation_insert_and_update_check_time(live_seed_db):
    student = live_seed_db.get_user("qwerty1")
    teacher = live_seed_db.get_teacher()

    conv_id = db.zoom_conversation.insert(student_id=student.id, teacher_id=teacher.id, lesson=1, group_id="i27c")
    db.sql.conn.execute(
        "update zoom_conversation set ts = :ts where id = :id",
        {"ts": (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)).isoformat(), "id": conv_id},
    )
    db.sql.conn.commit()

    db.zoom_conversation.update_check_time_spent_sec(conv_id)
    row = db.sql.conn.execute("select * from zoom_conversation where id = :id", {"id": conv_id}).fetchone()

    assert row is not None
    assert row["check_time_spent_sec"] is not None
    assert row["check_time_spent_sec"] > 0

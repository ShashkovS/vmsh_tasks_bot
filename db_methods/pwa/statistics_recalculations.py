"""Durable manual calculation records; docs/lesson-statistics.md."""

import uuid


def find_operation(connection, actor, key):
    return connection.execute(
        "SELECT * FROM statistics_recalculations WHERE actor_user_id=? AND idempotency_key=?",
        (actor, key),
    ).fetchone()


def latest_operation(connection, course_id):
    return connection.execute(
        "SELECT * FROM statistics_recalculations WHERE course_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
        (course_id,),
    ).fetchone()


def create_operation(connection, course_id, actor, key, now):
    operation_id = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO statistics_recalculations "
        "(operation_id,course_id,actor_user_id,idempotency_key,state,started_at) "
        "VALUES(?,?,?,?,'running',?)",
        (operation_id, course_id, actor, key, now),
    )
    connection.commit()
    return operation_id


def fail_operation(connection, operation_id, now, code):
    connection.execute(
        "UPDATE statistics_recalculations SET state='failed', completed_at=?, error_code=? "
        "WHERE operation_id=? AND state='running'",
        (now, code, operation_id),
    )
    connection.commit()


def recover_interrupted(connection, now):
    # Caller holds the same exclusive lock as the timer and every manual worker.
    connection.execute(
        "UPDATE statistics_recalculations SET state='failed', completed_at=?, "
        "error_code='interrupted' WHERE state='running'",
        (now,),
    )
    connection.commit()


def payload(row):
    if row is None:
        return None
    return {
        "operationId": row["operation_id"],
        "state": row["state"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
        "runId": row["run_public_id"],
        "errorCode": row["error_code"],
    }

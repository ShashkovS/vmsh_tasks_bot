"""Managed teacher-work worker, atomic publication, shared lock; docs/teacher-work.md."""

import fcntl
import logging
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime

from db_methods.pwa import teacher_work as records
from models.pwa.teacher_work import calculate_snapshot, fingerprint


def timestamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def calculate_course_work(connection, course_id, *, run_id=None):
    if run_id is None:
        with connection:
            run_id = records.create_run(
                connection, course_id, None, "timer:" + str(uuid.uuid4()), timestamp()
            )
    with connection:
        connection.execute(
            "UPDATE teacher_work_runs SET state='running' WHERE id=?", (run_id,)
        )
    try:
        for _ in range(3):
            # Hold a consistent read snapshot only while collecting facts, never during CPU.
            connection.execute("BEGIN")
            try:
                facts = records.source_facts(connection, course_id)
            finally:
                connection.execute("ROLLBACK")
            digest = fingerprint(facts)
            snapshot = calculate_snapshot(facts)
            connection.execute("BEGIN IMMEDIATE")
            try:
                if fingerprint(records.source_facts(connection, course_id)) != digest:
                    connection.execute("ROLLBACK")
                    continue
                records.publish(connection, run_id, digest, snapshot, timestamp())
                connection.execute("COMMIT")
                return run_id
            except BaseException:
                connection.execute("ROLLBACK")
                raise
        raise RuntimeError("source_changed")
    except Exception:
        with connection:
            records.fail_run(connection, run_id, timestamp(), "calculation_failed")
        raise


def operation_payload(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "state": row["state"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
        "errorCode": row["error_code"],
    }


class TeacherWorkRunner:
    def __init__(self, database_path):
        self.database_path = str(database_path)
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="teacher-work"
        )
        self.stopping = threading.Event()
        self.guard = threading.Lock()
        self.pending = set()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def status(self, course_id):
        with self.connection() as connection:
            row = records.latest_run(connection, course_id)
            return {
                "operation": operation_payload(row),
                "busy": bool(row and row["state"] in ("queued", "running")),
            }

    def start(self, course_id, actor, key):
        with self.guard, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = connection.execute(
                    """SELECT r.* FROM teacher_work_run_requests q
                  JOIN teacher_work_runs r ON r.id=q.run_id WHERE q.actor_id=? AND q.request_key=?""",
                    (actor, key),
                ).fetchone()
                if replay:
                    if replay["course_id"] != course_id:
                        raise ValueError("idempotency_conflict")
                    connection.rollback()
                    return {
                        "operation": operation_payload(replay),
                        "busy": replay["state"] in ("queued", "running"),
                    }
                queued = connection.execute(
                    "SELECT * FROM teacher_work_runs WHERE course_id=? AND state='queued' ORDER BY id DESC LIMIT 1",
                    (course_id,),
                ).fetchone()
                run_id = (
                    queued["id"]
                    if queued
                    else records.create_run(
                        connection, course_id, actor, f"{actor}:{key}", timestamp()
                    )
                )
                connection.execute(
                    "INSERT INTO teacher_work_run_requests VALUES(?,?,?,?,?)",
                    (actor, key, course_id, run_id, timestamp()),
                )
                row = connection.execute(
                    "SELECT * FROM teacher_work_runs WHERE id=?", (run_id,)
                ).fetchone()
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            if not queued:
                self.pending.add(course_id)
                try:
                    self.executor.submit(self.work, course_id, run_id)
                except BaseException:
                    with connection:
                        records.fail_run(
                            connection, run_id, timestamp(), "start_failed"
                        )
                    raise
            return {"operation": operation_payload(row), "busy": True}

    def work(self, course_id, run_id):
        try:
            with open(self.database_path + ".analytics.lock", "a") as lock:
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if self.stopping.wait(0.2):
                            raise RuntimeError("shutdown")
                with self.connection() as connection:
                    state = connection.execute(
                        "SELECT state FROM teacher_work_runs WHERE id=?", (run_id,)
                    ).fetchone()
                    if state["state"] in ("completed", "failed"):
                        return
                    # With the shared lock acquired, other running records are interrupted.
                    with connection:
                        connection.execute(
                            "UPDATE teacher_work_runs SET state='failed',completed_at=?,error_code='interrupted' WHERE state='running' AND id!=?",
                            (timestamp(), run_id),
                        )
                    calculate_course_work(connection, course_id, run_id=run_id)
        except Exception:
            logging.getLogger(__name__).exception(
                "Teacher work calculation failed run=%s", run_id
            )
            with self.connection() as connection, connection:
                records.fail_run(connection, run_id, timestamp(), "calculation_failed")
        finally:
            with self.guard:
                with self.connection() as connection:
                    remaining = connection.execute(
                        "SELECT 1 FROM teacher_work_runs WHERE course_id=? AND state='queued'",
                        (course_id,),
                    ).fetchone()
                if not remaining:
                    self.pending.discard(course_id)

    def recover(self):
        with self.guard, self.connection() as connection:
            queued = records.rows(
                connection,
                "SELECT id,course_id FROM teacher_work_runs WHERE state IN ('queued','running') ORDER BY id",
            )
            for row in queued:
                self.pending.add(row["course_id"])
                self.executor.submit(self.work, row["course_id"], row["id"])

    def close(self):
        self.stopping.set()
        self.executor.shutdown(wait=True)

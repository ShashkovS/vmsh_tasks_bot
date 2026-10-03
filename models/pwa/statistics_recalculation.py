"""Managed threaded calculation with the CLI lock; docs/lesson-statistics.md."""

import fcntl
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from db_methods.pwa import statistics_recalculations as records
from models.pwa.course_analytics_runner import calculate_course, timestamp


class RecalculationConflict(ValueError):
    pass


class StatisticsRecalculation:
    def __init__(self, database_path):
        self.database_path = str(database_path)
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="course-analytics"
        )

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def lock(self):
        lock = open(self.database_path + ".analytics.lock", "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return None
        return lock

    def status(self, course_id):
        lock = self.lock()
        try:
            with self.connection() as connection:
                if lock is not None:
                    records.recover_interrupted(connection, timestamp())
                return {
                    "operation": records.payload(
                        records.latest_operation(connection, course_id)
                    ),
                    "busy": lock is None,
                }
        finally:
            if lock is not None:
                lock.close()

    def start(self, course_id, actor, key):
        # Replay before contention, then recheck under the global lock.
        with self.connection() as connection:
            existing = records.find_operation(connection, actor, key)
            if existing is not None:
                if existing["course_id"] != course_id:
                    raise RecalculationConflict(
                        "idempotency key belongs to another course"
                    )
                status = self.status(course_id)
                existing = records.find_operation(connection, actor, key)
                return {**status, "operation": records.payload(existing)}
        lock = self.lock()
        if lock is None:
            with self.connection() as connection:
                return {
                    "operation": records.payload(
                        records.latest_operation(connection, course_id)
                    ),
                    "busy": True,
                }
        try:
            with self.connection() as connection:
                records.recover_interrupted(connection, timestamp())
                existing = records.find_operation(connection, actor, key)
                if existing is not None:
                    if existing["course_id"] != course_id:
                        raise RecalculationConflict(
                            "idempotency key belongs to another course"
                        )
                    return {"operation": records.payload(existing), "busy": False}
                operation_id = records.create_operation(
                    connection, course_id, actor, key, timestamp()
                )
                response = {
                    "operation": records.payload(
                        records.latest_operation(connection, course_id)
                    ),
                    "busy": True,
                }
            try:
                self.executor.submit(self.work, lock, course_id, operation_id)
            except BaseException:
                with self.connection() as connection:
                    records.fail_operation(
                        connection, operation_id, timestamp(), "start_failed"
                    )
                raise
            lock = None  # Ownership passes to the worker, including while queued.
            return response
        finally:
            if lock is not None:
                lock.close()

    def work(self, lock, course_id, operation_id):
        try:
            with self.connection() as connection:
                calculate_course(connection, course_id, operation_id=operation_id)
        except Exception:
            logging.getLogger(__name__).exception(
                "Manual analytics failed operation=%s course=%s",
                operation_id,
                course_id,
            )
            with self.connection() as connection:
                records.fail_operation(
                    connection, operation_id, timestamp(), "calculation_failed"
                )
        finally:
            lock.close()

    def close(self):
        self.executor.shutdown(wait=True)

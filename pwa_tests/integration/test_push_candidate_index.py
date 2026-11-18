"""Migration 0116: unchanged delivery rows, bounded scans of future/history events."""

import sqlite3
from contextlib import closing

import yoyo

from db_methods.pwa import apply_schema_migrations
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.notification_deliveries import list_due_candidates
from pwa_tests.integration.test_phase8_push_delivery import _prepare_database

MIGRATION_ID = "0116.notification_push_candidate_index"


def _read_candidates(connection):
    statements = []
    steps = 0

    def progress():
        nonlocal steps
        steps += 100
        return 0

    connection.set_trace_callback(statements.append)
    connection.set_progress_handler(progress, 100)
    try:
        rows = list_due_candidates(
            connection, now="2026-10-05T20:00:00Z",
            now_milliseconds=1791223200000, limit=200,
        )
    finally:
        connection.set_trace_callback(None)
        connection.set_progress_handler(None, 0)
    plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + statements[0])]
    return rows, steps, plan


def test_push_index_migration_preserves_candidates_and_skips_future_history(tmp_path):
    path, _factory = _prepare_database(tmp_path)
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.executemany(
            "INSERT INTO notification_events "
            "(account_id,category,dedupe_key,route,payload_json,occurred_at,"
            "deliver_after,read_at,created_at) VALUES "
            "(1,'review_completed',?,'/student/','{}',?,?,?,?)",
            [
                (f"history-{index}", "2026-09-20T00:00:00Z",
                 "2026-09-20T00:00:00Z" if index % 2 else "2027-09-20T00:00:00Z",
                 "2026-09-21T00:00:00Z" if index % 2 else None,
                 "2026-09-20T00:00:00Z")
                for index in range(5000)
            ],
        )
        connection.commit()
        before = [tuple(row) for row in connection.execute("SELECT * FROM notification_events")]

    with yoyo.get_backend(f"sqlite:///{path.resolve()}") as backend:
        migration = yoyo.read_migrations(str(MIGRATIONS_ROOT)).filter(
            lambda item: item.id == MIGRATION_ID
        )
        backend.rollback_migrations(migration)
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        baseline, baseline_steps, _ = _read_candidates(connection)
    assert apply_schema_migrations(path).is_current
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        indexed, indexed_steps, plan = _read_candidates(connection)
        assert [tuple(row) for row in connection.execute("SELECT * FROM notification_events")] == before
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert indexed == baseline
    assert len(indexed) == 1
    assert any("notification_events_push_due_idx" in item for item in plan)
    # VM steps, rather than host-dependent milliseconds, guard actual query work.
    assert indexed_steps < baseline_steps / 4

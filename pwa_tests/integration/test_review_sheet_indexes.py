"""Measured sheet indexes are lossless/reversible; followups-20261018.md."""

import sqlite3

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.review_sheet import CASE_THREADS_SQL, LATEST_REVIEW_SQL
from pwa_tests.integration import test_review_queue_repository as fixtures

review_queue_fixture = fixtures.review_queue_fixture


def test_index_up_down_up_preserves_records_and_lookup_results(review_queue_fixture):
    f = review_queue_fixture
    path = f.factory.database_path
    def records(c):
        return [tuple(r) for r in c.execute("SELECT * FROM submission_threads ORDER BY id")]
    before = f.factory.run_read(records)
    sql = LATEST_REVIEW_SQL.format(placeholders="?")
    def reads(c):
        return (c.execute(CASE_THREADS_SQL, ("st-1",)).fetchall(),
                c.execute(sql, (1,)).fetchall())
    expected = f.factory.run_read(reads)
    migration = next(m for m in yoyo.read_migrations(str(MIGRATIONS_ROOT)) if m.id == "0121.review_sheet_indexes")
    backend = yoyo.get_backend(f"sqlite:///{path}")
    names = ("submission_threads_public_id_idx", "submission_review_evidence_entries_thread_review_idx")
    with backend.lock():
        backend.rollback_migrations([migration])
        with sqlite3.connect(path) as c:
            assert not c.execute("SELECT name FROM sqlite_schema WHERE name IN (?,?)", names).fetchall()
        assert f.factory.run_read(records) == before
        assert f.factory.run_read(reads) == expected
        backend.apply_migrations(backend.to_apply(yoyo.read_migrations(str(MIGRATIONS_ROOT))))
    assert f.factory.run_read(records) == before
    assert f.factory.run_read(reads) == expected
    def plans(c):
        for query, values, index in ((CASE_THREADS_SQL, ("st-1",), names[0]), (sql, (1,), names[1])):
            plan = [r["detail"] for r in c.execute("EXPLAIN QUERY PLAN " + query, values)]
            assert any(index in detail for detail in plan)
    f.factory.run_read(plans)

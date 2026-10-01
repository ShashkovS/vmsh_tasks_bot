"""Receipt lookup uses an index without changing recheck data or results."""

import sqlite3

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.submissions import _stored_attempts
from pwa_tests.integration.test_submission_repository import (
    PROBLEM_PUBLIC_ID,
    build_submission_fixture,
    command,
)


MIGRATION_ID = "0105.pwa_recheck_receipt_lookup"
INDEX_NAME = "idempotency_records_completed_receipt_lookup_idx"


def _migrate(database_path, *, rollback):
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT))
    selected = migrations.filter(lambda item: item.id == MIGRATION_ID)
    assert {item.id for item in selected[0].depends} == {
        "0103.course_in_person_classes"
    }
    with yoyo.get_backend(f"sqlite:///{database_path.resolve()}") as backend:
        with backend.lock():
            if rollback:
                backend.rollback_migrations(backend.to_rollback(selected))
            else:
                backend.apply_migrations(backend.to_apply(selected))


def _inspect(fixture):
    def read(connection):
        statements = []
        connection.set_trace_callback(statements.append)
        try:
            attempts = _stored_attempts(connection, problem_id=fixture.problem_id)
        finally:
            connection.set_trace_callback(None)
        query = next(query for query in statements if "AS response_json" in query)
        plan = [
            row["detail"] for row in connection.execute("EXPLAIN QUERY PLAN " + query)
        ]
        rows = {
            table: [
                tuple(row.values())
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")
            ]
            for table in ("idempotency_records", "test_attempts", "results")
        }
        assert (
            connection.execute("PRAGMA integrity_check").fetchone()["integrity_check"]
            == "ok"
        )
        return attempts, plan, rows

    return fixture.factory.run_read(read)


async def test_recheck_receipt_index_up_down_up_preserves_results_and_removes_scan(
    tmp_path,
):
    fixture = build_submission_fixture(tmp_path)
    receipt = await fixture.repository.submit_test_answer(command(fixture))
    preview = await fixture.repository.get_test_attempt_recheck_preview(
        problem_public_id=PROBLEM_PUBLIC_ID
    )
    indexed_attempts, indexed_plan, rows = _inspect(fixture)
    assert len(indexed_attempts) == 1
    assert indexed_attempts[0].display_answer == receipt.display_answer
    assert any(f"USING INDEX {INDEX_NAME}" in step for step in indexed_plan)
    assert not any("SCAN idempotency" in step for step in indexed_plan)

    _migrate(fixture.factory.database_path, rollback=True)
    with sqlite3.connect(fixture.factory.database_path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name = ?", (INDEX_NAME,)
            ).fetchone()
            is None
        )
    old_attempts, old_plan, old_rows = _inspect(fixture)
    assert any("SCAN idempotency" in step for step in old_plan)
    assert old_attempts == indexed_attempts
    assert old_rows == rows

    _migrate(fixture.factory.database_path, rollback=False)
    restored_attempts, restored_plan, restored_rows = _inspect(fixture)
    assert any(f"USING INDEX {INDEX_NAME}" in step for step in restored_plan)
    assert restored_attempts == indexed_attempts
    assert restored_rows == rows
    assert (
        await fixture.repository.get_test_attempt_recheck_preview(
            problem_public_id=PROBLEM_PUBLIC_ID
        )
        == preview
    )

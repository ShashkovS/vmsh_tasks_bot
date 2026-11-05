"""Scoped callback parity and index lifecycle; scoped-reads-20261013.md."""

import json
import sqlite3

import pytest
import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT

from db_methods.pwa.live_marking import LIVE_CELLS_SQL, cells
from db_methods.pwa.performance_guard import check_database_performance
from pwa_tests.integration import test_written_result_precedence as support
from pwa_tests.sqlite_template import create_test_database

projection_template = support.projection_template
projection_db = support.projection_db


@pytest.mark.parametrize("after", [None, 0, 100000])
def test_scoped_board_matches_global_projection_with_aliases_and_other_students(projection_db, after):
    connection = projection_db
    for student in (support.STUDENT, 1004):
        support._add(connection, 17, 2, student=student)
        support._add(connection, 12, 1, problem=support.SECOND, student=student)
    # Reference is the global view, retaining the old ranking and delta filter.
    prefix = LIVE_CELLS_SQL[:LIVE_CELLS_SQL.index("scoped_logical_keys")]
    tail = LIVE_CELLS_SQL[LIVE_CELLS_SQL.index("scope AS ("):]
    reference = prefix + tail.replace("scoped_problem_members", "result_problem_groups").replace("scoped_effective_results", "effective_results")
    params = {"student_ids": json.dumps([support.STUDENT, 1004]),
              "problem_ids": json.dumps([support.FIRST, support.SECOND]), "after": after}
    expected = [dict(row) for row in connection.execute(reference, params)]
    actual = cells(connection, [support.STUDENT, 1004], [support.FIRST, support.SECOND], after)
    assert actual == expected
    plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + LIVE_CELLS_SQL, params)]
    assert not any("MATERIALIZE effective_results" in item for item in plan)
    assert any("scoped_teacher_choices" in item for item in plan)


def test_new_indexes_are_lossless_and_actual_callback_guard_runs(tmp_path):
    path = tmp_path / "scoped.sqlite3"
    create_test_database(path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        support._seed(connection)
        support._add(connection, 17, 2)
        connection.commit()
        results_before = [tuple(row) for row in connection.execute("SELECT * FROM results")]
    migration = next(item for item in yoyo.read_migrations(str(MIGRATIONS_ROOT)) if item.id == "0120.scoped_read_indexes")
    backend = yoyo.get_backend(f"sqlite:///{path}")
    with backend.lock():
        backend.rollback_migrations([migration])
        with sqlite3.connect(path) as connection:
            assert not connection.execute("SELECT 1 FROM sqlite_schema WHERE name IN ('results_by_problem_student','live_mark_operations_active_context')").fetchall()
            assert list(connection.execute("SELECT * FROM results")) == results_before
        backend.apply_migrations(backend.to_apply(yoyo.read_migrations(str(MIGRATIONS_ROOT))))
    with sqlite3.connect(path) as connection:
        assert len(connection.execute("SELECT 1 FROM sqlite_schema WHERE name IN ('results_by_problem_student','live_mark_operations_active_context')").fetchall()) == 2
        assert list(connection.execute("SELECT * FROM results")) == results_before
    proof = check_database_performance(path)
    names = {probe["name"] for probe in proof["probes"]}
    assert {"live-cell-scoped", "live-board-scoped", "live-visits-scoped", "statistics-results-scoped", "statistics-attempts-scoped", "statistics-pending-scoped", "statistics-reviews-scoped"} <= names

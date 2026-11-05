"""Current-schema contract for the test-attempt result lookup."""

import sqlite3

from db_methods.pwa.performance_guard import check_database_performance
from pwa_tests.sqlite_template import create_test_database


def test_current_attempt_result_lookup_is_indexed(tmp_path):
    database_path = tmp_path / "test-attempt-result-lookup.sqlite3"
    create_test_database(database_path)
    with sqlite3.connect(database_path) as connection:
        plan = [
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT count(*) FROM effective_results"
            )
        ]
        assert any("test_attempts_result_idx" in row for row in plan)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    report = check_database_performance(database_path)
    assert report["viewsChecked"] == 7
    assert report["probes"][0]["name"] == "effective-results-current-test-attempt"

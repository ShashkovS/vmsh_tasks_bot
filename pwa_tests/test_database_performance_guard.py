from __future__ import annotations

import sqlite3

import pytest

from db_methods.pwa.performance_guard import (
    CriticalQueryProbe,
    DatabasePerformanceGuardError,
    check_database_performance,
)


def test_guard_rejects_a_correlated_full_scan_and_accepts_indexed_lookup(tmp_path):
    database_path = tmp_path / "plans.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE parents (id INTEGER PRIMARY KEY);
            CREATE TABLE children (parent_id INTEGER NOT NULL);
            CREATE VIEW parent_matches AS
            SELECT parents.id
            FROM parents
            WHERE EXISTS (
                SELECT 1 FROM children WHERE children.parent_id = parents.id
            );
            """
        )

    with pytest.raises(
        DatabasePerformanceGuardError,
        match="parent_matches.*correlated full scan",
    ):
        check_database_performance(database_path, probes=())

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE INDEX children_parent_idx ON children (parent_id)"
        )

    report = check_database_performance(database_path, probes=())
    assert report == {
        "schemaVersion": 1,
        "database": "plans.sqlite3",
        "viewsChecked": 1,
        "probes": [],
    }


def test_guard_interrupts_a_critical_query_over_its_budget(tmp_path):
    database_path = tmp_path / "deadline.sqlite3"
    sqlite3.connect(database_path).close()
    probe = CriticalQueryProbe(
        name="deliberately-slow",
        sql="""
            WITH RECURSIVE counter(value) AS (
                VALUES(0)
                UNION ALL
                SELECT value + 1 FROM counter WHERE value < 100000000
            )
            SELECT sum(value) FROM counter
        """,
        time_budget_seconds=0.001,
    )

    with pytest.raises(
        DatabasePerformanceGuardError,
        match="deliberately-slow.*exceeded",
    ):
        check_database_performance(database_path, probes=(probe,))


def test_guard_requires_declared_query_plan_fragments(tmp_path):
    database_path = tmp_path / "required-index.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE records (lookup_key INTEGER NOT NULL)")
    probe = CriticalQueryProbe(
        name="record-lookup",
        sql="SELECT count(*) FROM records WHERE lookup_key = 1",
        required_plan_fragments=("records_lookup_idx",),
    )

    with pytest.raises(
        DatabasePerformanceGuardError,
        match="record-lookup.*records_lookup_idx",
    ):
        check_database_performance(database_path, probes=(probe,))

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE INDEX records_lookup_idx ON records (lookup_key)"
        )

    report = check_database_performance(database_path, probes=(probe,))
    assert report["probes"][0]["name"] == "record-lookup"

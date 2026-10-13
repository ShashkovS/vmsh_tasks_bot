"""Fail-closed query-plan and latency checks for a migrated SQLite database."""

from __future__ import annotations

import sqlite3
import time
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class DatabasePerformanceGuardError(RuntimeError):
    """A migrated database violates a production query performance contract."""


@dataclass(frozen=True, slots=True)
class CriticalQueryProbe:
    """One bounded read that represents a production fan-out dependency."""

    name: str
    sql: str
    required_plan_fragments: tuple[str, ...] = ()
    time_budget_seconds: float = 2.0
    parameters: Mapping[str, object] | None = None


# Keep this deliberately small and based on read-model fan-out, not individual
# HTTP routes.  One projection probe protects Student/Family/Staff consumers of
# effective_results, including the Staff statistics incident from 17 Sep 2026.
# Add a probe when a migration introduces another shared aggregate/projection.
CRITICAL_QUERY_PROBES: Final[tuple[CriticalQueryProbe, ...]] = (
    CriticalQueryProbe(
        name="effective-results-current-test-attempt",
        sql="SELECT count(*) FROM effective_results",
        required_plan_fragments=("test_attempts_result_idx",),
    ),
)


def scoped_query_probes(connection):
    """Real bound callbacks rather than only views; scoped-reads-20261013.md."""
    from db_methods.pwa.live_marking import LIVE_CELLS_SQL, LIVE_VISITS_SQL

    pair = connection.execute(
        """SELECT r.student_id,r.problem_id,p.group_id,p.lesson FROM results r
        JOIN problems p ON p.id=r.problem_id JOIN users u ON u.id=r.student_id
        WHERE u.type IN (1,-2) AND p.prob>0 ORDER BY r.id DESC LIMIT 1"""
    ).fetchone()
    student_ids, problem_ids = [], []
    if pair is not None:
        student_ids, problem_ids = [pair[0]], [pair[1]]
    exact = {"student_ids": json.dumps(student_ids), "problem_ids": json.dumps(problem_ids), "after": None}
    if pair is not None:
        student_ids = [row[0] for row in connection.execute(
            "SELECT student_user_id FROM course_enrollments WHERE active_group_id=? AND status='active' ORDER BY student_user_id LIMIT 60",
            (pair[2],),
        )] or student_ids
        problem_ids = [row[0] for row in connection.execute(
            "SELECT id FROM problems WHERE group_id=? AND lesson=? AND prob>0 ORDER BY id LIMIT 20",
            (pair[2], pair[3]),
        )] or problem_ids
    board = {"student_ids": json.dumps(student_ids), "problem_ids": json.dumps(problem_ids), "after": None}
    session = connection.execute(
        "SELECT session_id FROM live_mark_visits ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    from db_methods.pwa.lesson_statistics import PUBLISHED_PROBLEMS_SQL, CURRENT_RESULTS_SQL, CURRENT_ATTEMPTS_SQL, PENDING_SQL
    from db_methods.pwa.statistics_reports import REVIEWS_SQL
    course = connection.execute("SELECT course_id FROM group_lessons ORDER BY id DESC LIMIT 1").fetchone()
    publication = {"course_id": course[0] if course else -1, "group_ids": None, "lesson_number": None}
    published_ids = [row[0] for row in connection.execute(PUBLISHED_PROBLEMS_SQL, publication)]
    facts = {"problem_ids": json.dumps(published_ids), "exclude_reviewed": 1}
    return (
        CriticalQueryProbe("statistics-results-scoped", CURRENT_RESULTS_SQL, parameters=facts),
        CriticalQueryProbe("statistics-attempts-scoped", CURRENT_ATTEMPTS_SQL, parameters=facts),
        CriticalQueryProbe("statistics-pending-scoped", PENDING_SQL, parameters=facts),
        CriticalQueryProbe("statistics-reviews-scoped", REVIEWS_SQL, parameters=facts),
        CriticalQueryProbe("live-cell-scoped", LIVE_CELLS_SQL, parameters=exact),
        CriticalQueryProbe("live-board-scoped", LIVE_CELLS_SQL, parameters=board),
        CriticalQueryProbe("live-visits-scoped", LIVE_VISITS_SQL,
                           required_plan_fragments=("live_mark_operations_active_context",),
                           parameters={"session_id": session[0] if session else "performance-empty"}),
    )


def _quoted_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _query_plan(
    connection: sqlite3.Connection,
    sql: str,
    parameters=None,
) -> list[tuple[int, int, int, str]]:
    return [
        (int(row[0]), int(row[1]), int(row[2]), str(row[3]))
        for row in connection.execute("EXPLAIN QUERY PLAN " + sql, parameters or {})
    ]


def _correlated_full_scans(
    plan: list[tuple[int, int, int, str]],
) -> list[str]:
    """Return scans nested below correlated subqueries.

    A correlated full scan is the exact unbounded N×M plan that exhausted the
    two-connection read pools in production.  SQLite's plan tree exposes it
    independently of table size, so an empty migration fixture still catches
    the regression.
    """

    nodes = {node_id: (parent_id, detail) for node_id, parent_id, _, detail in plan}
    violations: list[str] = []
    for node_id, parent_id, _, detail in plan:
        del node_id
        if not detail.startswith("SCAN ") or detail.startswith("SCAN CONSTANT ROW"):
            continue
        ancestors: list[str] = []
        seen: set[int] = set()
        current = parent_id
        while current in nodes and current not in seen:
            seen.add(current)
            next_parent, ancestor_detail = nodes[current]
            ancestors.append(ancestor_detail)
            current = next_parent
        if any("CORRELATED" in ancestor for ancestor in ancestors):
            violations.append(f"{detail} below {' > '.join(ancestors)}")
    return violations


def _run_bounded_probe(
    connection: sqlite3.Connection,
    probe: CriticalQueryProbe,
) -> float:
    deadline = time.monotonic() + probe.time_budget_seconds
    interrupted = False

    def interrupt_after_deadline() -> int:
        nonlocal interrupted
        if time.monotonic() < deadline:
            return 0
        interrupted = True
        return 1

    connection.set_progress_handler(interrupt_after_deadline, 1_000)
    started = time.monotonic()
    try:
        connection.execute(probe.sql, probe.parameters or {}).fetchall()
    except sqlite3.OperationalError as error:
        if interrupted:
            raise DatabasePerformanceGuardError(
                f"critical query {probe.name!r} exceeded "
                f"{probe.time_budget_seconds:.3f}s"
            ) from error
        raise DatabasePerformanceGuardError(
            f"critical query {probe.name!r} failed: {error}"
        ) from error
    finally:
        connection.set_progress_handler(None, 0)
    elapsed = time.monotonic() - started
    if elapsed > probe.time_budget_seconds:
        raise DatabasePerformanceGuardError(
            f"critical query {probe.name!r} took {elapsed:.3f}s; "
            f"budget is {probe.time_budget_seconds:.3f}s"
        )
    return elapsed


def check_database_performance(
    database_path: str | Path,
    *,
    probes: tuple[CriticalQueryProbe, ...] = CRITICAL_QUERY_PROBES,
) -> dict[str, object]:
    """Inspect every view and run bounded critical reads on one SQLite file."""

    resolved_path = Path(database_path).resolve(strict=True)
    uri = resolved_path.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=0.1) as connection:
        connection.execute("PRAGMA query_only = ON")
        if probes is CRITICAL_QUERY_PROBES:
            probes = (*probes, *scoped_query_probes(connection))
        view_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE type = 'view' ORDER BY name"
            )
        ]
        for view_name in view_names:
            sql = f"SELECT count(*) FROM {_quoted_identifier(view_name)}"
            violations = _correlated_full_scans(_query_plan(connection, sql))
            if violations:
                raise DatabasePerformanceGuardError(
                    f"view {view_name!r} contains correlated full scan: "
                    + "; ".join(violations)
                )

        probe_reports: list[dict[str, object]] = []
        for probe in probes:
            plan = _query_plan(connection, probe.sql, probe.parameters)
            details = [row[3] for row in plan]
            violations = _correlated_full_scans(plan)
            if violations:
                raise DatabasePerformanceGuardError(
                    f"critical query {probe.name!r} contains correlated full scan: "
                    + "; ".join(violations)
                )
            missing = [
                fragment
                for fragment in probe.required_plan_fragments
                if not any(fragment in detail for detail in details)
            ]
            if missing:
                raise DatabasePerformanceGuardError(
                    f"critical query {probe.name!r} misses plan requirements: "
                    + ", ".join(missing)
                )
            elapsed = _run_bounded_probe(connection, probe)
            probe_reports.append(
                {
                    "name": probe.name,
                    "elapsedMs": round(elapsed * 1_000, 3),
                    "plan": details,
                }
            )

    return {
        "schemaVersion": 1,
        "database": resolved_path.name,
        "viewsChecked": len(view_names),
        "probes": probe_reports,
    }

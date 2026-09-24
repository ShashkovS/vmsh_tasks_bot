"""Fail-closed query-plan and latency checks for a migrated SQLite database."""

from __future__ import annotations

import sqlite3
import time
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


def _quoted_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _query_plan(
    connection: sqlite3.Connection,
    sql: str,
) -> list[tuple[int, int, int, str]]:
    return [
        (int(row[0]), int(row[1]), int(row[2]), str(row[3]))
        for row in connection.execute("EXPLAIN QUERY PLAN " + sql)
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
        connection.execute(probe.sql).fetchone()
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
            plan = _query_plan(connection, probe.sql)
            details = [row[3] for row in plan]
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

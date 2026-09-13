"""Accepted test results supersede only older live manual marks.

Owner decision: vmshpwa/docs/live-marking.md,
"Принятый контракт".
"""

from __future__ import annotations

import sqlite3

from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0091.pwa_test_result_live_mark_precedence"


def _insert_problem(connection: sqlite3.Connection, problem_id: int) -> None:
    connection.execute(
        "INSERT INTO problems "
        "(id,group_id,lesson,prob,item,title,prob_text,prob_type,synonyms) "
        "VALUES (?,'н',1,?,'','Тестовая задача','',1,'')",
        (problem_id, problem_id),
    )


def _insert_result(
    connection: sqlite3.Connection,
    *,
    student_id: int,
    problem_id: int,
    verdict: int,
    result_type: int,
) -> int:
    result_id = int(
        connection.execute(
            "INSERT INTO results "
            "(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) "
            "VALUES (?,?,'н',1,2,'2026-09-13T12:00:00Z',?,?) RETURNING id",
            (student_id, problem_id, verdict, result_type),
        ).fetchone()[0]
    )
    if result_type in (3, 4):
        connection.execute(
            "INSERT INTO live_mark_results(result_id) VALUES (?)", (result_id,)
        )
    return result_id


def _pinned_result(connection: sqlite3.Connection, problem_id: int) -> int | None:
    row = connection.execute(
        "SELECT result_id FROM live_mark_cells WHERE student_id=1 AND problem_id=?",
        (problem_id,),
    ).fetchone()
    assert row is not None
    return row[0]


def _effective_verdicts(connection: sqlite3.Connection, problem_id: int) -> list[int]:
    return [
        int(row[0])
        for row in connection.execute(
            "SELECT verdict FROM effective_results "
            "WHERE student_id=1 AND problem_id=? ORDER BY id",
            (problem_id,),
        )
    ]


def test_migration_repairs_stale_pins_and_enforces_chronological_precedence(
    tmp_path,
) -> None:
    database_path = tmp_path / "test-result-precedence.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0090.pwa_support_photos"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users(id,type,name,surname) VALUES "
            "(1,1,'Ученик','Тестовый'),(2,10,'Учитель','Тестовый')"
        )
        for problem_id in range(1, 10):
            _insert_problem(connection, problem_id)

        stale_manual = _insert_result(
            connection, student_id=1, problem_id=1, verdict=-1, result_type=4
        )
        _insert_result(
            connection, student_id=1, problem_id=1, verdict=18, result_type=1
        )
        assert _pinned_result(connection, 1) == stale_manual

        retained_after_wrong = _insert_result(
            connection, student_id=1, problem_id=2, verdict=17, result_type=4
        )
        _insert_result(
            connection, student_id=1, problem_id=2, verdict=-1, result_type=1
        )

        _insert_result(
            connection, student_id=1, problem_id=3, verdict=18, result_type=1
        )
        later_manual = _insert_result(
            connection, student_id=1, problem_id=3, verdict=-1, result_type=4
        )

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _pinned_result(connection, 1) is None
        assert _effective_verdicts(connection, 1) == [18]
        assert _pinned_result(connection, 2) == retained_after_wrong
        assert _effective_verdicts(connection, 2) == [17]
        assert _pinned_result(connection, 3) == later_manual
        assert _effective_verdicts(connection, 3) == [-1]

        _insert_result(
            connection, student_id=1, problem_id=4, verdict=-1, result_type=4
        )
        _insert_result(
            connection, student_id=1, problem_id=4, verdict=18, result_type=1
        )
        assert _pinned_result(connection, 4) is None
        assert _effective_verdicts(connection, 4) == [18]

        later_plus = _insert_result(
            connection, student_id=1, problem_id=5, verdict=17, result_type=4
        )
        _insert_result(
            connection, student_id=1, problem_id=5, verdict=-1, result_type=1
        )
        assert _pinned_result(connection, 5) == later_plus

        _insert_result(
            connection, student_id=1, problem_id=6, verdict=18, result_type=1
        )
        newest_manual = _insert_result(
            connection, student_id=1, problem_id=6, verdict=-1, result_type=4
        )
        assert _pinned_result(connection, 6) == newest_manual

        _insert_result(
            connection, student_id=1, problem_id=7, verdict=-1, result_type=4
        )
        rechecked_test = _insert_result(
            connection, student_id=1, problem_id=7, verdict=-1, result_type=1
        )
        connection.execute(
            "UPDATE results SET verdict=18 WHERE id=?", (rechecked_test,)
        )
        assert _pinned_result(connection, 7) is None

        older_test = _insert_result(
            connection, student_id=1, problem_id=8, verdict=-1, result_type=1
        )
        newest_plus = _insert_result(
            connection, student_id=1, problem_id=8, verdict=17, result_type=4
        )
        connection.execute("UPDATE results SET verdict=18 WHERE id=?", (older_test,))
        assert _pinned_result(connection, 8) == newest_plus

        newest_manual = int(
            connection.execute(
                "INSERT INTO results "
                "(id,student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) "
                "VALUES (10000,1,9,'н',1,2,'2026-09-13T12:01:00Z',17,4) "
                "RETURNING id"
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO live_mark_results(result_id) VALUES (?)", (newest_manual,)
        )
        connection.execute(
            "INSERT INTO results "
            "(id,student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) "
            "VALUES (9999,1,9,'н',1,2,'2026-09-13T12:00:00Z',18,1)"
        )
        assert _pinned_result(connection, 9) == newest_manual

    _rollback(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        manual_under_rollback = _insert_result(
            connection, student_id=1, problem_id=1, verdict=-1, result_type=4
        )
        _insert_result(
            connection, student_id=1, problem_id=1, verdict=18, result_type=1
        )
        assert _pinned_result(connection, 1) == manual_under_rollback

    _apply(database_path, {MIGRATION_ID})
    with sqlite3.connect(database_path) as connection:
        assert _pinned_result(connection, 1) is None
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

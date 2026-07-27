"""Characterize persisted verdict weights, solved thresholds and reactions."""

from __future__ import annotations

from datetime import datetime

from helpers.consts import (
    REACTION,
    VERDICT,
    VERDICT_DECODER,
    VERDICT_TO_NUM,
    VERDICT_TO_TICK,
    VERDICTS_SOLVED,
)


EXPECTED_VERDICT_WEIGHTS = {
    VERDICT.NO_ANSWER: 0.0,
    VERDICT.REJECTED_ANSWER: 0.0,
    VERDICT.WRONG_ANSWER: 0.0,
    VERDICT.VERDICT_MINUS: 0.0,
    VERDICT.VERDICT_MINUS_DOT: 0.05,
    VERDICT.VERDICT_MINUS_PLUS: 0.25,
    VERDICT.VERDICT_PLUS_DIV_2: 0.5,
    VERDICT.VERDICT_PLUS_MINUS: 0.7,
    VERDICT.VERDICT_PLUS_DOT: 0.95,
    VERDICT.VERDICT_PLUS: 1.0,
    VERDICT.OLD_SOLVED: 1.0,
    VERDICT.SOLVED: 1.0,
}

EXPECTED_REACTIONS = {
    REACTION.WRITTEN_STUDENT: (0, 1, 2),
    REACTION.WRITTEN_TEACHER: (100, 101, 102, 103),
    REACTION.ORAL_STUDENT: (200, 201, 202, 203, 204),
    REACTION.ORAL_TEACHER: (300, 301, 302, 303),
}


def _add_problem(legacy_db, problem_id: int, group_id: str, title: str) -> None:
    with legacy_db.sql.conn as connection:
        connection.execute(
            """
            INSERT INTO problems (
                id, group_id, lesson, prob, item, title, prob_text, prob_type,
                synonyms
            ) VALUES (?, ?, 12, ?, '', ?, '', 2, ?)
            """,
            (problem_id, group_id, problem_id, title, str(problem_id)),
        )


def test_verdict_ids_labels_ticks_and_weights_are_stable(legacy_domain_db):
    assert VERDICT_TO_NUM == EXPECTED_VERDICT_WEIGHTS
    assert set(VERDICT_DECODER) == set(VERDICT)
    assert set(VERDICT_TO_TICK) == set(VERDICT)
    assert VERDICTS_SOLVED == {
        VERDICT.SOLVED,
        VERDICT.OLD_SOLVED,
        VERDICT.VERDICT_PLUS,
        VERDICT.VERDICT_PLUS_DOT,
    }

    persisted = legacy_domain_db.sql.conn.execute(
        "SELECT id, tick, val FROM verdicts ORDER BY id"
    ).fetchall()
    # OLD_SOLVED=1 is a read-compatibility enum only: migration 0033 rewrote old
    # rows to SOLVED=18 and deliberately omitted id=1 from the lookup table.
    persisted_verdicts = set(VERDICT) - {VERDICT.OLD_SOLVED}
    assert {row["id"]: row["val"] for row in persisted} == {
        int(verdict): EXPECTED_VERDICT_WEIGHTS[verdict]
        for verdict in persisted_verdicts
    }
    assert {row["id"]: row["tick"] for row in persisted} == {
        int(verdict): VERDICT_TO_TICK[verdict] for verdict in persisted_verdicts
    }


def test_solved_queries_use_positive_and_point_eight_thresholds(legacy_domain_db):
    _add_problem(legacy_domain_db, 501, "alpha", "Threshold problem")
    _add_problem(legacy_domain_db, 502, "beta", "Other group problem")
    with legacy_domain_db.sql.conn as connection:
        connection.executemany(
            """
            INSERT INTO results (
                student_id, problem_id, group_id, lesson, teacher_id, ts,
                verdict, answer, res_type
            ) VALUES (1, ?, ?, 12, 10, ?, ?, '', 2)
            """,
            (
                (501, "alpha", "2026-07-27T10:00:00", int(VERDICT.VERDICT_MINUS_PLUS)),
                (501, "alpha", "2026-07-27T11:00:00", int(VERDICT.VERDICT_PLUS_DOT)),
                (502, "beta", "2026-07-27T12:00:00", int(VERDICT.VERDICT_PLUS_MINUS)),
            ),
        )

    assert legacy_domain_db.result.check_student_solved(1, 12, "alpha") == {
        501: int(VERDICT.VERDICT_PLUS_DOT)
    }
    assert legacy_domain_db.result.check_student_solved(1, 12, "beta") == {
        502: int(VERDICT.VERDICT_PLUS_MINUS)
    }
    solved = legacy_domain_db.result.get_student_solved(1, 12)
    assert [(row["title"], row["group_id"]) for row in solved] == [
        ("Threshold problem", "alpha")
    ]


def test_reaction_families_and_result_link_are_stable(legacy_domain_db):
    assert [row["reaction_type_id"] for row in legacy_domain_db.reaction.types()] == [
        int(reaction_type) for reaction_type in REACTION
    ]
    for reaction_type, expected_ids in EXPECTED_REACTIONS.items():
        rows = legacy_domain_db.reaction.enum(reaction_type)
        assert tuple(row["reaction_id"] for row in rows) == expected_ids
        assert all(row["reaction"] for row in rows)

    _add_problem(legacy_domain_db, 601, "alpha", "Reaction problem")
    with legacy_domain_db.sql.conn as connection:
        result_id = connection.execute(
            """
            INSERT INTO results (
                student_id, problem_id, group_id, lesson, teacher_id, ts,
                verdict, answer, res_type
            ) VALUES (1, 601, 'alpha', 12, 10, ?, ?, '', 2)
            RETURNING id
            """,
            (datetime.now().isoformat(), int(VERDICT.SOLVED)),
        ).fetchone()["id"]

    reaction_id = legacy_domain_db.reaction.insert(
        result_id=result_id,
        reaction_type_id=int(REACTION.WRITTEN_TEACHER),
        reaction_id=100,
    )
    stored = legacy_domain_db.sql.conn.execute(
        "SELECT * FROM reactions WHERE id = ?", (reaction_id,)
    ).fetchone()
    assert stored["result_id"] == result_id
    assert stored["zoom_conversation_id"] is None
    assert stored["reaction_type_id"] == int(REACTION.WRITTEN_TEACHER)
    assert stored["reaction_id"] == 100

"""Characterize legacy group/mode audit and Telegram message provenance.

These tests deliberately describe the persisted compatibility surface used by
the migration plan.  They do not make Telegram message ids the identity of a
future PWA submission; see ``vmshpwa/dev/development-plan/02-data-model.md``.
"""

from __future__ import annotations

from datetime import datetime

from helpers.consts import CHANGE, ONLINE_MODE, RES_TYPE, VERDICT
from models import Problem, Result, User, WrittenQueue


def _add_written_problem() -> Problem:
    return Problem(
        group_id="alpha",
        lesson=13,
        prob=1,
        item="",
        title="Synthetic Telegram provenance problem",
        prob_text="",
        prob_type=2,
        ans_type=None,
        ans_validation="",
        validation_error="",
        cor_ans="",
        cor_ans_checker="",
        wrong_ans="",
        congrat="",
    )


def _change_rows(legacy_db) -> list[dict]:
    return legacy_db.sql.conn.execute(
        """
        SELECT rowid, ts, user_id, change_type, new_value
        FROM user_changes_log
        ORDER BY rowid
        """
    ).fetchall()


def test_group_and_mode_mutators_append_legacy_audit_codes(legacy_domain_db):
    student = User.get_by_id(1)
    assert student is not None

    student.set_group_id("beta")
    student.set_online_mode(ONLINE_MODE.SCHOOL)
    student.set_online_mode(ONLINE_MODE.ONLINE)

    rows = _change_rows(legacy_domain_db)
    assert [(row["user_id"], row["change_type"], row["new_value"]) for row in rows] == [
        (student.id, CHANGE.GROUP.value, "beta"),
        (student.id, CHANGE.ONLINE.value, str(ONLINE_MODE.SCHOOL.value)),
        (student.id, CHANGE.ONLINE.value, str(ONLINE_MODE.ONLINE.value)),
    ]
    assert all(datetime.fromisoformat(row["ts"]) for row in rows)

    persisted = User.get_by_id(student.id)
    assert persisted is not None
    assert persisted.group_id == "beta"
    assert persisted.online is ONLINE_MODE.ONLINE


def test_legacy_mutators_log_repeated_assignments(legacy_domain_db):
    """Legacy rows describe commands, including no-op assignments.

    A future course-enrollment backfill therefore cannot infer that every row
    denotes an actual state transition without comparing adjacent state.
    """

    student = User.get_by_id(1)
    assert student is not None
    assert student.group_id == "alpha"
    assert student.online is ONLINE_MODE.ONLINE

    student.set_group_id("alpha")
    student.set_online_mode(ONLINE_MODE.ONLINE)

    assert [
        (row["change_type"], row["new_value"]) for row in _change_rows(legacy_domain_db)
    ] == [
        (CHANGE.GROUP.value, "alpha"),
        (CHANGE.ONLINE.value, str(ONLINE_MODE.ONLINE.value)),
    ]


def test_written_discussion_preserves_telegram_source_and_result_stays_separate(
    legacy_domain_db,
):
    student = User.get_by_id(1)
    teacher = User.get_by_id(10)
    assert student is not None
    assert teacher is not None
    problem = _add_written_problem()

    student_discussion_id = WrittenQueue.add_to_discussions(
        student.id,
        problem.id,
        None,
        "Synthetic student solution",
        None,
        7_100_000_001,
        901,
    )
    teacher_discussion_id = WrittenQueue.add_to_discussions(
        student.id,
        problem.id,
        teacher.id,
        "Synthetic teacher feedback",
        None,
        7_200_000_002,
        902,
    )

    discussion = WrittenQueue.get_discussion(student.id, problem.id)
    assert [row["id"] for row in discussion] == [
        student_discussion_id,
        teacher_discussion_id,
    ]
    assert [
        (row["teacher_id"], row["chat_id"], row["tg_msg_id"]) for row in discussion
    ] == [
        (None, 7_100_000_001, 901),
        (teacher.id, 7_200_000_002, 902),
    ]

    # A non-positive verdict avoids the legacy positive-result NATS side effect:
    # this characterization must remain hermetic and is about persistence only.
    result_id = Result.add(
        student,
        problem,
        teacher,
        VERDICT.WRONG_ANSWER,
        None,
        RES_TYPE.WRITTEN,
    )
    result = legacy_domain_db.sql.conn.execute(
        "SELECT * FROM results WHERE id = ?", (result_id,)
    ).fetchone()
    assert {
        "student_id": result["student_id"],
        "problem_id": result["problem_id"],
        "teacher_id": result["teacher_id"],
        "group_id": result["group_id"],
        "lesson": result["lesson"],
        "verdict": result["verdict"],
        "res_type": result["res_type"],
    } == {
        "student_id": student.id,
        "problem_id": problem.id,
        "teacher_id": teacher.id,
        "group_id": problem.group_id,
        "lesson": problem.lesson,
        "verdict": int(VERDICT.WRONG_ANSWER),
        "res_type": int(RES_TYPE.WRITTEN),
    }
    assert "chat_id" not in result
    assert "tg_msg_id" not in result

    # The result does not consume or rewrite the Telegram-backed messages.  The
    # legacy join is the shared (student_id, problem_id), not a result FK.
    assert [
        (row["id"], row["chat_id"], row["tg_msg_id"])
        for row in WrittenQueue.get_discussion(student.id, problem.id)
    ] == [
        (student_discussion_id, 7_100_000_001, 901),
        (teacher_discussion_id, 7_200_000_002, 902),
    ]


def test_written_discussion_allows_non_telegram_provenance(legacy_domain_db):
    student = User.get_by_id(1)
    assert student is not None
    problem = _add_written_problem()

    discussion_id = WrittenQueue.add_to_discussions(
        student.id,
        problem.id,
        None,
        "Synthetic message without a Telegram origin",
        None,
        None,
        None,
    )
    row = legacy_domain_db.sql.conn.execute(
        "SELECT * FROM written_tasks_discussions WHERE id = ?", (discussion_id,)
    ).fetchone()

    assert row["chat_id"] is None
    assert row["tg_msg_id"] is None

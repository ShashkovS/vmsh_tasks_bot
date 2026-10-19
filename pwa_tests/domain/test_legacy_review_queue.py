"""Characterize the Telegram-era written review queue and synonym projection."""

from __future__ import annotations

from datetime import datetime, timedelta

from helpers.consts import WRITTEN_STATUS


def _add_problem(
    legacy_db,
    *,
    problem_id: int,
    group_id: str,
    lesson: int,
    prob: int,
    title: str,
    synonyms: str = "",
) -> None:
    with legacy_db.sql.conn as connection:
        connection.execute(
            """
            INSERT INTO problems (
                id, group_id, lesson, prob, item, title, prob_text, prob_type,
                synonyms
            ) VALUES (?, ?, ?, ?, '', ?, '', 2, ?)
            """,
            (problem_id, group_id, lesson, prob, title, synonyms),
        )


def _queue(
    legacy_db,
    *,
    problem_id: int,
    submitted_at: datetime,
    status: WRITTEN_STATUS = WRITTEN_STATUS.NEW,
    teacher_id: int | None = None,
    teacher_at: datetime | None = None,
) -> None:
    with legacy_db.sql.conn as connection:
        connection.execute(
            """
            INSERT INTO written_tasks_queue (
                ts, student_id, problem_id, cur_status, teacher_ts, teacher_id
            ) VALUES (?, 1, ?, ?, ?, ?)
            """,
            (
                submitted_at.isoformat(),
                problem_id,
                int(status),
                teacher_at.isoformat() if teacher_at else None,
                teacher_id,
            ),
        )


def test_legacy_synonyms_join_same_lesson_title_and_price_variant(legacy_domain_db):
    _add_problem(
        legacy_domain_db,
        problem_id=101,
        group_id="alpha",
        lesson=7,
        prob=1,
        title="Перекладывание фишек",
    )
    _add_problem(
        legacy_domain_db,
        problem_id=102,
        group_id="beta",
        lesson=7,
        prob=1,
        title="Перекладывание фишек",
    )
    _add_problem(
        legacy_domain_db,
        problem_id=103,
        group_id="alpha",
        lesson=7,
        prob=2,
        title="5⚡ Геометрия на клетках",
    )
    _add_problem(
        legacy_domain_db,
        problem_id=104,
        group_id="beta",
        lesson=7,
        prob=2,
        title="8⚡ Геометрия на клетках",
    )
    _add_problem(
        legacy_domain_db,
        problem_id=105,
        group_id="gamma",
        lesson=8,
        prob=1,
        title="Перекладывание фишек",
    )

    legacy_domain_db.problem.update_synonyms(join=True)
    rows = legacy_domain_db.sql.conn.execute(
        "SELECT id, synonyms FROM problems WHERE id BETWEEN 101 AND 105 ORDER BY id"
    ).fetchall()
    assert {row["id"]: row["synonyms"] for row in rows} == {
        101: "101;102",
        102: "101;102",
        103: "103;104",
        104: "103;104",
        105: "105",
    }

    legacy_domain_db.problem.update_synonyms(join=False)
    rows = legacy_domain_db.sql.conn.execute(
        "SELECT id, synonyms FROM problems WHERE id BETWEEN 101 AND 105 ORDER BY id"
    ).fetchall()
    assert [row["synonyms"] for row in rows] == ["101", "102", "103", "104", "105"]


def test_review_selection_honours_lease_owner_age_group_and_order(legacy_domain_db):
    now = datetime.now()
    synonym_key = "201;202;203;204;205"
    for problem_id, group_id in (
        (201, "alpha"),
        (202, "alpha"),
        (203, "beta"),
        (204, "beta"),
        (205, "gamma"),
    ):
        _add_problem(
            legacy_domain_db,
            problem_id=problem_id,
            group_id=group_id,
            lesson=9,
            prob=problem_id,
            title="Shared review case",
            synonyms=synonym_key,
        )

    _queue(legacy_domain_db, problem_id=201, submitted_at=now - timedelta(minutes=60))
    _queue(
        legacy_domain_db,
        problem_id=202,
        submitted_at=now - timedelta(minutes=50),
        status=WRITTEN_STATUS.BEING_CHECKED,
        teacher_id=11,
        teacher_at=now,
    )
    _queue(
        legacy_domain_db,
        problem_id=203,
        submitted_at=now - timedelta(minutes=40),
        status=WRITTEN_STATUS.BEING_CHECKED,
        teacher_id=11,
        teacher_at=now - timedelta(minutes=31),
    )
    _queue(
        legacy_domain_db,
        problem_id=204,
        submitted_at=now - timedelta(minutes=30),
        status=WRITTEN_STATUS.BEING_CHECKED,
        teacher_id=10,
        teacher_at=now,
    )
    _queue(legacy_domain_db, problem_id=205, submitted_at=now - timedelta(minutes=20))

    rows = legacy_domain_db.written_task_queue.get_written_tasks_to_check(
        10,
        synonym_key,
        group_ids={"alpha", "beta"},
    )
    assert [row["problem_id"] for row in rows] == [201, 203, 204]

    assert (
        legacy_domain_db.written_task_queue.upd_written_task_status(
            1, 201, WRITTEN_STATUS.BEING_CHECKED, 10
        )
        == 1
    )
    assert (
        legacy_domain_db.written_task_queue.upd_written_task_status(
            1, 201, WRITTEN_STATUS.BEING_CHECKED, 11
        )
        == 0
    )
    assert (
        legacy_domain_db.written_task_queue.upd_written_task_status(
            1, 201, WRITTEN_STATUS.BEING_CHECKED, 10
        )
        == 1
    )

    with legacy_domain_db.sql.conn as connection:
        connection.execute(
            "UPDATE written_tasks_queue SET teacher_ts = ? WHERE problem_id = 201",
            ((now - timedelta(minutes=31)).isoformat(),),
        )
    assert (
        legacy_domain_db.written_task_queue.upd_written_task_status(
            1, 201, WRITTEN_STATUS.BEING_CHECKED, 11
        )
        == 1
    )


def test_review_selection_is_limited_to_eight_oldest_submissions(legacy_domain_db):
    now = datetime.now()
    problem_ids = list(range(301, 311))
    synonym_key = ";".join(map(str, problem_ids))
    for offset, problem_id in enumerate(problem_ids):
        _add_problem(
            legacy_domain_db,
            problem_id=problem_id,
            group_id="alpha" if offset % 2 == 0 else "beta",
            lesson=10,
            prob=offset + 1,
            title="Large shared review case",
            synonyms=synonym_key,
        )
        _queue(
            legacy_domain_db,
            problem_id=problem_id,
            submitted_at=now + timedelta(seconds=offset),
        )

    rows = legacy_domain_db.written_task_queue.get_written_tasks_to_check(
        10, synonym_key
    )
    assert [row["problem_id"] for row in rows] == problem_ids[:8]


def test_negative_problem_id_is_the_legacy_sos_partition(legacy_domain_db):
    _add_problem(
        legacy_domain_db,
        problem_id=401,
        group_id="alpha",
        lesson=11,
        prob=1,
        title="SOS source task",
        synonyms="401",
    )
    with legacy_domain_db.sql.conn as connection:
        connection.execute(
            """
            INSERT INTO written_tasks_queue (ts, student_id, problem_id, cur_status)
            VALUES (?, 1, -401, ?)
            """,
            (datetime.now().isoformat(), int(WRITTEN_STATUS.NEW)),
        )

    assert legacy_domain_db.written_task_queue.get_written_tasks_count({"alpha"}) == 0
    assert legacy_domain_db.written_task_queue.get_sos_tasks_count({"alpha"}) == 1
    rows = legacy_domain_db.written_task_queue.get_sos_tasks_to_check(
        10, group_ids={"alpha"}
    )
    assert [row["problem_id"] for row in rows] == [-401]

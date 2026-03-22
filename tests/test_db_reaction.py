from __future__ import annotations

import db_methods as db
from helpers.consts import REACTION, RES_TYPE, VERDICT
from models import Problem


def test_reaction_db_insert_enum_and_types(live_seed_db):
    student = live_seed_db.get_user("qwerty1")
    teacher = live_seed_db.get_teacher()
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None
    result_id = db.result.insert(
        student.id,
        problem.id,
        problem.lesson,
        teacher.id,
        int(VERDICT.SOLVED),
        None,
        int(RES_TYPE.WRITTEN),
        None,
        group_id=problem.group_id,
    )

    reaction_types = db.reaction.types()
    assert reaction_types
    reactions = db.reaction.enum(REACTION.WRITTEN_STUDENT)
    assert reactions

    inserted_id = db.reaction.insert(
        result_id=result_id,
        zoom_conversation_id=None,
        reaction_type_id=REACTION.WRITTEN_STUDENT,
        reaction_id=reactions[0]["reaction_id"],
    )
    row = db.sql.conn.execute("select * from reactions where id = :id", {"id": inserted_id}).fetchone()

    assert row is not None
    assert row["result_id"] == result_id
    assert db.reaction.get_by_id(reactions[0]["reaction_id"]) == reactions[0]["reaction"]

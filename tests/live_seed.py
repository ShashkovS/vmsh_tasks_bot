from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import db_methods as db
from helpers.consts import ANS_TYPE, PROB_TYPE, RES_TYPE, STATE, VERDICT
from models import Problem, Result, State as StateModel, User, WrittenQueue


LIVE_SEED_PATH = Path(__file__).resolve().parent / "fixtures" / "live_seed.json"


def _insert_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with db.sql.conn as conn:
        for row in rows:
            columns = ", ".join(row.keys())
            placeholders = ", ".join(f":{column}" for column in row.keys())
            conn.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                row,
            )


def load_live_seed(seed_path: Path = LIVE_SEED_PATH) -> dict[str, Any]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    tables = payload["tables"]
    with db.sql.conn as conn:
        conn.execute("DELETE FROM groups")
    for table_name in ("groups", "users", "problems", "states", "results", "messages_log", "signons"):
        _insert_rows(table_name, tables.get(table_name, []))
    db.lesson.update()
    db.problem.update_synonyms(join=False)
    return payload


@dataclass
class LiveScenarioBuilder:
    seed: dict[str, Any]

    def get_user(self, token: str) -> User:
        user = User.get_by_token(token)
        assert user is not None, token
        return user

    def get_teacher(self) -> User:
        teacher = next(User.all_teachers(), None)
        assert teacher is not None
        return teacher

    def bind_chat(self, user: User, chat_id: int) -> User:
        user.set_chat_id(chat_id)
        rebound = User.get_by_id(user.id)
        assert rebound is not None
        return rebound

    def add_problem(
        self,
        *,
        group_id: str,
        lesson: int,
        prob: int,
        title: str,
        prob_type: PROB_TYPE,
        item: str = "",
        ans_type: ANS_TYPE | str | None = None,
        ans_validation: str = "",
        validation_error: str = "",
        cor_ans: str = "",
        cor_ans_checker: str = "",
        wrong_ans: str = "",
        congrat: str = "",
    ) -> Problem:
        created = Problem(
            group_id=group_id,
            lesson=lesson,
            prob=prob,
            item=item,
            title=title,
            prob_text="",
            prob_type=int(prob_type),
            ans_type=(int(ans_type) if ans_type else ""),
            ans_validation=ans_validation,
            validation_error=validation_error,
            cor_ans=cor_ans,
            cor_ans_checker=cor_ans_checker,
            wrong_ans=wrong_ans,
            congrat=congrat,
        )
        db.lesson.update()
        db.problem.update_synonyms(join=False)
        refreshed = Problem.get_by_id(created.id)
        assert refreshed is not None
        return refreshed

    def add_test_result(
        self,
        *,
        student: User,
        problem: Problem,
        answer: str,
        verdict: VERDICT,
        teacher: User | None = None,
        res_type: RES_TYPE = RES_TYPE.TEST,
    ) -> int:
        return Result.add(student, problem, teacher, verdict, answer, res_type)

    def add_written_submission(
        self,
        *,
        student: User,
        problem: Problem,
        text: str,
        chat_id: int,
        tg_msg_id: int,
    ) -> None:
        WrittenQueue.add_to_discussions(student.id, problem.id, None, text, None, chat_id, tg_msg_id)
        WrittenQueue.add_to_queue(student.id, problem.id)

    def set_state(self, user: User, state: STATE, *, problem_id: int = 0) -> None:
        StateModel.set_by_user_id(user.id, state, problem_id=problem_id)

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from helpers.consts import *
import db_methods as db


@dataclass
class Problem:
    level: str
    lesson: int
    prob: int
    item: str
    title: str
    prob_text: str
    prob_type: int
    ans_type: int
    ans_validation: str
    validation_error: str
    cor_ans: str
    cor_ans_checker: str
    wrong_ans: str
    congrat: str
    synonyms: str = None  # Список синонимичных задач
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.problem.insert(self.__dict__)
        self.prob_type = PROB_TYPE(self.prob_type)
        if self.ans_type:
            self.ans_type = ANS_TYPE(self.ans_type)

    def __str__(self):
        # return f"Задача {self.lesson}{self.level}.{self.prob}{self.item}. {self.title}"
        return f"{self.lesson}{self.level}.{self.prob}{self.item} — {self.title}"

    def str_num(self):
        return f"{self.lesson}{self.level}.{self.prob}{self.item}. {self.title}"

    @classmethod
    def get_by_id(cls, id: int) -> Optional[Problem]:
        problem = db.problem.get_by_id(id)
        return problem and cls(**problem)

    @classmethod
    def get_by_key(cls, level: str, lesson: int, prob: int, item: ''):
        problem = db.problem.get_by_text_number(level, lesson, prob, item)
        return problem and cls(**problem)

    @classmethod
    def get_by_lesson(cls, level: str, lesson: int):
        problems = db.problem.get_all_by_lesson(level, lesson) or []
        return [cls(**problem) for problem in problems]

    @staticmethod
    def last_lesson_num(level: str = None) -> int:
        return db.lesson.get_last(level)

    @classmethod
    def oral_to_written(cls, levels=None):
        lesson = cls.last_lesson_num()
        for level in levels or LEVEL:
            db.problem.update_type(level, lesson, PROB_TYPE.ORALLY, PROB_TYPE.WRITTEN_BEFORE_ORALLY)

    @classmethod
    def written_to_oral(cls, levels=None):
        lesson = cls.last_lesson_num()
        for level in levels or LEVEL:
            db.problem.update_type(level, lesson, PROB_TYPE.WRITTEN_BEFORE_ORALLY, PROB_TYPE.ORALLY)

    def synonyms_set(self):
        return set(map(int, self.synonyms.split(';')))

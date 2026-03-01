# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Iterable, Tuple, Set

from helpers.consts import *
import db_methods as db


@dataclass
class Problem:
    group_id: str
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
    group_code: str = None
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.problem.insert(self.__dict__)
        if not self.group_code:
            group = db.group.get_by_id(self.group_id)
            self.group_code = (group and group.get('short_code')) or self.group_id
        self.prob_type = PROB_TYPE(self.prob_type)
        if self.ans_type:
            self.ans_type = ANS_TYPE(self.ans_type)

    def __str__(self):
        return f"{self.lesson}{self.group_code}.{self.prob}{self.item} — {self.title}"

    def str_num(self):
        return f"{self.lesson}{self.group_code}.{self.prob}{self.item}. {self.title}"

    @classmethod
    def get_by_id(cls, id: int) -> Optional[Problem]:
        problem = db.problem.get_by_id(id)
        return problem and cls(**problem)

    @classmethod
    def get_by_key(cls, group_id: str, lesson: int, prob: int, item: ''):
        problem = db.problem.get_by_text_number(group_id, lesson, prob, item)
        return problem and cls(**problem)

    @classmethod
    def get_by_lesson(cls, group_id: str, lesson: int):
        problems = db.problem.get_all_by_lesson(group_id, lesson) or []
        return [cls(**problem) for problem in problems]

    @staticmethod
    def last_lesson_num(group_id: str = None) -> int:
        return db.lesson.get_last(group_id=group_id)

    @staticmethod
    def parse_problem_ref(raw: str) -> Optional[Tuple[Optional[str], Optional[str], int, int, str]]:
        """Возвращает tuple(kind, group_token, lesson, prob, item)
        kind:
            - "group_id": формат <group_id>:<lesson>.<prob><item>
            - "group_code": формат <lesson><group_code>.<prob><item>
        """
        if not raw:
            return None
        text = raw.strip()
        explicit = re.fullmatch(r'([^:\s]+):(\d+)\.(\d+)([а-яА-Яa-zA-Z]?)', text)
        if explicit:
            group_id, lesson, prob, item = explicit.groups()
            return "group_id", group_id, int(lesson), int(prob), item
        compact = re.fullmatch(r'(\d+)([^\d\.\s]+)\.(\d+)([а-яА-Яa-zA-Z]?)', text)
        if compact:
            lesson, group_code, prob, item = compact.groups()
            return "group_code", group_code, int(lesson), int(prob), item
        return None

    @classmethod
    def resolve_problem_ref(
        cls,
        raw: str,
        *,
        allowed_group_ids: Optional[Iterable[str]] = None,
    ) -> Tuple[Optional["Problem"], Optional[str]]:
        """Возвращает (problem, error_code).
        error_code in {"invalid", "not_found", "ambiguous"}.
        """
        # Возможно, это id
        allowed: Optional[Set[str]] = set(allowed_group_ids) if allowed_group_ids else None
        if raw.isdecimal():
            problem = cls.get_by_id(int(raw))
            if not problem:
                return None, "not_found"
            if problem.group_id not in allowed:
                return None, "not_found"
            return problem, None
        parsed = cls.parse_problem_ref(raw)
        if not parsed:
            return None, "invalid"
        kind, group_token, lesson, prob, item = parsed
        if kind == "group_id":
            if allowed is not None and group_token not in allowed:
                return None, "not_found"
            problem = cls.get_by_key(group_token, lesson, prob, item)
            if not problem:
                return None, "not_found"
            return problem, None
        candidates = db.group.get_by_short_code(group_token)
        if allowed is not None:
            candidates = [group for group in candidates if group["group_id"] in allowed]
        if not candidates:
            return None, "not_found"
        matches = []
        for group in candidates:
            found = cls.get_by_key(group["group_id"], lesson, prob, item)
            if found:
                matches.append(found)
        if not matches:
            return None, "not_found"
        if len(matches) > 1:
            return None, "ambiguous"
        return matches[0], None

    @classmethod
    def oral_to_written(cls, group_ids=None):
        lesson = cls.last_lesson_num()
        if group_ids:
            for group_id in group_ids:
                db.problem.update_type(lesson, PROB_TYPE.ORALLY, PROB_TYPE.WRITTEN_BEFORE_ORALLY, group_id=group_id)
            return
        for group in db.group.get_all():
            db.problem.update_type(
                lesson,
                PROB_TYPE.ORALLY,
                PROB_TYPE.WRITTEN_BEFORE_ORALLY,
                group_id=group.get('group_id'),
            )

    @classmethod
    def written_to_oral(cls, group_ids=None):
        lesson = cls.last_lesson_num()
        if group_ids:
            for group_id in group_ids:
                db.problem.update_type(lesson, PROB_TYPE.WRITTEN_BEFORE_ORALLY, PROB_TYPE.ORALLY, group_id=group_id)
            return
        for group in db.group.get_all():
            db.problem.update_type(
                lesson,
                PROB_TYPE.WRITTEN_BEFORE_ORALLY,
                PROB_TYPE.ORALLY,
                group_id=group.get('group_id'),
            )

    def synonyms_set(self):
        return set(map(int, self.synonyms.split(';')))

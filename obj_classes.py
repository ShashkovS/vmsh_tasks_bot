# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Generator, List

from consts import *
from config import config, logger
from db_methods import db
from loader_from_google_spreadsheets import google_spreadsheet_loader


def _normilize_token(token: str, *, RU_TO_EN=str.maketrans('УКЕНХВАРОСМТукехарос', 'YKEHXBAPOCMTykexapoc')) -> str:
    return token.strip().translate(RU_TO_EN).lower()


@dataclass
class User:
    chat_id: int
    type: int
    level: str
    name: str
    surname: str
    middlename: str
    token: str
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.add_user(self.__dict__)

    def set_chat_id(self, chat_id: int):
        db.set_user_chat_id(self.id, chat_id)
        self.chat_id = chat_id

    def set_level(self, level: LEVEL):
        db.set_user_level(self.id, level.value)
        self.level = level.value

    def __str__(self):
        return f'{self.name} {self.middlename} {self.surname}'

    @classmethod
    def all(cls) -> Generator[User, None, None]:
        for user in db.fetch_all_users_by_type():
            yield cls(**user)

    @classmethod
    def all_students(cls) -> Generator[User, None, None]:
        for user in db.fetch_all_users_by_type(USER_TYPE.STUDENT):
            yield cls(**user)

    @classmethod
    def all_teachers(cls) -> Generator[User, None, None]:
        for user in db.fetch_all_users_by_type(USER_TYPE.TEACHER):
            yield cls(**user)

    @classmethod
    def get_by_chat_id(cls, chat_id: int) -> Optional[User]:
        user = db.get_user_by_chat_id(chat_id)
        return user and cls(**user)  # None -> None

    @classmethod
    def get_by_token(cls, token: str) -> Optional[User]:
        if not token:
            return None
        user = db.get_user_by_token(_normilize_token(token))
        return user and cls(**user)  # None -> None

    @classmethod
    def get_by_id(cls, id: int) -> Optional[User]:
        user = db.get_user_by_id(id)
        return user and cls(**user)  # None -> None


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
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.add_problem(self.__dict__)

    def __str__(self):
        return f"Задача {self.lesson}{self.level}.{self.prob}{self.item}. {self.title}"

    @classmethod
    def get_by_id(cls, id: int) -> Optional[Problem]:
        problem = db.get_problem_by_id(id)
        return problem and cls(**problem)

    @classmethod
    def get_by_key(cls, level: str, lesson: int, prob: int, item: ''):
        problem = db.get_problem_by_text_number(level, lesson, prob, item)
        return problem and cls(**problem)

    @classmethod
    def get_by_lesson(cls, level: str, lesson: int):
        problems = db.fetch_all_problems_by_lesson(level, lesson) or []
        return [cls(**problem) for problem in problems]

    @staticmethod
    def last_lesson_num() -> int:
        return db.get_last_lesson_num()


class State:
    @staticmethod
    def get_by_user_id(user_id: int):
        return db.get_state_by_user_id(user_id)

    @staticmethod
    def set_by_user_id(user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                       last_teacher_id: int = 0, oral_problem_id: int = None):
        db.update_state(user_id, state, problem_id, last_student_id, last_teacher_id, oral_problem_id)


class Waitlist:
    @staticmethod
    def enter(student_id: int, problem_id: int):
        db.update_oral_problem(student_id, problem_id)
        db.add_user_to_waitlist(student_id, problem_id)

    @staticmethod
    def leave(student_id: int):
        db.update_oral_problem(student_id, None)
        db.remove_user_from_waitlist(student_id)

    @staticmethod
    def top(n: int = 10) -> list:
        return db.get_waitlist_top(n)


class WrittenQueue:
    @staticmethod
    def add_to_queue(student_id: int, problem_id: int, ts: datetime = None):
        db.insert_into_written_task_queue(student_id, problem_id, cur_status=WRITTEN_STATUS.NEW, ts=ts)

    @staticmethod
    def take_top(teacher_id: int):
        return db.get_written_tasks_to_check(teacher_id)

    @staticmethod
    def mark_being_checked(student_id: int, problem_id: int, teacher_id: int):
        updated_rows = db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.BEING_CHECKED, teacher_id)
        return updated_rows > 0

    @staticmethod
    def mark_not_being_checked(student_id: int, problem_id: int):
        db.upd_written_task_status(student_id, problem_id, WRITTEN_STATUS.NEW, None)

    @staticmethod
    def delete_from_queue(student_id: int, problem_id: int):
        db.delete_from_written_task_queue(student_id, problem_id)

    @staticmethod
    def add_to_discussions(student_id: int, problem_id: int, teacher_id: Optional[int], text: str, attach_path: Optional[str], chat_id: int, tg_msg_id: int):
        db.insert_into_written_task_discussion(student_id, problem_id, teacher_id, text, attach_path, chat_id, tg_msg_id)

    @staticmethod
    def get_discussion(student_id: int, problem_id: int):
        return db.fetch_written_task_discussion(student_id, problem_id)


class Result:
    @staticmethod
    def add(student: User, problem: Problem, teacher: User, verdict: int, answer: str, res_type: int = None):
        return db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher and teacher.id, verdict, answer, res_type)


class FromGoogleSpreadsheet:
    @staticmethod
    def update_all():
        problems, students, teachers = google_spreadsheet_loader.get_all()
        FromGoogleSpreadsheet.problems_to_db(problems)
        FromGoogleSpreadsheet.students_to_db(students)
        FromGoogleSpreadsheet.teachers_to_db(teachers)

    @staticmethod
    def update_problems():
        problems = google_spreadsheet_loader.get_problems()
        FromGoogleSpreadsheet.problems_to_db(problems)

    @staticmethod
    def update_students():
        students = google_spreadsheet_loader.get_students()
        FromGoogleSpreadsheet.students_to_db(students)

    @staticmethod
    def update_teachers():
        teachers = google_spreadsheet_loader.get_teachers()
        FromGoogleSpreadsheet.teachers_to_db(teachers)

    @staticmethod
    def students_to_db(students: List[dict]):
        for student in students:
            student['type'] = USER_TYPE.STUDENT
            student['chat_id'] = None
            student['middlename'] = ''
            User(**student)

    @staticmethod
    def teachers_to_db(teachers: List[dict]):
        for teacher in teachers:
            teacher['type'] = USER_TYPE.TEACHER
            teacher['chat_id'] = None
            teacher['level'] = None
            User(**teacher)

    @staticmethod
    def problems_to_db(problems: List[dict]):
        for problem in problems:
            try:
                problem['prob_type'] = PROB_TYPES_DECODER[problem['prob_type']]
                problem['ans_type'] = ANS_TYPES_DECODER[problem['ans_type']]
            except:
                logger.error(f'Криво настроена задача: {problem!r}')
                continue
            Problem(**problem)
            db.update_lessons()


# db.setup(config.db_filename)
# google_spreadsheet_loader.setup(config.dump_filename, config.google_sheets_key, config.google_cred_json)
#
# # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы
# all_teachers = list(User.all_teachers())
# if len(all_teachers) == 0:
#     FromGoogleSpreadsheet.update_all()
#     all_teachers = list(User.all_teachers())
# logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')

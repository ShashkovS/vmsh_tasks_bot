# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Generator, List
import secrets
import orjson

from helpers.consts import *
from helpers.config import config, logger
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
from db_methods import db
from helpers.nats_brocker import vmsh_nats


def _normilize_token(token: str, *, RU_TO_EN=str.maketrans('УКЕНХВАРОСМТукехарос', 'YKEHXBAPOCMTykexapoc')) -> str:
    return token.strip().translate(RU_TO_EN).lower()


@dataclass
class User:
    chat_id: int
    type: USER_TYPE
    level: LEVEL
    name: str
    surname: str
    middlename: str
    token: str
    online: ONLINE_MODE
    grade: int
    birthday: date
    id: int = None

    def __post_init__(self):
        # Заполняем дефолтные значения
        if not self.level:
            self.level = LEVEL.NOVICE
        if not self.online:
            self.online = ONLINE_MODE.ONLINE
        # Заливаем в базу, если значение не из базы
        if self.id is None:
            self.id = db.add_user(self.__dict__)
        # Превращаем константы в enum'ы
        self.type = USER_TYPE(self.type)
        self.level = LEVEL(self.level) if self.level else None
        self.online = ONLINE_MODE(self.online) if self.online else None

    def set_chat_id(self, chat_id: int):
        db.set_user_chat_id(self.id, chat_id)
        self.chat_id = chat_id

    def set_level(self, level: LEVEL):
        db.set_user_level(self.id, level.value)
        db.log_change(self.id, CHANGE.LEVEL, level.value)
        self.level = level

    def set_user_type(self, user_type: USER_TYPE):
        db.set_user_type(self.id, user_type.value)
        self.type = user_type.value

    def set_online_mode(self, online: ONLINE_MODE):
        db.set_user_online_mode(self.id, online.value)
        db.log_change(self.id, CHANGE.ONLINE, online.value)
        self.online = online

    def __str__(self):
        return f'{self.name} {self.middlename} {self.surname}'

    def name_for_teacher(self):
        age = ''
        if self.birthday:
            try:
                age = f"возраст: {((datetime.now().date() - date.fromisoformat(self.birthday)).days / 365.25):0.1f}"
            except Exception as e:
                logger.exception(f'Дата рождения не парсится: {self.birthday}')
        if self.grade:
            grade = f'класс: {self.grade}'
        else:
            grade = ''
        return f'{self.name} {self.surname} {self.token}\nуровень: {self.level} {grade} {age}'

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
    synonyms: str = None  # Список синонимичных задач
    id: int = None

    def __post_init__(self):
        if self.id is None:
            self.id = db.add_problem(self.__dict__)
        self.prob_type = PROB_TYPE(self.prob_type)
        if self.ans_type:
            self.ans_type = ANS_TYPE(self.ans_type)

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
    def last_lesson_num(level: str = None) -> int:
        return db.get_last_lesson_num(level)

    @classmethod
    def oral_to_written(cls, levels=None):
        lesson = cls.last_lesson_num()
        for level in levels or LEVEL:
            db.update_problem_type(level, lesson, PROB_TYPE.ORALLY, PROB_TYPE.WRITTEN_BEFORE_ORALLY)

    @classmethod
    def written_to_oral(cls, levels=None):
        lesson = cls.last_lesson_num()
        for level in levels or LEVEL:
            db.update_problem_type(level, lesson, PROB_TYPE.WRITTEN_BEFORE_ORALLY, PROB_TYPE.ORALLY)

    @staticmethod
    def get_all_tags():
        return db.get_all_tags()

    def update_tags(self, tags: str, user: User):
        return db.add_tags(self.id, tags, user.id)

    def get_tags(self):
        return db.get_tags_by_problem_id(self.id)

    def synonyms_set(self):
        return set(map(int, self.synonyms.split(';')))


class State:
    @staticmethod
    def get_by_user_id(user_id: int):
        state = db.get_state_by_user_id(user_id) or {}
        if state.get('info', None):
            state['info'] = orjson.loads(state['info'])
        return state

    @staticmethod
    def set_by_user_id(user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0,
                       last_teacher_id: int = 0, oral_problem_id: int = None, info=None):
        if info is not None:
            info = orjson.dumps(info)
        db.update_state(user_id, state, problem_id, last_student_id, last_teacher_id, oral_problem_id, info)


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
    def take_top_synonyms(teacher_id: int, synonyms: str):
        return db.get_written_tasks_to_check(teacher_id, synonyms)

    @staticmethod
    def take_sos_top(teacher_id: int):
        return db.get_sos_tasks_to_check(teacher_id)

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
    def add_to_discussions(student_id: int, problem_id: int, teacher_id: Optional[int], text: str, attach_path: Optional[str], chat_id: int, tg_msg_id: int) -> int:
        wtd_id = db.insert_into_written_task_discussion(student_id, problem_id, teacher_id, text, attach_path, chat_id, tg_msg_id)
        return wtd_id

    @staticmethod
    def get_discussion(student_id: int, problem_id: int):
        return db.fetch_written_task_discussion(student_id, problem_id)


class Result:
    @staticmethod
    def add(student: User, problem: Problem, teacher: Optional[User], verdict: VERDICT, answer: Optional[str], res_type: RES_TYPE, zoom_conversation_id: int = None) -> int:
        result_id = db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher and teacher.id, verdict, answer, res_type, zoom_conversation_id)
        if verdict > 0:
            asyncio.create_task(vmsh_nats.publish(NATS_GAME_STUDENT_UPDATE, student.id))
        return result_id


class FromGoogleSpreadsheet:
    @staticmethod
    def update_all() -> List[str]:
        problems, students, teachers = google_spreadsheet_loader.get_all()
        errors = FromGoogleSpreadsheet.problems_to_db(problems)
        FromGoogleSpreadsheet.students_to_db(students)
        FromGoogleSpreadsheet.teachers_to_db(teachers)
        return errors

    @staticmethod
    def update_problems() -> List[str]:
        problems = google_spreadsheet_loader.get_problems()
        errors = FromGoogleSpreadsheet.problems_to_db(problems)
        return errors

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
            student['middlename'] = ''
            student['chat_id'] = None
            student['birthday'] = student['birthday'] or None
            student['grade'] = int(student['grade']) if student['grade'] else None
            try:
                student['online'] = ONLINE_MODE_DECODER[student['online']]
            except:
                student['online'] = ONLINE_MODE.ONLINE
            User(**student)

    @staticmethod
    def teachers_to_db(teachers: List[dict]):
        for teacher in teachers:
            teacher['type'] = USER_TYPE.TEACHER
            for non_teacher_key in ['chat_id', 'level', 'grade', 'birthday']:
                teacher[non_teacher_key] = None
            try:
                teacher['online'] = ONLINE_MODE_DECODER[teacher['online']]
            except:
                teacher['online'] = ONLINE_MODE.ONLINE
            User(**teacher)

    @staticmethod
    def problems_to_db(problems: List[dict]) -> List[str]:
        errors = []
        for problem in problems:
            if problem['level'] == problem['lesson'] == problem['lesson'] == problem['item'] == '':
                continue
            try:
                problem['prob_type'] = PROB_TYPES_DECODER[problem['prob_type']]
            except:
                errors.append(f'Кривой тип задачи у {problem!r}')
                continue
            try:
                if problem['prob_type'] == PROB_TYPE.TEST:
                    problem['ans_type'] = ANS_TYPES_DECODER[problem['ans_type']]
                else:
                    problem['ans_type'] = ''
            except:
                errors.append(f'Кривой тип ответа у тестовой задачи {problem!r}')
                continue
            try:
                if problem['ans_validation']:
                    re.compile(problem['ans_validation'])
            except:
                errors.append(f'Не компилируется регулярка валидации у задачи {problem!r}')
                continue
            Problem(**problem)
        # TODO Попахивает риском продолбать важное :(
        db.update_lessons()
        db.update_synonyms()
        return errors


def update_from_google_if_db_is_empty():
    # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы (иначе даже админ не сможет залогиниться)
    all_teachers = list(User.all_teachers())
    if len(all_teachers) == 0:
        FromGoogleSpreadsheet.update_all()
        all_teachers = list(User.all_teachers())
    logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')


class Webtoken:
    @staticmethod
    def gen_new_webtoken(tok_len=16, chars='23456789abcdefghijkmnpqrstuvwxyz') -> str:
        return ''.join(secrets.choice(chars) for _ in range(tok_len))

    @staticmethod
    def user_by_webtoken(webtoken: str) -> Optional[User]:
        if not webtoken:
            return None
        user_id = db.get_user_id_by_webtoken(webtoken)
        return user_id and User.get_by_id(user_id)  # None -> None

    @staticmethod
    def webtoken_by_user(user: User) -> str:
        if not user:
            return None
        webtoken = db.get_webtoken_by_user_id(user.id)
        if webtoken is None:
            webtoken = Webtoken.gen_new_webtoken()
            db.add_webtoken(user.id, webtoken)
        return webtoken

# db.setup(config.db_filename)
# google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
#
# # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы
# all_teachers = list(User.all_teachers())
# if len(all_teachers) == 0:
#     FromGoogleSpreadsheet.update_all()
#     all_teachers = list(User.all_teachers())
# logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')

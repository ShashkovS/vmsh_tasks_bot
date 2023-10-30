# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import List

from helpers.consts import *
from helpers.config import logger
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
import db_methods as db
from .state import State
from .user import User
from .problem import Problem

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
        print(students)
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
            user = User(**student)
            State.set_by_user_id(user.id, STATE.GET_TASK_INFO)


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
        db.lesson.update()
        db.problem.update_synonyms()
        return errors


def update_from_google_if_db_is_empty():
    # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы (иначе даже админ не сможет залогиниться)
    all_teachers = list(User.all_teachers())
    if len(all_teachers) == 0:
        FromGoogleSpreadsheet.update_all()
        all_teachers = list(User.all_teachers())
    logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')


# db.sql.setup(config.db_filename)
# google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
#
# # Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы
# all_teachers = list(User.all_teachers())
# if len(all_teachers) == 0:
#     FromGoogleSpreadsheet.update_all()
#     all_teachers = list(User.all_teachers())
# logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')

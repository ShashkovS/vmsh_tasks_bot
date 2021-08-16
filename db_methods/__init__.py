# -*- coding: utf-8 -*-
"""
По разным файлам раскиданы API для чтения/записи/обновления, сгруппированные по смыслу.
Здесь мы соединяем это всё в супер-класс DB, который умеет все-все-все методы
"""
from .db_abc import DB_CONNECTION
from .db_users import DB_USER
from .db_problems import DB_PROBLEM
from .db_lessons import DB_LESSON
from .db_states import DB_STATE
from .db_results import DB_RESULT
from .db_written_tasks_queue import DB_WRITTENTASKQUEUE
from .db_waitlist import DB_WAITLIST
from .db_written_task_discussion import DB_WRITTEN_TASK_DISCUSSION
from .db_features import DB_FEATURES


class DB(DB_CONNECTION, DB_USER, DB_PROBLEM, DB_LESSON, DB_STATE, DB_RESULT, DB_WRITTENTASKQUEUE, DB_WAITLIST, DB_WRITTEN_TASK_DISCUSSION, DB_FEATURES):
    pass


# Перед использованием объекта db, нужно открыть коннекшн командой вида
# db.setup(db_file="some.db")
db = DB()

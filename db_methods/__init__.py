# -*- coding: utf-8 -*-
"""
По разным файлам раскиданы API для чтения/записи/обновления, сгруппированные по смыслу.
Здесь мы соединяем это всё в супер-класс DB, который умеет все-все-все методы
"""

# Можно было бы подгружать все модули автоматом, но тогда подсказки в IDE работают хуже
"""
from pathlib import Path

modules = Path(__file__).parent.glob('db*.py')
__all__ = [module.stem for module in modules]
all_db_classes = []
for module in __all__:
    imported_module = __import__(module)
    classes = [getattr(imported_module, db_class) for db_class in dir(imported_module) if db_class.startswith('DB_')]
    all_db_classes.extend(classes)
print(all_db_classes)


class DB(*all_db_classes):
    pass
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
from .db_webtokens import DB_WEBTOKEN
from .db_last_keyboards import DB_LAST_KEYBOARD
from .db_zoom_queue import DB_ZOOM_QUEUE
from .db_problem_tags import DB_PROBLEM_TAGS
from .db_media_groups import DB_MEDIA_GROUPS
# from .db_zoom_confs import DB_ZOOM_CONF
from .db_student_reaction import DB_STUDENT_REACTION
from .db_teacher_reaction import DB_TEACHER_REACTION
from .db_game import DB_GAME

class DB(DB_CONNECTION, DB_USER, DB_PROBLEM, DB_LESSON, DB_STATE, DB_RESULT, DB_WRITTENTASKQUEUE, DB_WAITLIST, DB_WRITTEN_TASK_DISCUSSION, DB_FEATURES,
         DB_WEBTOKEN, DB_LAST_KEYBOARD,
         DB_ZOOM_QUEUE, DB_PROBLEM_TAGS,
         DB_MEDIA_GROUPS,
         # DB_ZOOM_CONF,
         DB_STUDENT_REACTION,
         DB_TEACHER_REACTION,
         DB_GAME
         ):
    pass


# Перед использованием объекта db, нужно открыть коннекшн командой вида
# db.setup(db_file="some.db")
db = DB()

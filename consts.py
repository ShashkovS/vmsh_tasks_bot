# -*- coding: utf-8 -*-
from enum import Enum, IntEnum, unique


# СОСТОЯНИЯ
# Важно, чтобы каждый state был уникальной числовой константой, которая больше никогда не меняется
# (так как она сохраняется в БД)
@unique
class STATE(IntEnum):
    GET_USER_INFO = 1
    GET_TASK_INFO = 2
    SENDING_SOLUTION = 3
    SENDING_TEST_ANSWER = 4
    WAIT_SOS_REQUEST = 5
    TEACHER_SELECT_ACTION = 6
    TEACHER_ACCEPTED_QUEUE = 7
    TEACHER_IS_CHECKING_TASK = 8
    STUDENT_IS_IN_CONFERENCE = 9
    TEACHER_WRITES_STUDENT_NAME = 10
    STUDENT_IS_SLEEPING = 12


# ПРЕФИКСЫ ДАННЫХ ДЛЯ КОЛЛБЕКОВ
# Важно, чтобы константа была уникальной буков (там хардкод взятия первой буквы)
@unique
class CALLBACK(Enum):
    PROBLEM_SELECTED = 't'
    SHOW_LIST_OF_LISTS = 'a'
    LIST_SELECTED = 'l'
    ONE_OF_TEST_ANSWER_SELECTED = 'x'
    CANCEL_TASK_SUBMISSION = 'c'
    GET_QUEUE_TOP = 'q'
    INS_ORAL_PLUSSES = 'i'
    SET_VERDICT = 'v'
    GET_WRITTEN_TASK = 'w'
    WRITTEN_TASK_SELECTED = 'W'
    TEACHER_CANCEL = 'R'
    WRITTEN_TASK_OK = 'O'
    WRITTEN_TASK_BAD = 'B'
    GET_OUT_OF_WAITLIST = 'X'
    ADD_OR_REMOVE_ORAL_PLUS = 'p'
    FINISH_ORAL_ROUND = 'f'
    STUDENT_SELECTED = 's'


# ТИПЫ ЗАДАЧ
@unique
class PROB_TYPE(IntEnum):
    TEST = 1
    WRITTEN = 2
    ORALLY = 3
    WRITTEN_BEFORE_ORALLY = 4


PROB_TYPES_DECODER = {
    "Тест": PROB_TYPE.TEST,
    "Письменно": PROB_TYPE.WRITTEN,
    "Письменно<-Устно": PROB_TYPE.WRITTEN_BEFORE_ORALLY,
    "Устно": PROB_TYPE.ORALLY,
}


# ТИПЫ ПОЛЬЗОВАТЕЛЕЙ
@unique
class USER_TYPE(IntEnum):
    STUDENT = 1
    TEACHER = 2


@unique
class LEVEL(Enum):
    NOVICE = 'н'
    PRO = 'п'


# ВИДЫ ОТВЕТА НА ТЕСТОВЫЕ ЗАДАЧИ
@unique
class ANS_TYPE(IntEnum):
    DIGIT = 1  # Цифра
    NATURAL = 2  # Натуральное
    INTEGER = 3  # Целое
    RATIO = 4  # Отношение
    FLOAT = 5  # Действительное
    FRACTION = 6  # Дроль
    INT_SEQ = 7  # Последовательность целых
    INT_2 = 8  # Два целых
    INT_3 = 9  # Три целых
    INT_4 = 10  # Четыре целых
    SELECT_ONE = 98  # Выбрать один из вариантов
    STRING = 99  # Просто какая-то строка

ANS_TYPES_DECODER = {
    'Цифра': ANS_TYPE.DIGIT,
    'Натуральное': ANS_TYPE.NATURAL,
    'Целое': ANS_TYPE.INTEGER,
    'Отношение': ANS_TYPE.RATIO,
    'Действительное': ANS_TYPE.FLOAT,
    'Дробь': ANS_TYPE.FRACTION,
    'ПоследЦелых': ANS_TYPE.INT_SEQ,
    'ДваЦелых': ANS_TYPE.INT_2,
    'ТриЦелых': ANS_TYPE.INT_3,
    'ЧетыреЦелых': ANS_TYPE.INT_4,
    'Выбор': ANS_TYPE.SELECT_ONE,
    'Строка': ANS_TYPE.STRING,
}
ANS_HELP_DESCRIPTIONS = {
    ANS_TYPE.NATURAL: ' — натуральное число (например, 179)',
    ANS_TYPE.INTEGER: ' — целое число (например, -179)',
    ANS_TYPE.FRACTION: ' — обыкновенную дробь (например, 2/3 или 179)',
    ANS_TYPE.FLOAT: ' — действительное число (например, 3.14 или 179)',
    ANS_TYPE.SELECT_ONE: ' — выбери один из следующих вариантов:',
    ANS_TYPE.STRING: '',
}


# ВЕРДИКТЫ
@unique
class VERDICT(IntEnum):
    SOLVED = 1
    WRONG_ANSWER = -1


# СТАТУСЫ ПРОВЕРКИ ЗАДАНИЯ
@unique
class WRITTEN_STATUS(IntEnum):
    NEW = 0
    BEING_CHECKED = 1


# ТИПЫ ПРИНЯТЫХ ЗАДАЧ
@unique
class RES_TYPE(IntEnum):
    TEST = 1
    WRITTEN = 2
    ZOOM = 3
    SCHOOL = 4

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
# (наследование от str важно, чтобы условный CALLBACK.PROBLEM_SELECTED превращался в t, а не в своё длинное имя
@unique
class CALLBACK(str, Enum):
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
    "Тест": PROB_TYPE.TEST.value,
    "Письменно": PROB_TYPE.WRITTEN.value,
    "Письменно<-Устно": PROB_TYPE.WRITTEN_BEFORE_ORALLY.value,
    "Устно": PROB_TYPE.ORALLY.value,
}


# ТИПЫ ПОЛЬЗОВАТЕЛЕЙ
@unique
class USER_TYPE(IntEnum):
    STUDENT = 1
    TEACHER = 2


@unique
class LEVEL(str, Enum):
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
    FRACTION = 6  # Дробь
    INT_SEQ = 7  # Последовательность целых
    INT_2 = 8  # Два целых
    INT_3 = 9  # Три целых
    INT_4 = 10  # Четыре целых
    INT_SET = 11  # Множество целых чисел
    SELECT_ONE = 98  # Выбрать один из вариантов
    STRING = 99  # Просто какая-то строка


ANS_TYPES_DECODER = {
    'Цифра': ANS_TYPE.DIGIT.value,
    'Натуральное': ANS_TYPE.NATURAL.value,
    'Целое': ANS_TYPE.INTEGER.value,
    'Отношение': ANS_TYPE.RATIO.value,
    'Действительное': ANS_TYPE.FLOAT.value,
    'Дробь': ANS_TYPE.FRACTION.value,
    'ПоследЦелых': ANS_TYPE.INT_SEQ.value,
    'МножЦелых': ANS_TYPE.INT_SET.value,
    'ДваЦелых': ANS_TYPE.INT_2.value,
    'ТриЦелых': ANS_TYPE.INT_3.value,
    'ЧетыреЦелых': ANS_TYPE.INT_4.value,
    'Выбор': ANS_TYPE.SELECT_ONE.value,
    'Строка': ANS_TYPE.STRING.value,
}
ANS_HELP_DESCRIPTIONS = {
    ANS_TYPE.DIGIT.value: ' — цифру (например, 0 или 7)',
    ANS_TYPE.NATURAL.value: ' — натуральное число (например, 179)',
    ANS_TYPE.INTEGER.value: ' — целое число (например, -179)',
    ANS_TYPE.RATIO.value: ' — отношение (например, 5/3 или -179/1)',
    ANS_TYPE.FLOAT.value: ' — десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FRACTION.value: ' — обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)',
    ANS_TYPE.INT_SEQ.value: ' — последовательность целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_SET.value: ' — множество целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_2.value: ' — два целых числа (например: 1, 7)',
    ANS_TYPE.INT_3.value: ' — три целых числа (например: 1, 7, 9)',
    ANS_TYPE.INT_4.value: ' — четыре целых числа (например: 0, 1, 7, 9)',
    ANS_TYPE.SELECT_ONE.value: ' — выберите один из следующих вариантов:',
    ANS_TYPE.STRING.value: '',
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

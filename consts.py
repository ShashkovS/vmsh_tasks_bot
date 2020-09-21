# -*- coding: utf-8 -*-
# СОСТОЯНИЯ
# Важно, чтобы каждый state был уникальной числовой константой, которая больше никогда не меняется
# (так как она сохраняется в БД)
STATE_GET_USER_INFO = 1
STATE_GET_TASK_INFO = 2
STATE_SENDING_SOLUTION = 3
STATE_SENDING_TEST_ANSWER = 4
STATE_WAIT_SOS_REQUEST = 5
STATE_TEACHER_SELECT_ACTION = 6
STATE_TEACHER_ACCEPTED_QUEUE = 7
STATE_TEACHER_IS_CHECKING_TASK = 8


# ПРЕФИКСЫ ДАННЫХ ДЛЯ КОЛЛБЕКОВ
# Важно, чтобы константа была уникальной буков (там хардкод взятия первой буквы)
CALLBACK_PROBLEM_SELECTED = 't'
CALLBACK_SHOW_LIST_OF_LISTS = 'a'
CALLBACK_LIST_SELECTED = 'l'
CALLBACK_ONE_OF_TEST_ANSWER_SELECTED = 'x'
CALLBACK_CANCEL_TASK_SUBMISSION = 'c'
CALLBACK_GET_QUEUE_TOP = 'q'
CALLBACK_SET_VERDICT = 'v'
CALLBACK_GET_WRITTEN_TASK = 'w'
CALLBACK_WRITTEN_TASK_SELECTED = 'W'
CALLBACK_TEACHER_CANCEL = 'R'
CALLBACK_WRITTEN_TASK_OK = 'O'
CALLBACK_WRITTEN_TASK_BAD = 'B'


# ТИПЫ ЗАДАЧ
PROB_TYPE_TEST = 1
PROB_TYPE_WRITTEN = 2
PROB_TYPE_ORALLY = 3

PROB_TYPES = {
    "Тест": PROB_TYPE_TEST,
    "Письменно": PROB_TYPE_WRITTEN,
    "Устно": PROB_TYPE_ORALLY,
}


# ТИПЫ ПОЛЬЗОВАТЕЛЕЙ
USER_TYPE_STUDENT = 1
USER_TYPE_TEACHER = 2


# ВИДЫ ОТВЕТА НА ТЕСТОВЫЕ ЗАДАЧИ
ANS_TYPE_NATURAL = 1  # Натуральное число
ANS_TYPE_INTEGER = 2  # Целое число
ANS_TYPE_FRACTION = 3  # Обыкновенная дробь (3/4, 4/4, 4)
ANS_TYPE_FLOAT = 4  # Десятичное с точностью проверки 0.01 (типа 32.73)
ANS_TYPE_SELECT_ONE = 5  # Выбрать один из вариантов
ANS_TYPE_STRING = 6  # Просто какая-то строка
ANS_TYPES = {
    'Натуральное': ANS_TYPE_NATURAL,
    'Целое': ANS_TYPE_INTEGER,
    'Дробь': ANS_TYPE_FRACTION,
    'Действительное': ANS_TYPE_FLOAT,
    'Выбор': ANS_TYPE_SELECT_ONE,
    'Строка': ANS_TYPE_STRING,
}
ANS_HELP_DESCRIPTIONS = {
    ANS_TYPE_NATURAL: ' — натуральное число (например, 179)',
    ANS_TYPE_INTEGER: ' — целое число (например, -179)',
    ANS_TYPE_FRACTION: ' — обыкновенную дробь (например, 2/3 или 179)',
    ANS_TYPE_FLOAT: ' — действительное число (например, 3.14 или 179)',
    ANS_TYPE_SELECT_ONE: ' — выбери один из следующих вариантов:',
    ANS_TYPE_STRING: '',
}


# ВЕРДИКТЫ
VERDICT_SOLVED = 1
VERDICT_WRONG_ANSWER = -1


# СТАТУСЫ ПРОВЕРКИ ЗАДАНИЯ
WRITTEN_STATUS_NEW = 0
WRITTEN_STATUS_BEING_CHECKED = 1
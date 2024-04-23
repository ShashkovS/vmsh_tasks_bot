# -*- coding: utf-8 -*-
from enum import Enum, IntEnum, IntFlag, unique


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
    USER_IS_NOT_ACTIVATED = -2


# ПРЕФИКСЫ ДАННЫХ ДЛЯ КОЛЛБЕКОВ
# Важно, чтобы константа была уникальной буквой (там хардкод взятия первой буквы)
# (наследование от str важно, чтобы условный CALLBACK.PROBLEM_SELECTED превращался в t, а не в своё длинное имя
@unique
class CALLBACK(str, Enum):
    PROBLEM_SELECTED = 't'
    SOS_PROBLEM_SELECTED = 'T'
    SHOW_LIST_OF_LISTS = 'a'
    LIST_SELECTED = 'l'
    ONE_OF_TEST_ANSWER_SELECTED = 'x'
    CANCEL_TASK_SUBMISSION = 'c'
    GET_QUEUE_TOP = 'q'
    INS_ORAL_PLUSSES = 'i'
    SET_VERDICT = 'v'
    GET_SOS_TASK = 'w'
    WRITTEN_TASK_SELECTED = 'W'
    SELECT_WRITTEN_TASK_TO_CHECK = 'P'
    CHECK_ONLY_SELECTED_WRITEN_TASK = 'H'
    TEACHER_CANCEL = 'R'
    WRITTEN_TASK_OK = 'O'
    WRITTEN_TASK_BAD = 'B'
    GET_OUT_OF_WAITLIST = 'X'
    ADD_OR_REMOVE_ORAL_PLUS = 'p'
    FINISH_ORAL_ROUND = 'f'
    STUDENT_SELECTED = 's'
    CHANGE_LEVEL = 'L'
    PROBLEM_SOS = 'A'
    OTHER_SOS = 'C'
    SEND_ANSWER = 'h'
    REACTION = 'r'

    def __str__(self):
        return self.value


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
class USER_TYPE(IntFlag):
    STUDENT = 1
    TEACHER = 2
    ADMIN = 128
    TEACHER_OR_ADMIN = TEACHER | ADMIN
    DELETED = -1
    DEACTIVATED_STUDENT = -2


LEVEL_DESCRIPTION = {'н': 'Начинающие', 'п': 'Продолжающие', 'э': 'Эксперты'}
LEVEL_URL = {
    'н': 'https://shashkovs.ru/vmsh/2023/n/',
    'п': 'https://shashkovs.ru/vmsh/2023/p/',
    'э': 'https://shashkovs.ru/vmsh/2023/x/',
}


@unique
class LEVEL(str, Enum):
    NOVICE = 'н'
    PRO = 'п'
    EXPERT = 'э'
    GR8 = 'В'

    def __init__(self, value):
        self.slevel = LEVEL_DESCRIPTION.get(self.value, None)
        self.url = LEVEL_URL.get(self.value, None)

    def __str__(self):
        return self.value


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
    POLYNOMIAL = 12  # Многочлен
    FLOAT_EPS = 13  # Действительное с указанием точности
    TIME = 14  # Время
    DATE = 15  # Дата
    WEEKDAY = 16  # День недели
    FRAC_SEQ = 17  # Последовательность дробей
    MULTISET = 18  # Мультимножество
    SELECT_ONE = 98  # Выбрать один из вариантов
    STRING = 99  # Просто какая-то строка

    def __init__(self, value):
        self.descr = None


# ANS_HELP_DESCRIPTIONS
for ans_type, descr in [
    (ANS_TYPE.DIGIT, ' — цифру (например, 0 или 7)'),
    (ANS_TYPE.NATURAL, ' — натуральное число (например, 179)'),
    (ANS_TYPE.INTEGER, ' — целое число (например, -179)'),
    (ANS_TYPE.RATIO, ' — отношение (например, 5/3 или -179/1)'),
    (ANS_TYPE.FLOAT, ' — десятичную дробь (например, 3.14 или 179)'),
    (ANS_TYPE.FRACTION, ' — обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)'),
    (ANS_TYPE.INT_SEQ, ' — последовательность целых чисел (например: 1, 7, 9)'),
    (ANS_TYPE.INT_SET, ' — множество целых чисел (например: 1, 7, 9)'),
    (ANS_TYPE.INT_2, ' — два целых числа (например: 1, 7)'),
    (ANS_TYPE.INT_3, ' — три целых числа (например: 1, 7, 9)'),
    (ANS_TYPE.INT_4, ' — четыре целых числа (например: 0, 1, 7, 9)'),
    (ANS_TYPE.SELECT_ONE, ' — выберите один из следующих вариантов:'),
    (ANS_TYPE.POLYNOMIAL, ' — выражение от n (например: 2n**2 + n(n+1)/2):'),
    (ANS_TYPE.FLOAT_EPS, ' — десятичную дробь (например, 3.14 или 179)'),
    (ANS_TYPE.TIME, '— время (например, 12:08, 3:15:24)'),
    (ANS_TYPE.DATE, '— дату (например, 31.12, 2024-02-16, 11.02.1986)'),
    (ANS_TYPE.WEEKDAY, '— день недели (например, Суббота)'),
    (ANS_TYPE.FRAC_SEQ, '— последовательность дробей (например, 2/5,3.75, -1)'),
    (ANS_TYPE.MULTISET, '— мультимножество (например, 1, 1, 2, 5, 7, 2/5, 2/5, -1.2, -1.2)'),
    (ANS_TYPE.STRING, ''),
]:
    ans_type.descr = descr

ANS_TYPES_DECODER = {
    'Цифра': ANS_TYPE.DIGIT,
    'Натуральное': ANS_TYPE.NATURAL,
    'Целое': ANS_TYPE.INTEGER,
    'Отношение': ANS_TYPE.RATIO,
    'Действительное': ANS_TYPE.FLOAT,
    'Дробь': ANS_TYPE.FRACTION,
    'ПоследЦелых': ANS_TYPE.INT_SEQ,
    'МножЦелых': ANS_TYPE.INT_SET,
    'ДваЦелых': ANS_TYPE.INT_2,
    'ТриЦелых': ANS_TYPE.INT_3,
    'ЧетыреЦелых': ANS_TYPE.INT_4,
    'Выбор': ANS_TYPE.SELECT_ONE,
    'Многочлен': ANS_TYPE.POLYNOMIAL,
    'Строка': ANS_TYPE.STRING,
    'ЧислоТочность': ANS_TYPE.FLOAT_EPS,
    'Время': ANS_TYPE.TIME,
    'Дата': ANS_TYPE.DATE,
    'ДеньНедели': ANS_TYPE.WEEKDAY,
    'ПоследДробей': ANS_TYPE.FRAC_SEQ,
    'МультиМнож': ANS_TYPE.MULTISET,
}


# ВЕРДИКТЫ
# Важно, что чем больше вердикт как число, тем выше оценка
@unique
class VERDICT(IntEnum):
    NO_ANSWER = -32768
    REJECTED_ANSWER = -2
    WRONG_ANSWER = -1
    VERDICT_MINUS = 11
    VERDICT_MINUS_DOT = 12
    VERDICT_MINUS_PLUS = 13
    VERDICT_PLUS_DIV_2 = 14
    VERDICT_PLUS_MINUS = 15
    VERDICT_PLUS_DOT = 16
    VERDICT_PLUS = 17
    OLD_SOLVED = 1
    SOLVED = 18


VERDICT_DECODER = {
    VERDICT.NO_ANSWER: '',
    VERDICT.REJECTED_ANSWER: '?->−',
    VERDICT.WRONG_ANSWER: '−',
    VERDICT.VERDICT_MINUS: '−',
    VERDICT.VERDICT_MINUS_DOT: '−.',
    VERDICT.VERDICT_MINUS_PLUS: '∓',
    VERDICT.VERDICT_PLUS_DIV_2: '⨧',
    VERDICT.VERDICT_PLUS_MINUS: '±',
    VERDICT.VERDICT_PLUS_DOT: '+.',
    VERDICT.VERDICT_PLUS: '+',
    VERDICT.OLD_SOLVED: '+',
    VERDICT.SOLVED: '+',
}

VERDICT_TO_TICK = {
    VERDICT.NO_ANSWER: '⬜',
    VERDICT.REJECTED_ANSWER: '🟥−',
    VERDICT.WRONG_ANSWER: '🟥−',
    VERDICT.VERDICT_MINUS: '🟥−',
    VERDICT.VERDICT_MINUS_DOT: '🟥−.',
    VERDICT.VERDICT_MINUS_PLUS: '🟥∓',
    VERDICT.VERDICT_PLUS_DIV_2: '🟧+∕2',
    VERDICT.VERDICT_PLUS_MINUS: '🟨±',
    VERDICT.VERDICT_PLUS_DOT: '✅+.',
    VERDICT.VERDICT_PLUS: '✅+',
    VERDICT.OLD_SOLVED: '✅+',
    VERDICT.SOLVED: '✅+',
}

VERDICT_TO_NUM = {
    VERDICT.NO_ANSWER: 0.0,
    VERDICT.REJECTED_ANSWER: 0.0,
    VERDICT.WRONG_ANSWER: 0.0,
    VERDICT.VERDICT_MINUS: 0.0,
    VERDICT.VERDICT_MINUS_DOT: 0.05,
    VERDICT.VERDICT_MINUS_PLUS: 0.25,
    VERDICT.VERDICT_PLUS_DIV_2: 0.5,
    VERDICT.VERDICT_PLUS_MINUS: 0.7,
    VERDICT.VERDICT_PLUS_DOT: 0.95,
    VERDICT.VERDICT_PLUS: 1.0,
    VERDICT.OLD_SOLVED: 1.0,
    VERDICT.SOLVED: 1.0,
}

VERDICTS_SOLVED = {
    VERDICT.SOLVED,
    VERDICT.OLD_SOLVED,
    VERDICT.VERDICT_PLUS,
    VERDICT.VERDICT_PLUS_DOT,
}


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


# Режим работы
@unique
class ONLINE_MODE(IntEnum):
    ONLINE = 1
    SCHOOL = 2


ONLINE_MODE_DECODER = {
    'онлайн': ONLINE_MODE.ONLINE,
    'в школе': ONLINE_MODE.SCHOOL,
    'online': ONLINE_MODE.ONLINE,
    'school': ONLINE_MODE.SCHOOL,
}


# Тип изменения в параметрах юзера
@unique
class CHANGE(str, Enum):
    LEVEL = 'L'
    ONLINE = 'O'


# Константы для имён topic'ов в nats
NATS_GAME_MAP_UPDATE = 'map_upd'
NATS_GAME_STUDENT_UPDATE = 'stud_upd'


@unique
class REACTION(IntEnum):
    """ Реакции учителя и ученика на письменную и устную сдачу задач.
    Смотри также отношение `reaction_type_enum` в БД.
    """
    WRITTEN_STUDENT = 0
    WRITTEN_TEACHER = 100
    ORAL_STUDENT = 200
    ORAL_TEACHER = 300

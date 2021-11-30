from fractions import Fraction
import re
from helpers.consts import ANS_TYPE
from helpers.calc_ans_func_values import calc_first_10_values

__ALL__ = ['ANS_CHECKER']

no_space = re.compile(r'\s+')


class Ne:
    def __eq__(self, other):
        return False

    def __repr__(self):
        return '≠'


ne = Ne()


def to_int(x):
    try:
        return int(no_space.sub('', x))
    except:
        return ne


def to_frac(x):
    try:
        return Fraction(no_space.sub('', x))
    except:
        return ne


def to_int_seq(x):
    try:
        return list(map(int, re.findall(r'[-+]*\d+', x)))
    except:
        return ne


def to_int_set(x):
    try:
        return set(map(int, re.findall(r'[-+]?\d+', x)))
    except:
        return ne


def int_eq(x, y):
    return to_int(x) == to_int(y)


def frac_eq(x, y):
    return to_frac(x) == to_frac(y)


def int_sec_eq(x, y):
    return to_int_seq(x) == to_int_seq(y)


def int_set_eq(x, y):
    return to_int_set(x) == to_int_set(y)


RU_TO_EN = str.maketrans('УКЕНХВАРОСМТукехарос', 'YKEHXBAPOCMTykexapoc')


def str_eq(x, y):
    return x.strip().translate(RU_TO_EN).lower() == y.strip().translate(RU_TO_EN).lower()


ANS_CHECKER = {
    ANS_TYPE.DIGIT: int_eq,  # цифру (например, 0 или 7)',
    ANS_TYPE.NATURAL: int_eq,  # натуральное число (например, 179)',
    ANS_TYPE.INTEGER: int_eq,  # целое число (например, -179)',
    ANS_TYPE.RATIO: frac_eq,  # отношение (например, 5/3 или -179/1)',
    ANS_TYPE.FLOAT: frac_eq,  # десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FRACTION: frac_eq,  # обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)',
    ANS_TYPE.INT_SEQ: int_sec_eq,  # последовательность целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_SET: int_set_eq,  # множество целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_2: int_sec_eq,  # два целых числа (например: 1, 7)',
    ANS_TYPE.INT_3: int_sec_eq,  # три целых числа (например: 1, 7, 9)',
    ANS_TYPE.INT_4: int_sec_eq,  # четыре целых числа (например: 0, 1, 7, 9)',
    ANS_TYPE.SELECT_ONE: str_eq,  # выберите один из следующих вариантов:',
    ANS_TYPE.POLYNOMIAL: calc_first_10_values,  # выражение от n (например: 2n**2 + n(n+1)/2)',
    ANS_TYPE.STRING: str_eq,  # строка
}
ANS_REGEX = {
    ANS_TYPE.DIGIT: re.compile(r'^\s*\d\s*$'),  # цифру (например, 0 или 7)',
    ANS_TYPE.NATURAL: re.compile(r'^\s*\d+\s*$'),  # натуральное число (например, 179)',
    ANS_TYPE.INTEGER: re.compile(r'^\s*[-+]?\d+\s*$'),  # целое число (например, -179)',
    ANS_TYPE.RATIO: re.compile(r'^\s*[-+]?\d+(?:\/\d+)?\s*$'),  # отношение (например, 5/3 или -179/1)',
    ANS_TYPE.FLOAT: re.compile(r'^\s*[-+]?(?=\d|\.\d)\d*(?:\.\d*)?(?:[eE][-+]?\d+)?\s*$'),  # десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FRACTION: re.compile(r'^\s*[-+]?(?=\d+|\.\d+)\d*(?:(?:/\d+)?|(?:\.\d*)?(?:[eE][-+]?\d+)?)\s*$'),  # обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)',
    ANS_TYPE.INT_SEQ: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+)*[^\d+-]*$'),  # последовательность целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_SET: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+)*[^\d+-]*$'),  # множество целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_2: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){1}[^\d+-]*$'),  # два целых числа (например: 1, 7)',
    ANS_TYPE.INT_3: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){2}[^\d+-]*$'),  # три целых числа (например: 1, 7, 9)',
    ANS_TYPE.INT_4: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){3}[^\d+-]*$'),  # четыре целых числа (например: 0, 1, 7, 9)',
    ANS_TYPE.POLYNOMIAL: re.compile(r'^[ \d+\-*/()nkijm^]+$'),  # выражение от n (например: 2n**2 + n(n+1)/2)',
    ANS_TYPE.SELECT_ONE: None,  # выберите один из следующих вариантов:',
    ANS_TYPE.STRING: None,  # строка
}

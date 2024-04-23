from fractions import Fraction
import re
from collections import Counter
from helpers.consts import ANS_TYPE
from helpers.calc_ans_func_values import calc_first_10_values

__ALL__ = ['ANS_CHECKER']

no_space = re.compile(r'\s+')
frac = re.compile(r'(?:[-+]?(?=\d|\.\d)\d*(?:/\d+|(?:\.\d*)?(?:[eE][-+]?\d+)?|))')
weekday = re.compile(r'.*(?:(п.?н)|(вт)|(ср)|(ч.?т)|(п.?т)|(с.?б)|(в.?с)).*', flags=re.IGNORECASE)


class Ne:
    def __eq__(self, other):
        return False

    def __le__(self, other):
        return False

    def __ge__(self, other):
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


def to_frac_seq(x):
    try:
        return list(map(Fraction, frac.findall(x)))
    except:
        return ne


def to_frac_multiset(x):
    try:
        return Counter(map(Fraction, frac.findall(x)))
    except:
        return ne


def to_weekday(x):
    try:
        return max(range(7), key=lambda i: weekday.search(x).groups()[i] or '')
    except:
        return ne


def to_time(x):
    try:
        nums = re.findall(r'\d+', x)
        if not 1 <= len(nums) <= 3:
            return ne
        return (list(map(int, nums)) + [0, 0])[:3]
    except:
        return ne


def to_date(x):
    try:
        nums = re.findall(r'\d+', x)
        if not 2 <= len(nums) <= 3:
            return ne
        nums = list(map(int, nums))
        if len(nums) == 2:
            return nums  # dd.mm
        if nums[0] > 31:  # y.m.d
            return nums[::-1]
        return nums
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


def close_to(x, y):
    x_float = to_frac(x)
    # y — это выражение вида 14.3+-0.4 — то есть число плюс-минус точность
    y = y.replace('+-', '±').replace('-+', '±')
    if '±' not in y:
        return x_float == to_frac(y)
    try:
        y, eps = y.split('±')
        y = float(y)
        eps = float(eps)
        return y - eps - eps / 1e6 <= x_float <= y + eps + eps / 1e6  # Добавка 1e6 для того, чтобы 0.3±0.1 нормально работало с 0.2 и 0.4
    except:
        return False


def int_sec_eq(x, y):
    return to_int_seq(x) == to_int_seq(y)


def int_set_eq(x, y):
    return to_int_set(x) == to_int_set(y)


def frac_seq_eq(x, y):
    return to_frac_seq(x) == to_frac_seq(y)


def frac_multiset_eq(x, y):
    return to_frac_multiset(x) == to_frac_multiset(y)


def time_eq(x, y):
    return to_time(x) == to_time(y)


def date_eq(x, y):
    return to_date(x) == to_date(y)


def weekday_eq(x, y):
    return to_weekday(x) == to_weekday(y)


RU_TO_EN = str.maketrans('УКЕНХВАРОСМТукехаросЁё', 'YKEHXBAPOCMTykexapocEe')


def str_eq(x, y):
    return x.strip().translate(RU_TO_EN).lower() == y.strip().translate(RU_TO_EN).lower()


ANS_CHECKER = {
    ANS_TYPE.DIGIT: int_eq,  # цифру (например, 0 или 7)',
    ANS_TYPE.NATURAL: int_eq,  # натуральное число (например, 179)',
    ANS_TYPE.INTEGER: int_eq,  # целое число (например, -179)',
    ANS_TYPE.RATIO: frac_eq,  # отношение (например, 5/3 или -179/1)',
    ANS_TYPE.FLOAT: frac_eq,  # десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FLOAT_EPS: close_to,  # десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FRACTION: frac_eq,  # обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)',
    ANS_TYPE.INT_SEQ: int_sec_eq,  # последовательность целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_SET: int_set_eq,  # множество целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_2: int_sec_eq,  # два целых числа (например: 1, 7)',
    ANS_TYPE.INT_3: int_sec_eq,  # три целых числа (например: 1, 7, 9)',
    ANS_TYPE.INT_4: int_sec_eq,  # четыре целых числа (например: 0, 1, 7, 9)',
    ANS_TYPE.SELECT_ONE: str_eq,  # выберите один из следующих вариантов:',
    ANS_TYPE.POLYNOMIAL: calc_first_10_values,  # выражение от n (например: 2n**2 + n(n+1)/2)',
    ANS_TYPE.TIME: time_eq,  # время (например, 12:08, 3:15:24)'),
    ANS_TYPE.DATE: date_eq,  # дату (например, 31.12, 2024-02-16, 11.02.1986)'),
    ANS_TYPE.WEEKDAY: weekday_eq,  # день недели (например, Суббота)'),
    ANS_TYPE.FRAC_SEQ: frac_seq_eq,  # последовательность дробей (например, 2/5,3.75, -1)'),
    ANS_TYPE.MULTISET: frac_multiset_eq,  # мультимножество (например, 1, 1, 2, 5, 7, 2/5, 2/5, -1.2, -1.2)'),
    ANS_TYPE.STRING: str_eq,  # строка
}


# используется fullmatch, применяется к student_answer.strip()
ANS_REGEX = {
    ANS_TYPE.DIGIT: re.compile(r'\d'),  # цифру (например, 0 или 7)',
    ANS_TYPE.NATURAL: re.compile(r'\d+'),  # натуральное число (например, 179)',
    ANS_TYPE.INTEGER: re.compile(r'[-+]?\d+'),  # целое число (например, -179)',
    ANS_TYPE.RATIO: re.compile(r'[-+]?\d+(?:\/\d+)?'),  # отношение (например, 5/3 или -179/1)',
    ANS_TYPE.FLOAT: frac,  # десятичную дробь (например, 3.14 или 179)',
    ANS_TYPE.FLOAT_EPS: frac,  # десятичную дробь (например, 3.14 или 179)',
    # обыкновенную или десятичную дробь (например, 7/3, -3.14 или 179)',
    ANS_TYPE.FRACTION: re.compile(r'[-+]?(?=\d+|\.\d+)\d*(?:(?:/\d+)?|(?:\.\d*)?(?:[eE][-+]?\d+)?)'),
    ANS_TYPE.INT_SEQ: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+)*[^\d+-]*$'),  # последовательность целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_SET: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+)*[^\d+-]*$'),  # множество целых чисел (например: 1, 7, 9)',
    ANS_TYPE.INT_2: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){1}[^\d+-]*$'),  # два целых числа (например: 1, 7)',
    ANS_TYPE.INT_3: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){2}[^\d+-]*$'),  # три целых числа (например: 1, 7, 9)',
    ANS_TYPE.INT_4: re.compile(r'^[^\d+-]*[-+]?\d+(?:[^\d+-]+[-+]?\d+){3}[^\d+-]*$'),  # четыре целых числа (например: 0, 1, 7, 9)',
    ANS_TYPE.POLYNOMIAL: re.compile(r'^[ \d+\-*/()nkijm^]+$'),  # выражение от n (например: 2n**2 + n(n+1)/2)',
    ANS_TYPE.TIME: re.compile(r'\d{1,2}(?:\D{1,2}\d{1,2}){1,2}'),  # время (например, 12:08, 3:15:24)'),
    ANS_TYPE.DATE: re.compile(r'\d{1,4}(?:\D{1,2}\d{1,4}){1,2}'),  # дату (например, 31.12, 2024-02-16, 11.02.1986)'),
    ANS_TYPE.WEEKDAY: re.compile(r'(?:п.?н|вт|ср|ч.?т|п.?т|с.?б|в.?с).*$', flags=re.IGNORECASE),
    # день недели (например, Суббота)'),
    ANS_TYPE.FRAC_SEQ: re.compile(
        r'^(?:[^0-9eE.+/-]*(?:[-+]?(?=\d|\.\d)\d*(?:/\d+|(?:\.\d*)?(?:[eE][-+]?\d+)?|))[^0-9eE.+/-]*)+$'),
    # последовательность дробей (например, 2/5,3.75, -1)'),
    ANS_TYPE.MULTISET: re.compile(
        r'^(?:[^0-9eE.+/-]*(?:[-+]?(?=\d|\.\d)\d*(?:/\d+|(?:\.\d*)?(?:[eE][-+]?\d+)?|))[^0-9eE.+/-]*)+$'),
    # мультимножество (например, 1, 1, 2, 5, 7, 2/5, 2/5, -1.2, -1.2)'),
    ANS_TYPE.SELECT_ONE: None,  # выберите один из следующих вариантов:',
    ANS_TYPE.STRING: None,  # строка
}

import re
from typing import Tuple, Union

VALID_ONE_PARM_FUNC = re.compile(r'[ \d+\-*/()nkijm^]+')
VALID_VARS = re.compile(r'[nkijm]')
INSERT_LOST_MUL = re.compile(r'(?<=[)n\d])(?=[(n])|(?<=[)n])(?=[(\dn])')
BAD_EXPONENT = re.compile(r'\*\*\s*(?:\D|\d\d)')
RUN_ON = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def run_expr_on(expr: str, vals: list):
    code = compile(expr, "<string>", "eval")
    result = [eval(code, {"__builtins__": {}}, {'n': v}) for v in vals]
    return result


def calc_first_10_values(expr: str) -> Tuple[bool, Union[str, list[float]]]:
    if len(expr) > 50:
        return False, f'Выражение слишком длинное'
    if wrong := VALID_ONE_PARM_FUNC.sub('', expr):
        return False, f'В выражении используются некорректные символы: {wrong}'
    expr = expr.replace('^', '**')
    if BAD_EXPONENT.search(expr):
        return False, f'Разрешается возводить в степень от 1 до 9'
    used_vars = set(VALID_VARS.findall(expr))
    if len(used_vars) > 1:
        return False, f'В выражении разрешается использовать только одну переменную, а здесь {", ".join(used_vars)}'
    expr = VALID_VARS.sub('n', expr)
    expr = INSERT_LOST_MUL.sub('*', expr)
    try:
        code = compile(expr, "<string>", "eval")
    except:
        return False, f'Некорректная формула: что-то не так со скобками или операциями'
    if code.co_names and code.co_names != ('n',):
        return False, f'Некорректная формула: что-то не так с используемой переменной'
    result = run_expr_on(expr, RUN_ON)
    return True, result

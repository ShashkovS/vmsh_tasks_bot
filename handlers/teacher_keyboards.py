from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from Levenshtein import jaro_winkler
from typing import List, Tuple

from helpers.consts import *
from helpers.config import logger
from helpers.msg_texts import msgs
import db_methods as db
from helpers.features import VERDICT_MODE, FEATURES
from models import User, Problem


def _get_student_groups(student: User, teacher: User = None):
    allowed_ids = set(student.allowed_groups_set or [])
    if student.group_id:
        allowed_ids.add(student.group_id)
    if teacher:
        teacher_ids = teacher.accessible_group_ids()
        if teacher_ids:
            allowed_ids &= teacher_ids
    if not allowed_ids:
        return []
    groups = [row for row in db.group.get_all() if row['group_id'] in allowed_ids]
    groups.sort(key=lambda row: (row.get('sort_order') or 0, row['group_id']))
    return groups


def build_teacher_actions(sos_count, prb_count):
    logger.debug('keyboards.build_teacher_actions')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    get_written_task_button = types.InlineKeyboardButton(
        text=msgs.t_btn_answer_question.format_map({'sos_count': sos_count}),
        callback_data=CALLBACK.GET_SOS_TASK
    )
    keyboard.add(get_written_task_button)
    get_written_task_button = types.InlineKeyboardButton(
        text=msgs.t_btn_check_written.format_map({'prb_count': prb_count}),
        callback_data=CALLBACK.SELECT_WRITTEN_TASK_TO_CHECK
    )
    keyboard.add(get_written_task_button)
    # get_queue_top_button = types.InlineKeyboardButton(
    #     text="Вызвать школьника на устную сдачу",
    #     callback_data=Callback.GET_QUEUE_TOP
    # )
    # keyboard.add(get_queue_top_button)
    insert_oral_pluses = types.InlineKeyboardButton(
        text=msgs.t_btn_insert_oral_pluses,
        callback_data=CALLBACK.INS_ORAL_PLUSSES
    )
    keyboard.add(insert_oral_pluses)
    return keyboard.as_markup()


def build_cancel_keyboard():
    logger.debug('build_cancel_keyboard')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    cancel = types.InlineKeyboardButton(
        text=msgs.t_btn_cancel,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard.add(cancel)
    return keyboard.as_markup()


def build_select_problem_to_check(problems_and_counts: List[Tuple[Problem, int, float]]):
    logger.debug('build_select_problem_to_check')
    # Сортировка уже в sql-запросе
    # problems_and_counts.sort(key=lambda el: (el[0].lesson, el[0].group_code, el[0].prob, el[0].item))
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    for problem, cnt, days_waits in problems_and_counts:
        if problem.prob_type == PROB_TYPE.TEST:
            tp = '⋯'
        elif problem.prob_type == PROB_TYPE.WRITTEN:
            tp = '🖊'
        elif problem.prob_type == PROB_TYPE.ORALLY or problem.prob_type == PROB_TYPE.WRITTEN_BEFORE_ORALLY:
            tp = '🗣'
        else:
            tp = '?'
        task_button = types.InlineKeyboardButton(
            text=f"{tp} {problem.str_num()} ({cnt}шт, {days_waits}дн)",
            callback_data=f"{CALLBACK.CHECK_ONLY_SELECTED_WRITEN_TASK}_{problem.id}"
        )
        keyboard.add(task_button)
    cancel = types.InlineKeyboardButton(
        text=msgs.t_btn_cancel,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard.add(cancel)
    return keyboard.as_markup()


def build_teacher_select_written_problem(top: list):
    logger.debug('keyboards.build_teacher_select_written_problem')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    for row in top:
        student = User.get_by_id(row['student_id'])
        problem = Problem.get_by_id(abs(row['problem_id']))  # убираем знак, он может быть отрицательным при вопросе
        task_button = types.InlineKeyboardButton(
            text=f"{problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title}) {student.surname} {student.name}",
            callback_data=f"{CALLBACK.WRITTEN_TASK_SELECTED}_{student.id}_{row['problem_id']}"
        )
        keyboard_markup.add(task_button)
    cancel = types.InlineKeyboardButton(
        text=msgs.t_btn_cancel,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup.as_markup()


def build_select_student(name_to_find: str, group_ids=None):
    logger.debug('keyboards.build_select_student')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    name_to_find_lower = name_to_find.lower()
    allowed = set(group_ids or [])
    all_students = User.all_students()
    if allowed:
        all_students = [student for student in all_students if student.group_id in allowed]
    students = sorted(
        all_students,
        key=lambda user: -jaro_winkler(name_to_find_lower, f'{user.surname} {user.name} {user.token}'.lower(), prefix_weight=1 / 32)
    )
    for student in students[:8]:
        student_button = types.InlineKeyboardButton(
            text=f"{student.surname} {student.name} {student.group_code} {student.token}",
            callback_data=f"{CALLBACK.STUDENT_SELECTED}_{student.id}"
        )
        keyboard_markup.add(student_button)
    cancel = types.InlineKeyboardButton(
        text=msgs.t_btn_cancel,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup.as_markup()


def build_written_task_checking_verdict(student: User, problem: Problem, wtd_ids_to_remove: List = None):
    logger.debug('keyboards.build_written_task_checking_verdict')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    # TODO сделать нормально
    if VERDICT_MODE == FEATURES.VERDICT_PLUS_MINUS:
        keyboard_markup.add(types.InlineKeyboardButton(
            text=msgs.t_btn_accept_task.format_map({
                'problem_str': f"{problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title})"
            }),
            callback_data=f"{CALLBACK.WRITTEN_TASK_OK}_{student.id}_{problem.id}_{VERDICT.SOLVED}"
        ))
        keyboard_markup.add(types.InlineKeyboardButton(
            text=msgs.t_btn_reject_task.format_map({
                'student_name': f"{student.surname} {student.name}"
            }),
            callback_data=f"{CALLBACK.WRITTEN_TASK_BAD}_{student.id}_{problem.id}_{VERDICT.WRONG_ANSWER}"
        ))
    else:
        for verdict in VERDICT_MODE.value:
            keyboard_markup.add(types.InlineKeyboardButton(
                text=msgs.t_btn_tick_task.format_map({
                    'verdict_tick': VERDICT_TO_TICK[verdict],
                    'problem_str': f"{problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title})",
                }),
                callback_data=f"{CALLBACK.WRITTEN_TASK_OK}_{student.id}_{problem.id}_{verdict}"
            ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=msgs.t_btn_refuse_checking,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}_del_{'' if not wtd_ids_to_remove else ','.join(map(str, wtd_ids_to_remove))}"
        # TODO А-а-а! ТРЕШНЯК!!!
    ))
    return keyboard_markup.as_markup()


def build_answer_verdict(student: User, problem: Problem, wtd_ids_to_remove: List = None):
    logger.debug('keyboards.build_answer_verdict')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    keyboard_markup.add(types.InlineKeyboardButton(
        text=msgs.t_btn_send_answer,
        callback_data=f"{CALLBACK.SEND_ANSWER}_{student.id}_{-problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=msgs.t_btn_skip_answer,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}_del_{'' if not wtd_ids_to_remove else ','.join(map(str, wtd_ids_to_remove))}"
        # TODO А-а-а! ТРЕШНЯК!!!
    ))
    return keyboard_markup.as_markup()


def build_verdict_for_oral_problems(
    plus_ids: set, minus_ids: set, student: User, online: ONLINE_MODE, lesson_num=None, teacher: User = None
):
    logger.debug('keyboards.build_verdict_for_oral_problems')
    if lesson_num is None:
        lesson_num = Problem.last_lesson_num(student.group_id)
    solved = {
        problem_id
        for (problem_id, verdict) in db.result.check_student_solved(
            student.id, lesson_num, group_id=student.group_id
        ).items()
        if verdict in VERDICTS_SOLVED
    }
    keyboard_markup = InlineKeyboardBuilder()
    plus_ids_str = ','.join(map(str, plus_ids))
    minus_ids_str = ','.join(map(str, minus_ids))
    if online == ONLINE_MODE.SCHOOL:
        select_problem_types = list(PROB_TYPE)  # В школе принимаем все задачи
    else:
        select_problem_types = (PROB_TYPE.ORALLY, PROB_TYPE.WRITTEN_BEFORE_ORALLY)  # Дистанционно — только устные
    use_problems = [problem for problem in Problem.get_by_lesson(student.group_id, lesson_num)
                    if problem.prob_type in select_problem_types]
    problem_buttons = []
    for problem in use_problems:
        if problem.synonyms_set() & solved and problem.id not in minus_ids:
            tick = '✅✅'
        elif problem.id in plus_ids:
            tick = '👍'
        elif problem.id in minus_ids:
            tick = '❌'
        else:
            tick = ''
        if online == ONLINE_MODE.SCHOOL:
            text = f"{tick} {problem.lesson}{problem.group_code}.{problem.prob}{problem.item}"
        else:
            text = f"{tick} {problem}"
        task_button = types.InlineKeyboardButton(
            text=text,
            callback_data=f"{CALLBACK.ADD_OR_REMOVE_ORAL_PLUS}_{problem.id}_{plus_ids_str}_{minus_ids_str}"
        )
        problem_buttons.append(task_button)
    if online == ONLINE_MODE.SCHOOL:
        for i in range(0, len(problem_buttons), 4):
            keyboard_markup.row(*problem_buttons[i:i + 4], width=4)
    else:
        keyboard_markup.row(*problem_buttons, width=3)
    row_btns = []
    groups = _get_student_groups(student, teacher=teacher)
    for group in groups:
        if group['group_id'] == student.group_id:
            continue
        row_btns.append(types.InlineKeyboardButton(
            text=msgs.t_btn_level_template.format_map({
                'short_code': group.get('short_code') or group['group_id'],
                'public_name': group.get('public_name') or group['group_id'],
            }),
            callback_data=f"{CALLBACK.CHANGE_GROUP}_{student.id}_{group['group_id']}"
        ))
    if row_btns:
        keyboard_markup.row(*row_btns, width=len(row_btns))
    ready_button = types.InlineKeyboardButton(
        text=msgs.t_btn_ready_oral,
        callback_data=f"{CALLBACK.FINISH_ORAL_ROUND}_{plus_ids_str}_{minus_ids_str}"
    )
    keyboard_markup.row(ready_button, width=1)
    cancel = types.InlineKeyboardButton(
        text=msgs.t_btn_cancel_oral,
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.row(cancel, width=1)
    return keyboard_markup.as_markup()


def build_teacher_reaction_on_solution(result_id: int):
    """Создает инлайн клавиатуру для учителя для оценки решения ученика
    после принятия/отклонения учителем письменной работы.
    """
    logger.debug('keyboards.build_teacher_reaction_on_solution')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    for reaction in db.reaction.enum(REACTION.WRITTEN_TEACHER):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_{result_id}_None_{reaction["reaction_id"]}_{REACTION.WRITTEN_TEACHER}'
            )
        )
    return keyboard.as_markup()


def build_teacher_reaction_oral(zoom_conversation_id: int):
    """Создает инлайн клавиатуру для учителя для оценки устной сдачи ученика."""
    logger.debug('keyboards.build_teacher_reaction_oral')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    for reaction in db.reaction.enum(REACTION.ORAL_TEACHER):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_None_{zoom_conversation_id}_{reaction["reaction_id"]}_{REACTION.ORAL_TEACHER}'
            )
        )
    return keyboard.as_markup()

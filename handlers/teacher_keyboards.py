from aiogram import types
from Levenshtein import jaro_winkler
from typing import List, Tuple

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, Problem, db


def build_teacher_actions():
    logger.debug('keyboards.build_teacher_actions')
    keyboard = types.InlineKeyboardMarkup()
    sos_count = db.get_sos_tasks_count()
    prb_count = db.get_written_tasks_count()
    get_written_task_button = types.InlineKeyboardButton(
        text=f"Ответить на вопрос (всего {sos_count})",
        callback_data=CALLBACK.GET_SOS_TASK
    )
    keyboard.add(get_written_task_button)
    get_written_task_button = types.InlineKeyboardButton(
        text=f"Проверять письменные (всего {prb_count})",
        callback_data=CALLBACK.SELECT_WRITTEN_TASK_TO_CHECK
    )
    keyboard.add(get_written_task_button)
    # get_queue_top_button = types.InlineKeyboardButton(
    #     text="Вызвать школьника на устную сдачу",
    #     callback_data=Callback.GET_QUEUE_TOP
    # )
    # keyboard.add(get_queue_top_button)
    insert_oral_pluses = types.InlineKeyboardButton(
        text="Внести плюсы за устную сдачу",
        callback_data=CALLBACK.INS_ORAL_PLUSSES
    )
    keyboard.add(insert_oral_pluses)
    return keyboard


def build_cancel_keyboard():
    logger.debug('build_cancel_keyboard')
    keyboard = types.InlineKeyboardMarkup()
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard.add(cancel)
    return keyboard


def build_select_problem_to_check(problems_and_counts: List[Tuple[Problem, int]]):
    logger.debug('build_select_problem_to_check')
    # Сортировка уже в sql-запросе
    # problems_and_counts.sort(key=lambda el: (el[0].lesson, el[0].level, el[0].prob, el[0].item))
    keyboard = types.InlineKeyboardMarkup()
    for problem, cnt in problems_and_counts:
        if problem.prob_type == PROB_TYPE.TEST:
            tp = '⋯'
        elif problem.prob_type == PROB_TYPE.WRITTEN or problem.prob_type == PROB_TYPE.WRITTEN_BEFORE_ORALLY:
            tp = '🖊'
        elif problem.prob_type == PROB_TYPE.ORALLY:
            tp = '🗣'
        else:
            tp = '?'
        task_button = types.InlineKeyboardButton(
            text=f"{tp} {problem} — {cnt}",
            callback_data=f"{CALLBACK.CHECK_ONLY_SELECTED_WRITEN_TASK}_{problem.id}"
        )
        keyboard.add(task_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard.add(cancel)
    return keyboard


def build_teacher_select_written_problem(top: list):
    logger.debug('keyboards.build_teacher_select_written_problem')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    for row in top:
        student = User.get_by_id(row['student_id'])
        problem = Problem.get_by_id(abs(row['problem_id']))  # убираем знак, он может быть отрицательным при вопросе
        task_button = types.InlineKeyboardButton(
            text=f"{problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) {student.surname} {student.name}",
            callback_data=f"{CALLBACK.WRITTEN_TASK_SELECTED}_{student.id}_{row['problem_id']}"
        )
        keyboard_markup.add(task_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup


def build_select_student(name_to_find: str):
    logger.debug('keyboards.build_select_student')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    students = sorted(
        User.all_students(),
        key=lambda user: -jaro_winkler(name_to_find.lower(), f'{user.surname} {user.name} {user.token}'.lower(), 1 / 10)
    )
    for student in students[:8]:
        student_button = types.InlineKeyboardButton(
            text=f"{student.surname} {student.name} {student.level} {student.token}",
            callback_data=f"{CALLBACK.STUDENT_SELECTED}_{student.id}"
        )
        keyboard_markup.add(student_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup


def build_written_task_checking_verdict(student: User, problem: Problem, wtd_ids_to_remove: List = None):
    logger.debug('keyboards.build_written_task_checking_verdict')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"👍 Засчитать задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})",
        callback_data=f"{CALLBACK.WRITTEN_TASK_OK}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отклонить и переслать все сообщения выше студенту {student.surname} {student.name}",
        callback_data=f"{CALLBACK.WRITTEN_TASK_BAD}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"Отказаться от проверки и вернуться назад",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}_del_{'' if not wtd_ids_to_remove else ','.join(map(str, wtd_ids_to_remove))}"
        # TODO А-а-а! ТРЕШНЯК!!!
    ))
    return keyboard_markup


def build_answer_verdict(student: User, problem: Problem, wtd_ids_to_remove: List = None):
    logger.debug('keyboards.build_answer_verdict')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"Отправить ответ на вопрос",
        callback_data=f"{CALLBACK.SEND_ANSWER}_{student.id}_{-problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"Не отвечать на вопрос и вернуться назад",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}_del_{'' if not wtd_ids_to_remove else ','.join(map(str, wtd_ids_to_remove))}"
        # TODO А-а-а! ТРЕШНЯК!!!
    ))
    return keyboard_markup


def build_verdict_for_oral_problems(plus_ids: set, minus_ids: set, student: User, online: ONLINE_MODE):
    logger.debug('keyboards.build_verdict_for_oral_problems')
    lesson_num = Problem.last_lesson_num(student.level)
    solved = set(db.check_student_solved(student.id, lesson_num))
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    plus_ids_str = ','.join(map(str, plus_ids))
    minus_ids_str = ','.join(map(str, minus_ids))
    if online == ONLINE_MODE.SCHOOL:
        select_problem_types = list(PROB_TYPE)  # В школе принимаем все задачи
    else:
        select_problem_types = (PROB_TYPE.ORALLY, PROB_TYPE.WRITTEN_BEFORE_ORALLY)  # Дистанционно — только устные
    use_problems = [problem for problem in Problem.get_by_lesson(student.level, lesson_num)
                    if problem.prob_type in select_problem_types]
    problem_buttons = []
    for problem in use_problems:
        if problem.synonyms & solved and problem.id not in minus_ids:
            tick = '✅✅'
        elif problem.id in plus_ids:
            tick = '👍'
        elif problem.id in minus_ids:
            tick = '❌'
        else:
            tick = ''
        if online == ONLINE_MODE.SCHOOL:
            text = f"{tick} {problem.lesson}{problem.level}.{problem.prob}{problem.item}"
        else:
            text = f"{tick} {problem}"
        task_button = types.InlineKeyboardButton(
            text=text,
            callback_data=f"{CALLBACK.ADD_OR_REMOVE_ORAL_PLUS}_{problem.id}_{plus_ids_str}_{minus_ids_str}"
        )
        problem_buttons.append(task_button)
    if online == ONLINE_MODE.SCHOOL:
        for i in range(0, len(problem_buttons), 4):
            keyboard_markup.row(*problem_buttons[i:i+4])
    else:
        for task_button in problem_buttons:
            keyboard_markup.add(task_button)
    row_btns = []
    for lvl in LEVEL:
        if student.level != lvl:
            row_btns.append(types.InlineKeyboardButton(text=f"Уровень: {lvl} «{lvl.slevel}»",
                                                       callback_data=f"{CALLBACK.CHANGE_LEVEL}_{student.id}_{lvl}"))
    keyboard_markup.row(*row_btns)
    ready_button = types.InlineKeyboardButton(
        text="Готово (завершить сдачу и внести в кондуит)",
        callback_data=f"{CALLBACK.FINISH_ORAL_ROUND}_{plus_ids_str}_{minus_ids_str}"
    )
    keyboard_markup.add(ready_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена (ничего не трогать и выйти)",
        callback_data=f"{CALLBACK.TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup


def build_teacher_reaction_on_solution(result_id: int):
    """Создает инлайн клавиатуру для учителя для оценки решения ученика
    после принятия/отклонения учителем письменной работы.
    """
    logger.debug('keyboards.build_teacher_reaction_on_solution')
    keyboard = types.InlineKeyboardMarkup()
    for reaction in db.get_reactions_enum(REACTION.WRITTEN_TEACHER):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_{result_id}_None_{reaction["reaction_id"]}_{REACTION.WRITTEN_TEACHER}'
            )
        )
    return keyboard


def build_teacher_reaction_oral(zoom_conversation_id: int):
    """Создает инлайн клавиатуру для учителя для оценки устной сдачи ученика."""
    logger.debug('keyboards.build_teacher_reaction_oral')
    keyboard = types.InlineKeyboardMarkup()
    for reaction in db.get_reactions_enum(REACTION.ORAL_TEACHER):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_None_{zoom_conversation_id}_{reaction["reaction_id"]}_{REACTION.ORAL_TEACHER}'
            )
        )
    return keyboard

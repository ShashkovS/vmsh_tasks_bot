from aiogram.dispatcher.webhook import types
from Levenshtein import jaro_winkler

from consts import *
from config import logger, config
from obj_classes import User, Problem, State, Waitlist, WrittenQueue, Result, db


def build_problems(lesson_num: int, student: User):
    logger.debug('keyboards.build_problems')
    solved = db.check_student_solved(student.id, student.level, lesson_num)
    being_checked = db.check_student_sent_written(student.id, lesson_num)
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for problem in Problem.get_by_lesson(student.level, lesson_num):
        if problem.id in solved:
            tick = '✅'
        elif problem.id in being_checked:
            tick = '❓'
        elif problem.prob_type == PROB_TYPE_ORALLY and State.get_by_user_id(student.id)['oral_problem_id'] is not None:
            tick = '⌛'
        else:
            tick = '⬜'
        if problem.prob_type == PROB_TYPE_TEST:
            tp = '⋯'
        elif problem.prob_type == PROB_TYPE_WRITTEN or problem.prob_type == PROB_TYPE_WRITTEN_BEFORE_ORALLY:
            tp = '🖊'
        elif problem.prob_type == PROB_TYPE_ORALLY:
            tp = '🗣'
        else:
            tp = '?'
        task_button = types.InlineKeyboardButton(
            text=f"{tick} {tp} {problem}",
            callback_data=f"{CALLBACK_PROBLEM_SELECTED}_{problem.id}"
        )
        keyboard_markup.add(task_button)
    # Пока отключаем эту фичу
    # to_lessons_button = types.InlineKeyboardButton(
    #     text="К списку всех листков",
    #     callback_data=f"{CALLBACK_SHOW_LIST_OF_LISTS}"
    # )
    # keyboard_markup.add(to_lessons_button)
    return keyboard_markup


def build_lessons():
    logger.debug('keyboards.build_lessons')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    logger.error('Здесь не добавлена обработка level')
    # TODO add level
    # for lesson in problems.all_lessons:
    #     lesson_button = types.InlineKeyboardButton(
    #         text=f"Листок {lesson}",
    #         callback_data=f"{CALLBACK_LIST_SELECTED}_{lesson}",
    #     )
    #     keyboard_markup.add(lesson_button)
    return keyboard_markup


def build_test_answers(choices):
    logger.debug('keyboards.build_test_answers')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for choice in choices:
        lesson_button = types.InlineKeyboardButton(
            text=choice,
            callback_data=f"{CALLBACK_ONE_OF_TEST_ANSWER_SELECTED}_{choice}",
        )
        keyboard_markup.add(lesson_button)
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK_CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup


def build_cancel_task_submission():
    logger.debug('keyboards.build_cancel_task_submission')
    keyboard_markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK_CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup


def build_exit_waitlist():
    logger.debug('keyboards.build_exit_waitlist')
    keyboard_markup = types.ReplyKeyboardMarkup(selective=True, resize_keyboard=True)
    exit_button = types.KeyboardButton(
        text="/exit_waitlist Выйти из очереди"
    )
    keyboard_markup.add(exit_button)
    return keyboard_markup


def build_teacher_actions():
    logger.debug('keyboards.build_teacher_actions')
    keyboard = types.InlineKeyboardMarkup()
    prb_count = db.get_written_tasks_count()
    get_written_task_button = types.InlineKeyboardButton(
        text=f"Проверить письменную задачу (всего {prb_count})",
        callback_data=CALLBACK_GET_WRITTEN_TASK
    )
    keyboard.add(get_written_task_button)
    # get_queue_top_button = types.InlineKeyboardButton(
    #     text="Вызвать школьника на устную сдачу",
    #     callback_data=CALLBACK_GET_QUEUE_TOP
    # )
    # keyboard.add(get_queue_top_button)
    insert_oral_pluses = types.InlineKeyboardButton(
        text="Внести плюсы за устную сдачу",
        callback_data=CALLBACK_INS_ORAL_PLUSSES
    )
    keyboard.add(insert_oral_pluses)
    return keyboard


def build_teacher_select_written_problem(top: list):
    logger.debug('keyboards.build_teacher_select_written_problem')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    for row in top:
        student = User.get_by_id(row['student_id'])
        problem = Problem.get_by_id(row['problem_id'])
        task_button = types.InlineKeyboardButton(
            text=f"{problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) {student.surname} {student.name}",
            callback_data=f"{CALLBACK_WRITTEN_TASK_SELECTED}_{student.id}_{problem.id}"
        )
        keyboard_markup.add(task_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK_TEACHER_CANCEL}"
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
            callback_data=f"{CALLBACK_STUDENT_SELECTED}_{student.id}"
        )
        keyboard_markup.add(student_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK_TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup


def build_written_task_checking_verdict(student: User, problem: Problem):
    logger.debug('keyboards.build_written_task_checking_verdict')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"👍 Засчитать задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})",
        callback_data=f"{CALLBACK_WRITTEN_TASK_OK}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отклонить и переслать все сообщения выше студенту {student.surname} {student.name}",
        callback_data=f"{CALLBACK_WRITTEN_TASK_BAD}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"Отказаться от проверки и вернуться назад",
        callback_data=f"{CALLBACK_TEACHER_CANCEL}_{student.id}_{problem.id}"
    ))
    return keyboard_markup


def build_student_in_conference():
    logger.debug('keyboards.build_student_in_conference')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"✔ Беседа окончена",
        callback_data=f"{CALLBACK_GET_OUT_OF_WAITLIST}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отказаться от устной сдачи",
        callback_data=f"{CALLBACK_GET_OUT_OF_WAITLIST}"
    ))
    return keyboard_markup


def build_verdict(plus_ids: set, minus_ids: set, student):
    logger.debug('keyboards.build_verdict')
    lesson_num = Problem.last_lesson_num()
    solved = db.check_student_solved(student.id, student.level, lesson_num)
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    plus_ids_str = ','.join(map(str, plus_ids))
    minus_ids_str = ','.join(map(str, minus_ids))
    use_problems = [problem for problem in Problem.get_by_lesson(student.level, lesson_num) if
                    problem.prob_type in (PROB_TYPE_WRITTEN, PROB_TYPE_ORALLY, PROB_TYPE_WRITTEN_BEFORE_ORALLY)]
    for problem in use_problems:
        if problem.id in solved and problem.id not in minus_ids:
            tick = '✅✅'
        elif problem.id in plus_ids:
            tick = '👍'
        elif problem.id in minus_ids:
            tick = '❌'
        else:
            tick = ''
        task_button = types.InlineKeyboardButton(
            text=f"{tick} {problem}",
            callback_data=f"{CALLBACK_ADD_OR_REMOVE_ORAL_PLUS}_{problem.id}_{plus_ids_str}_{minus_ids_str}"
        )
        keyboard_markup.add(task_button)
    ready_button = types.InlineKeyboardButton(
        text="Готово (завершить сдачу и внести в кондуит)",
        callback_data=f"{CALLBACK_FINISH_ORAL_ROUND}_{plus_ids_str}_{minus_ids_str}"
    )
    keyboard_markup.add(ready_button)
    return keyboard_markup

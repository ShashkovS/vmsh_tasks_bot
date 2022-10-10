from aiogram import types

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, Problem, State, db


def build_problems(lesson_num: int, student: User, is_sos_question=False):
    logger.debug('keyboards.build_problems')
    solved = set(db.check_student_solved(student.id, lesson_num))
    being_checked = set(db.check_student_sent_written(student.id, lesson_num))
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    # Кнопки с вопросами
    if not is_sos_question:
        que1 = types.InlineKeyboardButton(
            text=f"Вопрос по задаче",
            callback_data=CALLBACK.PROBLEM_SOS
        )
        que2 = types.InlineKeyboardButton(
            text=f"Другой вопрос",
            callback_data=CALLBACK.OTHER_SOS
        )
        keyboard_markup.row(que1, que2)
    for problem in Problem.get_by_lesson(student.level, lesson_num):
        if problem.synonyms & solved:
            tick = '✅'
        elif problem.synonyms & being_checked:
            tick = '❓'
        elif problem.prob_type == PROB_TYPE.ORALLY and State.get_by_user_id(student.id)['oral_problem_id'] is not None:
            tick = '⌛'
        else:
            tick = '⬜'
        if problem.prob_type == PROB_TYPE.TEST:
            tp = '⋯'
        elif problem.prob_type == PROB_TYPE.WRITTEN or problem.prob_type == PROB_TYPE.WRITTEN_BEFORE_ORALLY:
            tp = '🖊'
        elif problem.prob_type == PROB_TYPE.ORALLY:
            tp = '🗣'
        else:
            tp = '?'
        if is_sos_question:
            use_callback = CALLBACK.SOS_PROBLEM_SELECTED
            tt = '❓'
        else:
            use_callback = CALLBACK.PROBLEM_SELECTED
            tt = ""
        task_button = types.InlineKeyboardButton(
            text=f"{tt}{tick} {tp} {problem}{tt}",
            callback_data=f"{use_callback}_{problem.id}"
        )
        keyboard_markup.add(task_button)
    # Пока отключаем эту фичу
    # to_lessons_button = types.InlineKeyboardButton(
    #     text="К списку всех листков",
    #     callback_data=f"{Callback.SHOW_LIST_OF_LISTS}"
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
    #         callback_data=f"{Callback.LIST_SELECTED}_{lesson}",
    #     )
    #     keyboard_markup.add(lesson_button)
    return keyboard_markup


def build_test_answers(problem: Problem):
    logger.debug('keyboards.build_test_answers')
    choices = problem.ans_validation.split(';')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for choice in choices:
        lesson_button = types.InlineKeyboardButton(
            text=choice,
            callback_data=f"{CALLBACK.ONE_OF_TEST_ANSWER_SELECTED}_{problem.id}_{choice[:24]}",  # Максимальная длина callback_data — 65 байт.
        )
        keyboard_markup.add(lesson_button)
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK.CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup


def build_cancel_task_submission():
    logger.debug('keyboards.build_cancel_task_submission')
    keyboard_markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK.CANCEL_TASK_SUBMISSION,
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


def build_student_in_conference():
    logger.debug('keyboards.build_student_in_conference')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"✔ Беседа окончена",
        callback_data=f"{CALLBACK.GET_OUT_OF_WAITLIST}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отказаться от устной сдачи",
        callback_data=f"{CALLBACK.GET_OUT_OF_WAITLIST}"
    ))
    return keyboard_markup

def build_student_sos_actions():
    logger.debug('keyboards.build_student_sos_actions')
    keyboard = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(
        text=f"Вопрос по задаче",
        callback_data=CALLBACK.PROBLEM_SOS
    )
    keyboard.add(button)
    button = types.InlineKeyboardButton(
        text=f"Другой вопрос",
        callback_data=CALLBACK.OTHER_SOS
    )
    keyboard.add(button)
    return keyboard

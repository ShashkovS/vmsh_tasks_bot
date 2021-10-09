from aiogram import types

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, Problem, State, db


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
        task_button = types.InlineKeyboardButton(
            text=f"{tick} {tp} {problem}",
            callback_data=f"{CALLBACK.PROBLEM_SELECTED}_{problem.id}"
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

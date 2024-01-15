from aiogram import types

from helpers.consts import *
from helpers.config import logger, config
from models import User, Problem, State, Webtoken
from helpers.features import RESULT_MODE, FEATURES
import db_methods as db


def build_problems(lesson_num: int, student: User, is_sos_question=False):
    logger.debug('keyboards.build_problems')
    solved = set(db.result.check_student_solved(student.id, lesson_num))
    being_checked = set(db.written_task_queue.check_student_sent_written(student.id, lesson_num))
    if RESULT_MODE == FEATURES.RESULT_AFTER:
        student_tried = set(db.result.check_student_tried(student.id, lesson_num))
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    # to_game_button = types.InlineKeyboardButton(
    #     text="🕹🎲 Открыть командную игру 🎉🏆",
    #     url=f'https://{config.webhook_host}/game/webtoken/{Webtoken.webtoken_by_user(student)}'
    # )
    # keyboard_markup.add(to_game_button)
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
        synonyms_set = problem.synonyms_set()
        if RESULT_MODE == FEATURES.RESULT_IMMEDIATELY:
            if synonyms_set & solved:
                tick = '✅'
            elif synonyms_set & being_checked:
                tick = '❓'
            elif problem.prob_type == PROB_TYPE.ORALLY and State.get_by_user_id(student.id)['oral_problem_id'] is not None:
                tick = '⌛'
            else:
                tick = '⬜'
        elif RESULT_MODE == FEATURES.RESULT_AFTER:
            if synonyms_set & student_tried or synonyms_set & being_checked:
                tick = '❓'
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
    #     callback_data=f"{CALLBACK.SHOW_LIST_OF_LISTS}"
    # )
    # keyboard_markup.add(to_lessons_button)
    # to_game_button = types.InlineKeyboardButton(
    #     text="🕹🎲 Открыть командную игру 🎉🏆",
    #     url=f'https://{config.webhook_host}/game/webtoken/{Webtoken.webtoken_by_user(student)}'
    # )
    # keyboard_markup.add(to_game_button)
    return keyboard_markup


def build_lessons(level):
    logger.debug('keyboards.build_lessons')
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for lesson in db.lesson.get_all(level):
        lesson_button = types.InlineKeyboardButton(
            text=f"Листок {lesson['lesson']}",
            callback_data=f"{CALLBACK.LIST_SELECTED}_{lesson['lesson']}",
        )
        keyboard_markup.add(lesson_button)
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


def build_student_reaction_on_task_bad_verdict(result_id: int):
    """Создает инлайн клавиатуру для ученика получающего отрицательный вердикт по письменной работе.
    (В результате нажатия учителем "Отклонить и переслать все сообщения выше студенту ...").
    """
    logger.debug('keyboards.build_student_reaction_on_task_bad_verdict')
    keyboard = types.InlineKeyboardMarkup()
    for reaction in db.reaction.enum(REACTION.WRITTEN_STUDENT):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_{result_id}_None_{reaction["reaction_id"]}_{REACTION.WRITTEN_STUDENT}'
            )
        )
    return keyboard


def build_student_reaction_oral(zoom_conversation_id: int):
    """Создает инлайн клавиатуру для ученика для оценки устной сдачи."""
    logger.debug('keyboards.build_student_reaction_oral')
    keyboard = types.InlineKeyboardMarkup()
    for reaction in db.reaction.enum(REACTION.ORAL_STUDENT):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_None_{zoom_conversation_id}_{reaction["reaction_id"]}_{REACTION.ORAL_STUDENT}'
            )
        )
    return keyboard

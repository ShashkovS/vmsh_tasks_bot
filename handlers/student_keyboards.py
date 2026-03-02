from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from helpers.consts import *
from helpers.config import logger, config
from helpers.msg_texts import msgs
from models import User, Problem, State, Webtoken
from helpers.features import RESULT_MODE, FEATURES, PREV_PROBLEMS_MODE, GAME_MODE
import db_methods as db


def build_problems(lesson_num: int, student: User, is_sos_question=False):
    logger.debug('keyboards.build_problems')
    group_id = student.group_id
    solved = db.result.check_student_solved(student.id, lesson_num, group_id=group_id)
    being_checked = set(db.written_task_queue.check_student_sent_written(student.id, lesson_num))
    student_tried = set()
    if RESULT_MODE == FEATURES.RESULT_AFTER:
        student_tried = set(db.result.check_student_tried(student.id, lesson_num))
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    if GAME_MODE == FEATURES.GAME_SHOW:
        to_game_button = types.InlineKeyboardButton(
            text=msgs.open_game,
            url=f'https://{config.webhook_host}/game/webtoken/{Webtoken.webtoken_by_user(student)}'
        )
        keyboard_markup.add(to_game_button)
    # Кнопки с вопросами
    if not is_sos_question:
        que1 = types.InlineKeyboardButton(
            text=msgs.problem_question,
            callback_data=CALLBACK.PROBLEM_SOS
        )
        que2 = types.InlineKeyboardButton(
            text=msgs.other_question,
            callback_data=CALLBACK.OTHER_SOS
        )
        keyboard_markup.row(que1, que2)
    if group_id and not student.can_access_group(group_id):
        return keyboard_markup.as_markup()
    for problem in Problem.get_by_lesson(group_id, lesson_num):
        synonyms_set = problem.synonyms_set()
        if RESULT_MODE == FEATURES.RESULT_IMMEDIATELY:
            max_verdict = VERDICT.NO_ANSWER if not solved else max(solved.get(prob_id, VERDICT.NO_ANSWER) for prob_id in synonyms_set)
            verdict_tick = VERDICT_TO_TICK[max_verdict]
            if max_verdict in VERDICTS_SOLVED:
                tick = verdict_tick
            elif synonyms_set & being_checked:
                tick = '❓'
            elif problem.prob_type == PROB_TYPE.ORALLY and State.get_by_user_id(student.id)['oral_problem_id'] is not None:
                tick = '⌛'
            else:
                tick = verdict_tick
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
    if PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_SHOW_ALL or PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_SHOW_ALL:
        to_lessons_button = types.InlineKeyboardButton(
            text=msgs.to_list_of_topics,
            callback_data=f"{CALLBACK.SHOW_LIST_OF_LISTS}"
        )
        keyboard_markup.add(to_lessons_button)
    if GAME_MODE == FEATURES.GAME_SHOW:
        to_game_button = types.InlineKeyboardButton(
            text=msgs.open_game,
            url=f'https://{config.webhook_host}/game/webtoken/{Webtoken.webtoken_by_user(student)}'
        )
        keyboard_markup.add(to_game_button)
    return keyboard_markup.as_markup()


def build_lessons(group_id: str = None):
    logger.debug('keyboards.build_lessons')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    all_lessons = db.lesson.get_all(group_id=group_id)
    # PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_SHOW_ALL or PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_SHOW_ALL
    use_lessons = []
    if PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_SHOW_ALL:
        use_lessons = all_lessons
    elif PREV_PROBLEMS_MODE == FEATURES.PREV_PROBLEMS_PREV and all_lessons:
        last = max(lesson['lesson'] for lesson in all_lessons)
        use_lessons = [lesson for lesson in all_lessons if lesson['lesson'] >= last - 1]  # ахтунг! int !!
    for lesson in use_lessons:
        lesson_num = lesson['lesson']
        lesson_button = types.InlineKeyboardButton(
            text=msgs.topic_hint.format_map({'lesson_num': lesson_num}),
            callback_data=f"{CALLBACK.LIST_SELECTED}_{lesson['lesson']}",
        )
        keyboard_markup.add(lesson_button)
    return keyboard_markup.as_markup()


def build_test_answers(problem: Problem):
    logger.debug('keyboards.build_test_answers')
    choices = problem.ans_validation.split(';')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    for choice in choices:
        lesson_button = types.InlineKeyboardButton(
            text=choice,
            callback_data=f"{CALLBACK.ONE_OF_TEST_ANSWER_SELECTED}_{problem.id}_{choice[:24]}",  # Максимальная длина callback_data — 65 байт.
        )
        keyboard_markup.add(lesson_button)
    cancel_button = types.InlineKeyboardButton(
        text=msgs.cancel,
        callback_data=CALLBACK.CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup.as_markup()


def build_cancel_task_submission():
    logger.debug('keyboards.build_cancel_task_submission')
    keyboard_markup = InlineKeyboardBuilder()
    cancel_button = types.InlineKeyboardButton(
        text=msgs.cancel,
        callback_data=CALLBACK.CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup.as_markup()


def build_exit_waitlist():
    logger.debug('keyboards.build_exit_waitlist')
    keyboard_markup = ReplyKeyboardBuilder()
    exit_button = types.KeyboardButton(
        text="/exit_waitlist Выйти из очереди"
    )
    keyboard_markup.add(exit_button)
    return keyboard_markup.as_markup(selective=True, resize_keyboard=True)


def build_student_in_conference():
    logger.debug('keyboards.build_student_in_conference')
    keyboard_markup = InlineKeyboardBuilder()
    keyboard_markup.max_width = 1
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"✔ Беседа окончена",
        callback_data=f"{CALLBACK.GET_OUT_OF_WAITLIST}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отказаться от устной сдачи",
        callback_data=f"{CALLBACK.GET_OUT_OF_WAITLIST}"
    ))
    return keyboard_markup.as_markup()


def build_student_sos_actions():
    logger.debug('keyboards.build_student_sos_actions')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    button = types.InlineKeyboardButton(
        text=msgs.problem_question,
        callback_data=CALLBACK.PROBLEM_SOS
    )
    keyboard.add(button)
    button = types.InlineKeyboardButton(
        text=msgs.other_question,
        callback_data=CALLBACK.OTHER_SOS
    )
    keyboard.add(button)
    return keyboard.as_markup()


def build_student_reaction_on_task_bad_verdict(result_id: int):
    """Создает инлайн клавиатуру для ученика получающего отрицательный вердикт по письменной работе.
    (В результате нажатия учителем "Отклонить и переслать все сообщения выше студенту ...").
    """
    logger.debug('keyboards.build_student_reaction_on_task_bad_verdict')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    for reaction in db.reaction.enum(REACTION.WRITTEN_STUDENT):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_{result_id}_None_{reaction["reaction_id"]}_{REACTION.WRITTEN_STUDENT}'
            )
        )
    return keyboard.as_markup()


def build_student_reaction_oral(zoom_conversation_id: int):
    """Создает инлайн клавиатуру для ученика для оценки устной сдачи."""
    logger.debug('keyboards.build_student_reaction_oral')
    keyboard = InlineKeyboardBuilder()
    keyboard.max_width = 1
    for reaction in db.reaction.enum(REACTION.ORAL_STUDENT):
        keyboard.add(
            types.InlineKeyboardButton(
                text=reaction['reaction'],
                callback_data=f'{CALLBACK.REACTION}_None_{zoom_conversation_id}_{reaction["reaction_id"]}_{REACTION.ORAL_STUDENT}'
            )
        )
    return keyboard.as_markup()

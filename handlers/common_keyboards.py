from aiogram import types

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User


def build_survey(user: User, survey, survey_result):
    logger.debug('keyboards.build_problems')
    # survey: {'id': 1, 'survey_type': 'r', 'for_user_type': 1, 'is_active': 1, 'question': 'WHAT??',
    # 'choices': [
    #   {'id': 1, 'survey_id': 1, 'text': 'One'},
    #   {'id': 2, 'survey_id': 1, 'text': 'Two'}
    #   ]}
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for choice in survey['choices']:
        if choice['id'] in survey_result:
            tick = '✅'
        else:
            tick = '⬜'
        cur_choices = ';'.join(map(str, survey_result))
        task_button = types.InlineKeyboardButton(
            text=f"{tick} {choice['text']}",
            callback_data=f"{CALLBACK.SURVEY}_{user.id}_{survey['id']}_{survey['survey_type']}_{choice['id']}_{cur_choices}"
        )
        keyboard_markup.add(task_button)
    return keyboard_markup

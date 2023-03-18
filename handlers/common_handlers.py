import asyncio

import aiogram
from aiogram.dispatcher.webhook import types
from aiogram.utils.exceptions import BadRequest
from contextlib import suppress

from handlers import sleep_and_send_problems_keyboard
from handlers.common_keyboards import build_survey
from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, db
from helpers.bot import reg_callback, bot, reg_state


@reg_callback(CALLBACK.REACTION)
async def prc_reaction(query: types.CallbackQuery, student: User):
    """Коллбек на реакцию учителя."""
    logger.debug(f'prc_reaction - {query.data}')
    callback, result_id, zoom_conversation_id, reaction_id, reaction_type_id = query.data.split('_')
    reaction_type_id = int(reaction_type_id)
    reaction_id = int(reaction_id)
    result_id = int(result_id) if result_id.isdecimal() else None
    zoom_conversation_id = int(zoom_conversation_id) if zoom_conversation_id.isdecimal() else None
    # вносим реакции в БД
    db.write_reaction(result_id=result_id, zoom_conversation_id=zoom_conversation_id,
                      reaction_type_id=reaction_type_id, reaction_id=reaction_id)

    # отвечаем на внесённые реакций в телеграме
    # учитель
    old_text = query.message.text
    if reaction_type_id in (REACTION.WRITTEN_TEACHER, REACTION.ORAL_TEACHER):
        original_message = query.message.text.split('\n')[0] if reaction_type_id == REACTION.WRITTEN_TEACHER else query.message.text
        new_text = f"{original_message}\n\n{db.get_reaction_by_id(reaction_id)}"
        if old_text != new_text:
            with suppress(aiogram.utils.exceptions.MessageNotModified):
                await query.message.edit_text(new_text, reply_markup=None)
        try:
            await query.answer(f'Принято')
        except aiogram.utils.exceptions.InvalidQueryID:
            pass
    # ученик
    elif reaction_type_id in (REACTION.WRITTEN_STUDENT, REACTION.ORAL_STUDENT):
        original_message = query.message.text.split()[0] if reaction_type_id == REACTION.WRITTEN_STUDENT else query.message.text
        new_text = f"{original_message}\n\n{db.get_reaction_by_id(reaction_id)}"
        if old_text != new_text:
            with suppress(aiogram.utils.exceptions.MessageNotModified):
                await query.message.edit_text(new_text, reply_markup=None)
        try:
            await query.answer(f'Принято')
        except aiogram.utils.exceptions.InvalidQueryID:
            pass


@reg_callback(CALLBACK.SURVEY)
async def prc_survey(query: types.CallbackQuery, user: User):
    """Коллбек на реакцию учителя."""
    logger.debug(f'prc_survey - {query.data}')
    callback, user_id, survey_id, survey_type, choice_id, selection_ids = query.data.split('_')
    user_id = int(user_id)
    survey_id = int(survey_id)
    choice_id = int(choice_id)
    if survey_type == SURVEY_TYPES.RADIO:
        selection_ids = [choice_id]
        db.update_survey_result(user_id, survey_id, selection_ids)
    elif survey_type == SURVEY_TYPES.CHECKBOX:
        selection_ids = set(map(int, selection_ids.split(';'))) ^ {choice_id}
        db.update_survey_result(user_id, survey_id, selection_ids)
    survey = db.get_survey_by_id(survey_id)
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=build_survey(user, survey, selection_ids))
    await bot.answer_callback_query_ig(query.id)

@reg_state(STATE.SURVEY)
async def prc_survey_state(message, student: User):
    logger.debug('prc_survey_state')
    # Обрабатываем как обычно
    alarm = ''
    # Попытка послать что-то во время опроса
    if message.photo or message.document:
        alarm = '❗❗❗ Файл НЕ ПРИНЯТ'
    elif message.text and len(message.text) > 5:
        alarm = '❗❗❗ Текст НЕ ПРИНЯТ'
    sleep = 0
    if alarm:
        await bot.send_message(chat_id=message.chat.id, text=alarm, )
        sleep = 8
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student, sleep=sleep))

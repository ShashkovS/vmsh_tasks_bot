import aiogram
from aiogram.dispatcher.webhook import types
from aiogram.utils.exceptions import BadRequest
from contextlib import suppress

from helpers.consts import *
from helpers.config import logger
import db_methods as db
from models import User, Webtoken
from helpers.bot import reg_callback, dispatcher, bot
from handlers.common_keyboards import build_survey


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
    db.reaction.insert(result_id=result_id, zoom_conversation_id=zoom_conversation_id,
                      reaction_type_id=reaction_type_id, reaction_id=reaction_id)

    # отвечаем на внесённые реакций в телеграме
    # учитель
    old_text = query.message.text
    if reaction_type_id in (REACTION.WRITTEN_TEACHER, REACTION.ORAL_TEACHER):
        original_message = query.message.text.split('\n')[0] if reaction_type_id == REACTION.WRITTEN_TEACHER else query.message.text
        new_text = f"{original_message}\n\n{db.reaction.get_by_id(reaction_id)}"
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
        new_text = f"{original_message}\n\n{db.reaction.get_by_id(reaction_id)}"
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
        db.survey.update_survey_result(user_id, survey_id, selection_ids)
    elif survey_type == SURVEY_TYPES.CHECKBOX:
        selection_ids = set(map(int, selection_ids.split(';'))) ^ {choice_id}
        db.survey.update_survey_result(user_id, survey_id, selection_ids)
    survey = db.survey.get_survey_by_id(survey_id)
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=build_survey(user, survey, selection_ids))
    await bot.answer_callback_query_ig(query.id)

@dispatcher.message_handler(commands=['password'])
async def get_my_password(message: types.Message):
    logger.debug('password')
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        return
    await bot.send_message(
        chat_id=message.chat.id, parse_mode = "HTML",
        text=f"🤖 Ваш пароль:\n<pre>{user.token}</pre>",
    )

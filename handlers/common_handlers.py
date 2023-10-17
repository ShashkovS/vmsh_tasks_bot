import aiogram
from aiogram.dispatcher.webhook import types
from aiogram.utils.exceptions import BadRequest
from contextlib import suppress

from helpers.consts import *
from helpers.config import logger, config
import db_methods as db
from models import User, Webtoken
from helpers.bot import reg_callback, dispatcher, bot


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


@dispatcher.message_handler(commands=['statw'])
async def get_statw_url(message: types.Message):
    logger.debug('statw')
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        return
    url = f'https://{config.webhook_host}/stat/webtoken/{Webtoken.webtoken_by_user(user)}'
    await bot.send_message(
        chat_id=message.chat.id,
        text=url,
    )

import aiogram
from aiogram.dispatcher.webhook import types
from aiogram.utils.exceptions import BadRequest

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, db
from helpers.bot import reg_callback


@reg_callback(CALLBACK.REACTION)
async def prc_reaction(query: types.CallbackQuery, student: User):
    """Коллбек на реакцию учителя."""
    callback, result_or_zoom_conversation_id, reaction_id, reaction_type_id = query.data.split('_')
    reaction_type_id = int(reaction_type_id)
    logger.debug(f'prc_reaction - {query.data}')
    reaction_id = int(reaction_id)
    result_or_conversation_id = int(result_or_zoom_conversation_id)
    # вносим реакции в БД
    try:
        # письменно
        if reaction_type_id in (REACTION.WRITTEN_STUDENT, REACTION.WRITTEN_TEACHER):
            result_id = result_or_zoom_conversation_id
            db.write_reaction(reaction_type_id=reaction_type_id, reaction_id=reaction_id, result_id=result_id)
        # устно
        elif reaction_type_id in (REACTION.ORAL_STUDENT, REACTION.ORAL_TEACHER):
            zoom_conversation_id = result_or_zoom_conversation_id
            db.write_oral_reaction(reaction_type_id=reaction_type_id, reaction_id=reaction_id, zoom_conversation_id=zoom_conversation_id)
        else:
            logger.warning(f'Неизвестный reaction_type_id={reaction_type_id} в коллбеке prc_reaction.')
    except Exception:
        logger.error(f'Ошибка записи реакции {query.data} в БД.')
    # отвечаем на внесённые реакций в телеграме
    else:
        # учитель
        if reaction_type_id in (REACTION.WRITTEN_TEACHER, REACTION.ORAL_TEACHER):
            original_message = query.message.text.split('\n')[0] if reaction_type_id == REACTION.WRITTEN_TEACHER else query.message.text
            await query.message.edit_text(f"{original_message}\n{db.get_reaction_by_id(reaction_id)}",
                                          reply_markup=None)
            await query.answer(f'Принято')
        # ученик
        elif reaction_type_id in (REACTION.WRITTEN_STUDENT, REACTION.ORAL_STUDENT):
            old_text = query.message.text
            original_message = query.message.text.split()[0] if reaction_type_id == REACTION.WRITTEN_STUDENT else query.message.text
            new_text = f"{original_message}\n{db.get_reaction_by_id(reaction_id)}"
            if old_text != new_text:
                try:
                    await query.message.edit_text(new_text, reply_markup=None)
                except aiogram.utils.exceptions.MessageNotModified:
                    pass
            await query.answer(f'Принято')



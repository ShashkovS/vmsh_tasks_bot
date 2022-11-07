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
    callback, *result_id, reaction_id, reaction_type_id = query.data.split('_')
    reaction_type_id = int(reaction_type_id)
    logger.debug(f'prc_reaction - {query.data}')
    reaction_id = int(reaction_id)
    result_id = int(result_id[0]) if result_id else None
    try:
        db.write_reaction(reaction_type_id=reaction_type_id, reaction_id=reaction_id, result_id=result_id)
    except Exception:
        logger.error(f'Ошибка записи реакции {query.data} в БД.')
    else:
        # учитель
        if reaction_type_id in (REACTION.WRITTEN_TEACHER,):
            original_message = query.message.text.split('\n')[0]
            await query.message.edit_text(f"{original_message}\n{db.get_reaction_by_id(reaction_id)}",
                                          reply_markup=None)
            await query.answer(f'Принято')
        # ученик
        elif reaction_type_id in (REACTION.WRITTEN_STUDENT,):
            old_text = query.message.text
            original_message = query.message.text.split()[0]
            new_text = f"{original_message}\n{db.get_reaction_by_id(reaction_id)}"
            if old_text != new_text:
                try:
                    await query.message.edit_text(new_text, reply_markup=None)
                except aiogram.utils.exceptions.MessageNotModified:
                    pass
            await query.answer(f'Принято')
        else:
            logger.warning('Неизвестный reaction_type_id в коллбеке prc_reaction.')




# @reg_callback(CALLBACK.REACTION)
# async def prc_student_reaction(query: types.CallbackQuery, student: User):
#     """Коллбек на реакцию ученика."""
#     callback, *result_id, reaction_id, reaction_type_id = query.data.split('_')
#     reaction_type_id = int(reaction_type_id)
#     if reaction_type_id not in (REACTION.WRITTEN_STUDENT, REACTION.ORAL_STUDENT):  # здесь обрабатываем только реакции ученика
#         return
#     logger.debug(f'prc_student_reaction - {query.data}')
#     reaction_id = int(reaction_id)
#     result_id = int(result_id[0]) if result_id else None
#     try:
#         db.write_reaction(reaction_type_id, result_id, reaction_id)
#     except Exception:
#         logger.error('Ошибка записи реакции ученика в БД.')
#     else:
#         old_text = query.message.text
#         original_message = query.message.text.split()[0]
#         new_text = f"{original_message}\nОценка проверки: {db.get_reaction_by_id(reaction_id)}"
#         if old_text != new_text:
#             try:
#                 await query.message.edit_text(new_text, reply_markup=None)
#             except aiogram.utils.exceptions.MessageNotModified:
#                 pass
#         await query.answer(f'Принято')

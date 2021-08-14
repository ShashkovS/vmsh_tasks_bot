# -*- coding: utf-8 -*-
from config import config, logger
import aiogram
from aiogram.utils.exceptions import MessageNotModified
from aiogram.dispatcher import Dispatcher
from consts import CALLBACK

# Запускаем API телеграм-бота
bot = aiogram.Bot(config.telegram_bot_token)
# Запускаем API телеграм-бота
dispatcher = Dispatcher(bot)


async def bot_edit_message_text(*args, **kwargs):
    logger.debug('bot_edit_message_text')
    try:
        await bot.edit_message_text(*args, **kwargs)
    except MessageNotModified as e:
        logger.INFO(f'SHIT: {e}')


async def bot_edit_message_reply_markup(*args, **kwargs):
    logger.debug('bot_edit_message_reply_markup')
    try:
        await bot.edit_message_reply_markup(*args, **kwargs)
    except MessageNotModified as e:
        logger.INFO(f'SHIT: {e}')


async def bot_answer_callback_query(*args, **kwargs):
    logger.debug('bot_answer_callback_query')
    try:
        await bot.answer_callback_query(*args, **kwargs)
    except Exception as e:
        logger.error(f'SHIT: {e}')


async def bot_post_logging_message(msg):
    logger.debug('bot_post_logging_message')
    if config.production_mode:
        msg = 'PRODUCTION!\n' + msg
    else:
        msg = 'DEV MODE\n' + msg
    try:
        res = await bot.send_message(config.exceptions_channel, msg)
        # У секрентного чата id — это число. А у открытого — это строка.
        if type(config.exceptions_channel) == str:
            await bot.send_message(config.exceptions_channel, f'(Exceptions chat id = {res["chat"]["id"]})')
    except Exception as e:
        logger.error(f'SHIT: {e}')


callbacks_processors = {
}


def callback(key: CALLBACK):
    def decorator(callback_func):
        callbacks_processors[key.value] = callback_func
        return callback_func

    return decorator

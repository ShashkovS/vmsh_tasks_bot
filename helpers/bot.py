# -*- coding: utf-8 -*-
import aiogram
from aiogram.utils.exceptions import MessageNotModified
from aiogram.dispatcher import Dispatcher
from helpers.config import config, logger
from helpers.consts import CALLBACK, STATE


# Добавляем методов, которые игнорируют некоторые ошибки
class BotIg(aiogram.Bot):
    async def edit_message_text_ig(self, *args, **kwargs):
        logger.debug('bot.edit_message_text_ig')
        try:
            await self.edit_message_text(*args, **kwargs)
        except MessageNotModified as e:
            pass

    async def edit_message_reply_markup_ig(self, *args, **kwargs):
        logger.debug('bot.edit_message_reply_markup_ig')
        try:
            await self.edit_message_reply_markup(*args, **kwargs)
        except MessageNotModified as e:
            pass

    async def answer_callback_query_ig(self, *args, **kwargs):
        logger.debug('bot.answer_callback_query_ig')
        try:
            await self.answer_callback_query(*args, **kwargs)
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def delete_message_ig(self, *args, **kwargs):
        logger.debug('bot.delete_message_ig')
        try:
            await self.delete_message(*args, **kwargs)
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def post_logging_message(self, msg):
        logger.debug('bot.post_logging_message')
        if config.production_mode:
            msg = 'PRODUCTION!\n' + msg
        else:
            msg = 'DEV MODE\n' + msg
        try:
            res = await self.send_message(config.exceptions_channel, msg)
            # У секрентного чата id — это число. А у открытого — это строка.
            if type(config.exceptions_channel) == str:
                await self.send_message(config.exceptions_channel, f'(Exceptions chat id = {res["chat"]["id"]})')
        except Exception as e:
            logger.exception(f'SHIT: {e}')


# Запускаем API телеграм-бота
bot = BotIg(config.telegram_bot_token)
# Запускаем API телеграм-бота
dispatcher = Dispatcher(bot)

callbacks_processors = {}
state_processors = {}


def reg_callback(key: CALLBACK):
    def decorator(callback_func):
        callbacks_processors[key.value] = callback_func
        return callback_func

    return decorator


def reg_state(state: STATE):
    def decorator(callback_func):
        state_processors[state.value] = callback_func
        return callback_func

    return decorator

# -*- coding: utf-8 -*-
import aiogram
import asyncio
from aiogram.utils.exceptions import MessageNotModified, MessageToEditNotFound
from aiogram.dispatcher import Dispatcher
from helpers.config import config, logger
from helpers.consts import CALLBACK, STATE


# Добавляем методов, которые игнорируют некоторые ошибки
class BotIg(aiogram.Bot):
    username: aiogram.types.User

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
        except (MessageNotModified, MessageToEditNotFound) as e:
            pass

    async def answer_callback_query_ig(self, *args, **kwargs):
        logger.debug('bot.answer_callback_query_ig')
        try:
            await self.answer_callback_query(*args, **kwargs)
        except aiogram.utils.exceptions.InvalidQueryID:
            pass
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def delete_message_ig(self, *args, **kwargs):
        logger.debug('bot.delete_message_ig')
        try:
            await self.delete_message(*args, **kwargs)
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass
        except aiogram.utils.exceptions.MessageCantBeDeleted:
            try:
                await self.edit_message_reply_markup_ig(*args, reply_markup=None, **kwargs)
            except MessageNotModified as e:
                pass
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def post_logging_message(self, msg):
        logger.debug('bot.post_logging_message')
        bot_type = 'PRODUCTION' if config.production_mode else 'DEV MODE'
        try:
            res = await self.send_message(config.exceptions_channel, f'{bot_type} @{bot.username}\n{msg}')
            # У секрентного чата id — это число. А у открытого — это строка.
            if type(config.exceptions_channel) == str:
                await self.send_message(config.exceptions_channel, f'(Exceptions chat id = {res["chat"]["id"]})')
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def delete_messages_after_task(self, messages: list, timeout: int):  # List[types.Message]
        await asyncio.sleep(timeout)
        if type(messages) == aiogram.types.Message:
            messages = [messages]
        for message in messages:
            await self.delete_message_ig(chat_id=message.chat.id, message_id=message.message_id)

    async def delete_messages_after(self, messages: list, timeout: int):  # List[types.Message]
        asyncio.create_task(self.delete_messages_after_task(messages, timeout))


# Запускаем API телеграм-бота
bot = BotIg(config.telegram_bot_token, timeout=5)
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

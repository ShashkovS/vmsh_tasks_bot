# -*- coding: utf-8 -*-
import aiogram
import asyncio
import typing
from typing import List, Union
from aiogram.utils.exceptions import MessageNotModified, MessageToEditNotFound, ChatNotFound
from aiogram.dispatcher import Dispatcher
import aiogram.types as types
from aiogram.types import Message, base
from helpers.config import config, logger
from helpers.consts import CALLBACK, STATE

TIMEOUTS = [0.5, 1, 2, None]

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
        except (MessageNotModified, MessageToEditNotFound, ChatNotFound) as e:
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

    async def delete_messages_after_task(self, messages: Union[List[Message], Message], timeout: int):  # List[types.Message]
        await asyncio.sleep(timeout)
        if type(messages) == Message:
            messages = [messages]
        for message in messages:
            await self.delete_message_ig(chat_id=message.chat.id, message_id=message.message_id)

    async def remove_markup_after_task(self, messages: Union[List[Message], Message], timeout: int):  # List[types.Message]
        await asyncio.sleep(timeout)
        if type(messages) == Message:
            messages = [messages]
        for message in messages:
            await self.edit_message_reply_markup_ig(chat_id=message.chat.id, message_id=message.message_id, reply_markup=None)

    def delete_messages_after(self, messages: Union[List[Message], Message], timeout: int):
        asyncio.create_task(self.delete_messages_after_task(messages, timeout))

    def remove_markup_after(self, messages: Union[List[Message], Message], timeout: int):
        asyncio.create_task(self.remove_markup_after_task(messages, timeout))

    async def copy_message(
            self,
            chat_id: typing.Union[base.Integer, base.String],
            from_chat_id: typing.Union[base.Integer, base.String],
            message_id: base.Integer,
            caption: typing.Optional[base.String] = None,
            parse_mode: typing.Optional[base.String] = None,
            caption_entities: typing.Optional[typing.List[types.MessageEntity]] = None,
            message_thread_id: typing.Optional[base.Integer] = None,
            disable_notification: typing.Optional[base.Boolean] = None,
            protect_content: typing.Optional[base.Boolean] = None,
            reply_to_message_id: typing.Optional[base.Integer] = None,
            allow_sending_without_reply: typing.Optional[base.Boolean] = None,
            reply_markup: typing.Union[types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove, types.ForceReply, None] = None,
    ) -> types.MessageId:
        for t in TIMEOUTS:
            try:
                return await super().copy_message(chat_id, from_chat_id, message_id, caption, parse_mode, caption_entities, message_thread_id, disable_notification, protect_content, reply_to_message_id, allow_sending_without_reply, reply_markup)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in copy_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in copy_message in a row...")

    async def delete_message(
            self,
            chat_id: typing.Union[base.Integer, base.String],
            message_id: base.Integer
    ) -> base.Boolean:
        for t in TIMEOUTS:
            try:
                return await super().delete_message(chat_id, message_id)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in delete_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in delete_message in a row...")

    async def edit_message_reply_markup(
            self,
            chat_id: typing.Union[base.Integer, base.String, None] = None,
            message_id: typing.Optional[base.Integer] = None,
            inline_message_id: typing.Optional[base.String] = None,
            reply_markup: typing.Union[types.InlineKeyboardMarkup, None] = None
    ) -> types.Message or base.Boolean:
        for t in TIMEOUTS:
            try:
                return await super().edit_message_reply_markup(chat_id, message_id, inline_message_id, reply_markup)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in edit_message_reply_markup...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in edit_message_reply_markup in a row...")

    async def edit_message_text(
            self,
            text: base.String,
            chat_id: typing.Union[base.Integer, base.String, None] = None,
            message_id: typing.Optional[base.Integer] = None,
            inline_message_id: typing.Optional[base.String] = None,
            parse_mode: typing.Optional[base.String] = None,
            entities: typing.Optional[typing.List[types.MessageEntity]] = None,
            disable_web_page_preview: typing.Optional[base.Boolean] = None,
            reply_markup: typing.Union[types.InlineKeyboardMarkup, None] = None,
    ) -> types.Message or base.Boolean:
        for t in TIMEOUTS:
            try:
                return await super().edit_message_text(text, chat_id, message_id, inline_message_id, parse_mode, entities, disable_web_page_preview, reply_markup)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in edit_message_text...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in edit_message_text in a row...")

    async def forward_message(
            self,
            chat_id: typing.Union[base.Integer, base.String],
            from_chat_id: typing.Union[base.Integer, base.String],
            message_id: base.Integer,
            message_thread_id: typing.Optional[base.Integer] = None,
            disable_notification: typing.Optional[base.Boolean] = None,
            protect_content: typing.Optional[base.Boolean] = None,
    ) -> types.Message:
        for t in TIMEOUTS:
            try:
                return await super().forward_message(chat_id, from_chat_id, message_id, message_thread_id, disable_notification, protect_content)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in forward_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in forward_message in a row...")

    async def send_message(
            self,
            chat_id: typing.Union[base.Integer, base.String],
            text: base.String,
            parse_mode: typing.Optional[base.String] = None,
            entities: typing.Optional[typing.List[types.MessageEntity]] = None,
            disable_web_page_preview: typing.Optional[base.Boolean] = None,
            message_thread_id: typing.Optional[base.Integer] = None,
            disable_notification: typing.Optional[base.Boolean] = None,
            protect_content: typing.Optional[base.Boolean] = None,
            reply_to_message_id: typing.Optional[base.Integer] = None,
            allow_sending_without_reply: typing.Optional[base.Boolean] = None,
            reply_markup: typing.Union[types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove, types.ForceReply, None] = None,
    ) -> types.Message:
        for t in TIMEOUTS:
            try:
                return await super().send_message(chat_id, text, parse_mode, entities, disable_web_page_preview, message_thread_id, disable_notification, protect_content, reply_to_message_id, allow_sending_without_reply, reply_markup)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in send_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in send_message in a row...")

    async def answer_callback_query(
            self,
            callback_query_id: base.String,
            text: typing.Optional[base.String] = None,
            show_alert: typing.Optional[base.Boolean] = None,
            url: typing.Optional[base.String] = None,
            cache_time: typing.Optional[base.Integer] = None
    ) -> base.Boolean:
        for t in TIMEOUTS:
            try:
                return await super().answer_callback_query(callback_query_id, text, show_alert, url, cache_time)
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in answer_callback_query...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in answer_callback_query in a row...")


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

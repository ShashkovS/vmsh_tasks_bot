# -*- coding: utf-8 -*-
import asyncio
import typing
import time
from typing import List, Union

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import Default, DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)
import aiogram.types as types
from aiogram.types import ErrorEvent, Message
from helpers.config import config, logger, sentry_sdk
from helpers.consts import CALLBACK, STATE

TIMEOUTS = [0.5, 1, 2, None]

prev_usr_ts = {}
prev_global_ts = -1
LIMIT = 1 / 5
GLOBAL_LIMIT = 1 / 30


async def rate_lim(chat_id: int):
    global prev_global_ts
    current_utc_time = time.time()
    prev_utc_time = prev_usr_ts.get(chat_id, -1)
    while current_utc_time - prev_utc_time < LIMIT or current_utc_time - prev_global_ts < GLOBAL_LIMIT:
        if current_utc_time - prev_utc_time < LIMIT:
            await asyncio.sleep(LIMIT)
        else:
            await asyncio.sleep(GLOBAL_LIMIT)
        current_utc_time = time.time()
        prev_utc_time = prev_usr_ts.get(chat_id, -1)
    prev_global_ts = prev_usr_ts[chat_id] = time.time()


# Добавляем методов, которые игнорируют некоторые ошибки
class BotIg(Bot):
    username: types.User

    async def edit_message_text_ig(self, *args, **kwargs):
        logger.debug('bot.edit_message_text_ig')
        try:
            await self.edit_message_text(*args, **kwargs)
        except TelegramBadRequest:
            pass

    async def edit_message_reply_markup_ig(self, *args, **kwargs):
        logger.debug('bot.edit_message_reply_markup_ig')
        try:
            await self.edit_message_reply_markup(*args, **kwargs)
        except (TelegramBadRequest, TelegramNotFound) as e:
            pass

    async def answer_callback_query_ig(self, *args, **kwargs):
        logger.debug('bot.answer_callback_query_ig')
        try:
            await self.answer_callback_query(*args, **kwargs)
        except TelegramBadRequest:
            pass
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def delete_message_ig(self, *args, **kwargs):
        logger.debug('bot.delete_message_ig')
        try:
            await self.delete_message(*args, **kwargs)
        except TelegramNotFound:
            pass
        except (TelegramBadRequest, TelegramForbiddenError):
            try:
                await self.edit_message_reply_markup_ig(*args, reply_markup=None, **kwargs)
            except TelegramBadRequest:
                pass
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def post_logging_message(self, msg):
        logger.debug('bot.post_logging_message')
        bot_type = 'PRODUCTION' if config.production_mode else 'DEV MODE'
        full_msg = f'{bot_type} @{bot.username}\n{msg}'
        if len(full_msg) > 4096:
            full_msg = full_msg[:4096]
        try:
            res = await self.send_message(config.exceptions_channel, full_msg)
            # У секрентного чата id — это число. А у открытого — это строка.
            if type(config.exceptions_channel) == str:
                await self.send_message(config.exceptions_channel, f'(Exceptions chat id = {res["chat"]["id"]})')
        except Exception as e:
            logger.exception(f'SHIT: {e}')

    async def delete_messages_after_task(
        self, messages: Union[List[Message], Message], timeout: int
        ):  # List[types.Message]
        await asyncio.sleep(timeout)
        if type(messages) == Message:
            messages = [messages]
        for message in messages:
            await self.delete_message_ig(chat_id=message.chat.id, message_id=message.message_id)

    async def remove_markup_after_task(
        self, messages: Union[List[Message], Message], timeout: int
        ):  # List[types.Message]
        await asyncio.sleep(timeout)
        if type(messages) == Message:
            messages = [messages]
        for message in messages:
            await self.edit_message_reply_markup_ig(
                chat_id=message.chat.id, message_id=message.message_id, reply_markup=None
                )

    def delete_messages_after(self, messages: Union[List[Message], Message], timeout: int):
        asyncio.create_task(self.delete_messages_after_task(messages, timeout))

    def remove_markup_after(self, messages: Union[List[Message], Message], timeout: int):
        asyncio.create_task(self.remove_markup_after_task(messages, timeout))

        # self,
        # chat_id: ChatIdUnion,
        # from_chat_id: ChatIdUnion,
        # message_id: int,
        # message_thread_id: int | None = None,
        # direct_messages_topic_id: int | None = None,
        # video_start_timestamp: DateTimeUnion | None = None,
        # caption: str | None = None,
        # parse_mode: str | Default | None = Default("parse_mode"),
        # caption_entities: list[MessageEntity] | None = None,
        # show_caption_above_media: bool | Default | None = Default("show_caption_above_media"),
        # disable_notification: bool | None = None,
        # protect_content: bool | Default | None = Default("protect_content"),
        # allow_paid_broadcast: bool | None = None,
        # message_effect_id: str | None = None,
        # suggested_post_parameters: SuggestedPostParameters | None = None,
        # reply_parameters: ReplyParameters | None = None,
        # reply_markup: ReplyMarkupUnion | None = None,
        # allow_sending_without_reply: bool | None = None,
        # reply_to_message_id: int | None = None,
        # request_timeout: int | None = None,

    async def copy_message(
        self,
        chat_id: typing.Union[int, str],
        from_chat_id: typing.Union[int, str],
        message_id: int,
        message_thread_id: typing.Optional[int] = None,
        direct_messages_topic_id: typing.Optional[int] = None,
        video_start_timestamp: typing.Optional[typing.Any] = None,
        caption: typing.Optional[str] = None,
        parse_mode: typing.Union[str, Default, None] = Default("parse_mode"),
        caption_entities: typing.Optional[typing.List[types.MessageEntity]] = None,
        show_caption_above_media: typing.Union[bool, Default, None] = Default("show_caption_above_media"),
        disable_notification: typing.Optional[bool] = None,
        protect_content: typing.Union[bool, Default, None] = Default("protect_content"),
        allow_paid_broadcast: typing.Optional[bool] = None,
        message_effect_id: typing.Optional[str] = None,
        suggested_post_parameters: typing.Optional[typing.Any] = None,
        reply_parameters: typing.Optional[typing.Any] = None,
        reply_markup: typing.Union[
            types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove, types.ForceReply, None] = None,
        allow_sending_without_reply: typing.Optional[bool] = None,
        reply_to_message_id: typing.Optional[int] = None,
        request_timeout: typing.Optional[int] = None,
    ) -> types.MessageId:
        for t in TIMEOUTS:
            try:
                return await super().copy_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                    message_thread_id=message_thread_id,
                    direct_messages_topic_id=direct_messages_topic_id,
                    video_start_timestamp=video_start_timestamp,
                    caption=caption,
                    parse_mode=parse_mode,
                    caption_entities=caption_entities,
                    show_caption_above_media=show_caption_above_media,
                    disable_notification=disable_notification,
                    protect_content=protect_content,
                    allow_paid_broadcast=allow_paid_broadcast,
                    message_effect_id=message_effect_id,
                    suggested_post_parameters=suggested_post_parameters,
                    reply_parameters=reply_parameters,
                    reply_markup=reply_markup,
                    allow_sending_without_reply=allow_sending_without_reply,
                    reply_to_message_id=reply_to_message_id,
                    request_timeout=request_timeout,
                    )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in copy_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in copy_message in a row...")

    async def delete_message(
        self,
        chat_id: typing.Union[int, str],
        message_id: int,
        request_timeout: typing.Optional[int] = None,
    ) -> bool:
        for t in TIMEOUTS:
            try:
                return await super().delete_message(
                    chat_id=chat_id,
                    message_id=message_id,
                    request_timeout=request_timeout,
                )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in delete_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in delete_message in a row...")

    async def edit_message_reply_markup(
        self,
        business_connection_id: typing.Optional[str] = None,
        chat_id: typing.Union[int, str, None] = None,
        message_id: typing.Optional[int] = None,
        inline_message_id: typing.Optional[str] = None,
        reply_markup: typing.Union[types.InlineKeyboardMarkup, None] = None,
        request_timeout: typing.Optional[int] = None,
    ) -> typing.Union[types.Message, bool]:
        for t in TIMEOUTS:
            try:
                return await super().edit_message_reply_markup(
                    business_connection_id=business_connection_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    inline_message_id=inline_message_id,
                    reply_markup=reply_markup,
                    request_timeout=request_timeout,
                )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in edit_message_reply_markup...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in edit_message_reply_markup in a row...")

    async def edit_message_text(
        self,
        text: str,
        business_connection_id: typing.Optional[str] = None,
        chat_id: typing.Union[int, str, None] = None,
        message_id: typing.Optional[int] = None,
        inline_message_id: typing.Optional[str] = None,
        parse_mode: typing.Union[str, Default, None] = Default("parse_mode"),
        entities: typing.Optional[typing.List[types.MessageEntity]] = None,
        link_preview_options: typing.Union[typing.Any, Default, None] = Default("link_preview"),
        reply_markup: typing.Union[types.InlineKeyboardMarkup, None] = None,
        disable_web_page_preview: typing.Union[bool, Default, None] = Default("link_preview_is_disabled"),
        request_timeout: typing.Optional[int] = None,
    ) -> typing.Union[types.Message, bool]:
        for t in TIMEOUTS:
            try:
                return await super().edit_message_text(
                    text=text,
                    business_connection_id=business_connection_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    inline_message_id=inline_message_id,
                    parse_mode=parse_mode,
                    entities=entities,
                    link_preview_options=link_preview_options,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    request_timeout=request_timeout,
                    )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in edit_message_text...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in edit_message_text in a row...")

    async def forward_message(
        self,
        chat_id: typing.Union[int, str],
        from_chat_id: typing.Union[int, str],
        message_id: int,
        message_thread_id: typing.Optional[int] = None,
        direct_messages_topic_id: typing.Optional[int] = None,
        video_start_timestamp: typing.Optional[typing.Any] = None,
        disable_notification: typing.Optional[bool] = None,
        protect_content: typing.Union[bool, Default, None] = Default("protect_content"),
        message_effect_id: typing.Optional[str] = None,
        suggested_post_parameters: typing.Optional[typing.Any] = None,
        request_timeout: typing.Optional[int] = None,
    ) -> types.Message:
        for t in TIMEOUTS:
            try:
                return await super().forward_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                    message_thread_id=message_thread_id,
                    direct_messages_topic_id=direct_messages_topic_id,
                    video_start_timestamp=video_start_timestamp,
                    disable_notification=disable_notification,
                    protect_content=protect_content,
                    message_effect_id=message_effect_id,
                    suggested_post_parameters=suggested_post_parameters,
                    request_timeout=request_timeout,
                    )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in forward_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in forward_message in a row...")

    async def send_message(
        self,
        chat_id: typing.Union[int, str],
        text: str,
        business_connection_id: typing.Optional[str] = None,
        message_thread_id: typing.Optional[int] = None,
        direct_messages_topic_id: typing.Optional[int] = None,
        parse_mode: typing.Union[str, Default, None] = Default("parse_mode"),
        entities: typing.Optional[typing.List[types.MessageEntity]] = None,
        link_preview_options: typing.Union[typing.Any, Default, None] = Default("link_preview"),
        disable_notification: typing.Optional[bool] = None,
        protect_content: typing.Union[bool, Default, None] = Default("protect_content"),
        allow_paid_broadcast: typing.Optional[bool] = None,
        message_effect_id: typing.Optional[str] = None,
        suggested_post_parameters: typing.Optional[typing.Any] = None,
        reply_parameters: typing.Optional[typing.Any] = None,
        reply_markup: typing.Union[
            types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove, types.ForceReply, None] = None,
        allow_sending_without_reply: typing.Optional[bool] = None,
        disable_web_page_preview: typing.Union[bool, Default, None] = Default("link_preview_is_disabled"),
        reply_to_message_id: typing.Optional[int] = None,
        request_timeout: typing.Optional[int] = None,
    ) -> types.Message:
        for t in TIMEOUTS:
            try:
                await rate_lim(chat_id)
                # logger.warning(f'{chat_id=} {text=}')
                return await super().send_message(
                    chat_id=chat_id,
                    text=text,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    direct_messages_topic_id=direct_messages_topic_id,
                    parse_mode=parse_mode,
                    entities=entities,
                    link_preview_options=link_preview_options,
                    disable_notification=disable_notification,
                    protect_content=protect_content,
                    allow_paid_broadcast=allow_paid_broadcast,
                    message_effect_id=message_effect_id,
                    suggested_post_parameters=suggested_post_parameters,
                    reply_parameters=reply_parameters,
                    reply_markup=reply_markup,
                    allow_sending_without_reply=allow_sending_without_reply,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_to_message_id=reply_to_message_id,
                    request_timeout=request_timeout,
                    )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in send_message...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in send_message in a row...")
            except TelegramRetryAfter as e:
                logger.error(':( RetryAfter in send_message...')
                await asyncio.sleep(2)
                raise asyncio.TimeoutError("The RetryAfter in send_message in a row...")

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: typing.Optional[str] = None,
        show_alert: typing.Optional[bool] = None,
        url: typing.Optional[str] = None,
        cache_time: typing.Optional[int] = None,
        request_timeout: typing.Optional[int] = None,
    ) -> bool:
        for t in TIMEOUTS:
            try:
                return await super().answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=text,
                    show_alert=show_alert,
                    url=url,
                    cache_time=cache_time,
                    request_timeout=request_timeout,
                )
            except asyncio.TimeoutError as e:
                logger.error(':( TimeoutError in answer_callback_query...')
                if t:
                    await asyncio.sleep(t)
                else:
                    raise asyncio.TimeoutError("The TimeoutError in answer_callback_query in a row...")


# Запускаем API телеграм-бота
bot = BotIg(
    config.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=AiohttpSession(timeout=5),
)
router = Router()
dispatcher = Dispatcher()
dispatcher.include_router(router)


async def capture_aiogram_error(event: ErrorEvent, bot: Bot) -> None:
    if sentry_sdk is None:
        return
    update = getattr(event, "update", None)
    with sentry_sdk.push_scope() as scope:
        if update is not None:
            scope.set_tag("update_type", getattr(update, "event_type", "unknown"))
            scope.set_extra("update_id", getattr(update, "update_id", None))
            user = getattr(update, "event_from_user", None)
            if user is not None:
                scope.set_user(
                    {
                        "id": user.id,
                        "username": user.username,
                    }
                )
        sentry_sdk.capture_exception(event.exception)


dispatcher.errors.register(capture_aiogram_error)

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

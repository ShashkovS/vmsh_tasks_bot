# -*- coding: utf-8 -*-
import asyncio
import logging
from random import uniform

from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from helpers.config import config, logger, DEBUG
from helpers.bot import bot, dispatcher, router, group_router
from helpers.shutdown import wait_for_valuable_tasks
from helpers.trace import init_trace
from helpers.trace_middleware import TraceMessageMiddleware, TraceCallbackMiddleware
import db_methods as db
from models.spreadsheets import google_spreadsheet_loader, update_from_google_if_db_is_empty
from handlers.student_handlers import register_group_switch_commands
import handlers

USE_WEBHOOKS = False
WEBHOOK_URL = None
WEBHOOK_PATH = None
_TRACE_MIDDLEWARES_READY = False


def setup_trace_middlewares():
    global _TRACE_MIDDLEWARES_READY
    if _TRACE_MIDDLEWARES_READY:
        return
    message_middleware = TraceMessageMiddleware()
    callback_middleware = TraceCallbackMiddleware()
    router.message.middleware(message_middleware)
    router.callback_query.middleware(callback_middleware)
    group_router.message.middleware(message_middleware)
    group_router.callback_query.middleware(callback_middleware)
    _TRACE_MIDDLEWARES_READY = True


async def check_webhook():
    logger.debug('check_webhook')
    # Ждём слуайное время от 0 до 2 секунд. Чтобы несколько worker'ов не пытались получить хук одновременно
    # TODO сделать через блокировку в базе
    await asyncio.sleep(uniform(0, 5))
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def log_bot_name(username):
    await asyncio.sleep(1)
    logger.info(f'Бот начал свою работу: https://t.me/{username}')


async def on_startup(bot: Bot, **_kwargs):
    logger.warning('bot on_startup')
    logger.debug(f'{handlers}')

    # Настраиваем БД
    db.sql.setup(config.db_filename)
    init_trace(config)
    setup_trace_middlewares()

    # Настраиваем загрузчик из гугль-таблиц
    google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
    # Подгружаем данные, если база пуста
    update_from_google_if_db_is_empty()
    register_group_switch_commands()

    if USE_WEBHOOKS:
        await check_webhook()

    bot.username = (await bot.get_me()).username

    await bot.post_logging_message(f'Бот начал свою работу')
    asyncio.create_task(log_bot_name(bot.username))


async def on_shutdown(bot: Bot, **_kwargs):
    """
    Graceful shutdown.
    """
    logger.warning('bot on_shutdown')
    # Remove webhook.
    if USE_WEBHOOKS:
        await bot.delete_webhook()
    # Отключаемся от гугль-таблицы (если вдруг коннект ещё жив)
    google_spreadsheet_loader.close()
    # Пишем, что останавливаемся
    await bot.post_logging_message('Бот остановил свою работу')
    await wait_for_valuable_tasks(logger, timeout=20)
    # Close all connections.
    # Здесь какая-то ерунда, зачем-то выводится вот такое предупреждение:
    # https://github.com/aiogram/aiogram/blob/a852b9559612e3b9d542588a4539e64c50393a9c/aiogram/bot/base.py#L208
    if bot.session:
        await bot.session.close()
    storage = getattr(dispatcher, "storage", None)
    if storage:
        await storage.close()
        if hasattr(storage, "wait_closed"):
            await storage.wait_closed()
    if __name__ == "__main__":
        db.sql.disconnect()
    logger.warning('bot Bye!')


def start_bot_in_polling_mode():
    global USE_WEBHOOKS
    USE_WEBHOOKS = False
    # Включаем все отладочные сообщения
    logger.setLevel(DEBUG)
    logging.getLogger('aiogram').setLevel(DEBUG)


def _build_webhook_path():
    parts = [part for part in (config.webhook_path, config.telegram_bot_token) if part]
    cleaned = [part.strip('/') for part in parts]
    return "/" + "/".join(cleaned)


def setup_tgbot_webhook(app: web.Application):
    global USE_WEBHOOKS, WEBHOOK_URL, WEBHOOK_PATH
    USE_WEBHOOKS = True
    WEBHOOK_PATH = _build_webhook_path()
    WEBHOOK_URL = f"https://{config.webhook_host}:{config.webhook_port}{WEBHOOK_PATH}"

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dispatcher, bot=bot)
    logger.info(f"Webhook установлен по пути: {WEBHOOK_PATH}")


async def run_tg_bot_in_polling_mode():
    global USE_WEBHOOKS
    USE_WEBHOOKS = False
    await bot.delete_webhook(drop_pending_updates=False)
    await dispatcher.start_polling(bot)


def start_bot_in_webhook_mode(app):
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    setup_tgbot_webhook(app)


def configue(app):
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)


if __name__ == "__main__":
    app = web.Application()
    configue(app)
    start_bot_in_polling_mode()
    # В режиме отладки запускаем без вебхуков
    asyncio.run(run_tg_bot_in_polling_mode())

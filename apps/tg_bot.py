# -*- coding: utf-8 -*-
import logging
from aiogram.dispatcher.webhook import configure_app, web
from aiogram.utils.executor import start_polling
import asyncio
from random import uniform

import handlers
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
from helpers.obj_classes import db, update_from_google_if_db_is_empty
from helpers.config import config, logger, DEBUG
from helpers.bot import bot, dispatcher

USE_WEBHOOKS = False
routes = None


async def check_webhook():
    logger.debug('check_webhook')
    # Ждём слуайное время от 0 до 2 секунд. Чтобы несколько worker'ов не пытались получить хук одновременно
    # TODO сделать через блокировку в базе
    await asyncio.sleep(uniform(0, 2))
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def on_startup(app):
    logger.warning('bot on_startup')
    logger.debug(f'{handlers}')

    # Настраиваем БД
    db.setup(config.db_filename)

    # Настраиваем загрузчик из гугль-таблиц
    google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
    # Подгружаем данные, если база пуста
    update_from_google_if_db_is_empty()

    if USE_WEBHOOKS:
        await check_webhook()
    bot.username = (await bot.me).username

    await bot.post_logging_message(f'Бот начал свою работу')


async def on_shutdown(app):
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
    # Завершаем, если вдруг что-то ещё живо
    all_async_tasks_but_current = list(asyncio.all_tasks() - {asyncio.current_task()})
    for i in range(len(all_async_tasks_but_current) - 1, -1, -1):
        task = all_async_tasks_but_current[i]
        coro_name = task.get_coro().__qualname__
        # TODO Это, конечно, отстой... Но хз, как сделать лучше
        if 'start_polling' in coro_name or 'Client._' in coro_name or 'Subscription._' in coro_name:
            all_async_tasks_but_current.pop(i)
        else:
            logger.warning(f'Pending task: {task.get_coro().__qualname__}')
    if all_async_tasks_but_current:
        await asyncio.wait(all_async_tasks_but_current, timeout=20)
    # Close all connections.
    # Здесь какая-то ерунда, зачем-то выводится вот такое предупреждение:
    # https://github.com/aiogram/aiogram/blob/a852b9559612e3b9d542588a4539e64c50393a9c/aiogram/bot/base.py#L208
    if bot._session:
        await bot._session.close()
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    if __name__ == "__main__":
        db.disconnect()
    logger.warning('Bye!')


def start_bot_in_polling_mode():
    global USE_WEBHOOKS
    USE_WEBHOOKS = False
    # Включаем все отладочные сообщения
    logger.setLevel(DEBUG)
    logging.getLogger('aiogram').setLevel(DEBUG)
    from aiogram.contrib.middlewares.logging import LoggingMiddleware
    dispatcher.middleware.setup(LoggingMiddleware())
    # В режиме отладки запускаем без вебхуков
    start_polling(dispatcher, on_startup=on_startup, on_shutdown=on_shutdown)


def start_bot_in_webhook_mode(app):
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    global USE_WEBHOOKS, WEBHOOK_URL
    USE_WEBHOOKS = True
    WEBHOOK_URL = "https://{}:{}/{}/".format(config.webhook_host, config.webhook_port, config.telegram_bot_token)
    configure_app(app.dispatcher, app, path='/{token}/', route_name='telegram_webhook_handler')

    # app will be started by gunicorn, so no need to start_webhook
    # start_webhook(
    #     dispatcher=dispatcher,
    #     webhook_path='/',
    #     on_startup=on_startup,
    #     on_shutdown=on_shutdown,
    #     host=config.webhook_host,
    #     port=config.webhook_port,
    # )


def configue(app):
    app.dispatcher = dispatcher
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    app = web.Application()
    configue(app)
    start_bot_in_polling_mode()

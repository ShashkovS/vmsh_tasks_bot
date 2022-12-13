# -*- coding: utf-8 -*-
from aiogram.dispatcher.webhook import web
import asyncio

import apps
from helpers.config import config, logger
from db_methods import db


async def on_startup(app):
    logger.warning('Start up!')
    # Настраиваем БД
    db.setup(config.db_filename)


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.debug('on_shutdown')
    logger.warning('Shutting down..')
    all_async_tasks_but_current = list(asyncio.all_tasks() - {asyncio.current_task()})
    logger.warning(f'Tasks to wait: {all_async_tasks_but_current!r}')
    if all_async_tasks_but_current:
        await asyncio.wait(all_async_tasks_but_current, timeout=20)
    db.disconnect()
    logger.warning('Bye!')


if __name__ == "__main__":
    # В режиме отладки запускаем в режиме long polling, соответственно у нас нет web-приложений, только голый бот
    apps.tg_bot.start_bot_in_polling_mode()
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    app = web.Application()
    # Важно, что текущий on_startup первый
    app.on_startup.append(on_startup)
    # Теперь настраиваем все модули
    for module in apps.all_apps:
        module.configue(app)
    # Важно, что текущий on_shutdown — последний
    app.on_shutdown.append(on_shutdown)
    # Ну всё, можно делать заключительные приготовления
    apps.tg_bot.start_bot_in_webhook_mode(app)

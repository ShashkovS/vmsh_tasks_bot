# -*- coding: utf-8 -*-
from aiogram.dispatcher.webhook import web
import asyncio

import apps
from helpers.config import config, logger
import db_methods as db


async def on_startup(app):
    logger.warning('MainApp Start up!')
    # Настраиваем БД
    db.sql.setup(config.db_filename)


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.warning('on_shutdown')
    logger.warning('MainApp Shutting down..')
    # К этому моменту все задания уже должны быть закончены. Поэтому закрываем прямо всё
    all_async_tasks_but_current = list(asyncio.all_tasks() - {asyncio.current_task()})
    logger.warning(f'Tasks to wait: {all_async_tasks_but_current!r}')
    if all_async_tasks_but_current:
        await asyncio.wait(all_async_tasks_but_current, timeout=20)
    db.disconnect()
    logger.warning('MainApp Bye!')


if __name__ == "__main__":
    # В режиме отладки запускаем в режиме long polling, соответственно у нас нет web-приложений, только голый бот
    apps.tg_bot.start_bot_in_polling_mode()
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    app = web.Application()
    # Важно, что текущие on_startup и on_shutdown первые. Мы потом развернём список on_shutdown в обратном порядке
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    # Теперь настраиваем все модули
    for module in apps.all_apps:
        module.configue(app)
    # Обращаем on_shutdown, чтобы приложения закрывались в правильном порядке
    app.on_shutdown[:] = app.on_shutdown[::-1]
    # Ну всё, можно делать заключительные приготовления
    apps.tg_bot.start_bot_in_webhook_mode(app)

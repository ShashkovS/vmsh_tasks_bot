# -*- coding: utf-8 -*-
from aiogram.dispatcher.webhook import web
import asyncio

import apps
from helpers.config import config, logger
import db_methods as db
from helpers.features import set_features
from helpers.msg_texts import msgs

LOCAL_APP_PORT = 8179


async def on_startup(app):
    logger.warning('MainApp Start up!')
    # Настраиваем БД
    db.sql.setup(config.db_filename)
    bot_settings = db.settings.get_settings()
    config.update_from_dict(bot_settings)
    set_features(config)
    ui_messages = db.settings.get_ui_messages()
    msgs.update_from_dict(ui_messages)


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
    # Останавливаем sympy-воркера (если он был запущен)
    from helpers.checkers import worker
    worker.shutdown()
    db.sql.disconnect()
    logger.warning('MainApp Bye!')


def prepare_app():
    app = web.Application()
    # Важно, что текущие on_startup и on_shutdown первые. Мы потом развернём список on_shutdown в обратном порядке
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    # Теперь настраиваем все модули
    for module in apps.all_apps:
        module.configue(app)
    # Обращаем on_shutdown, чтобы приложения закрывались в правильном порядке
    app.on_shutdown[:] = app.on_shutdown[::-1]
    if __name__ == '__main__':
        url_prefix = f'http://127.0.0.1:{LOCAL_APP_PORT}'
    else:
        url_prefix = f'https://{config.webhook_host}'
    logger.info('Routes:')
    for route in app.router.routes():
        logger.info(f'{route.method}: {url_prefix}{route.resource.canonical}')
        print(f'{route.method}: {url_prefix}{route.resource.canonical}')

    return app


app = prepare_app()
if __name__ == "__main__":
    # Start aiohttp server
    apps.tg_bot.start_bot_in_polling_mode()
    webapp_task = asyncio.create_task(web.run_app(app, port=LOCAL_APP_PORT))
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    # Ну всё, можно делать заключительные приготовления
    apps.tg_bot.start_bot_in_webhook_mode(app)

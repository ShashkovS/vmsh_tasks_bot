# -*- coding: utf-8 -*-
import asyncio
from contextlib import suppress

from aiohttp import web

import apps
from helpers.config import config, logger
import db_methods as db
from helpers.features import set_features
from helpers.msg_texts import msgs
from helpers.shutdown import wait_for_valuable_tasks

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
    await wait_for_valuable_tasks(logger, timeout=20)
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
        if hasattr(apps, "tg_bot"):
            apps.tg_bot.setup_tgbot_webhook(app)
        url_prefix = f'https://{config.webhook_host}'
    logger.info('Routes:')
    for route in app.router.routes():
        logger.info(f'{route.method}: {url_prefix}{route.resource.canonical}')
        print(f'{route.method}: {url_prefix}{route.resource.canonical}')

    return app


app = prepare_app()
if __name__ == "__main__":
    # Start aiohttp server
    async def dev_main():
        apps.tg_bot.start_bot_in_polling_mode()

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="127.0.0.1", port=LOCAL_APP_PORT)
        await site.start()
        logger.info(f"Веб-сервер запущен на порту {LOCAL_APP_PORT}")

        polling_task = asyncio.create_task(apps.tg_bot.run_tg_bot_in_polling_mode())
        try:
            await asyncio.Event().wait()
        finally:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task
            await runner.cleanup()

    try:
        asyncio.run(dev_main())
    except KeyboardInterrupt:
        pass
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    # Ну всё, можно делать заключительные приготовления
    pass

# -*- coding: utf-8 -*-
import logging
from aiogram.dispatcher.webhook import configure_app, web
from aiogram.utils.executor import start_polling
from helpers.config import config, logger, DEBUG
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
from helpers.obj_classes import db, update_from_google_if_db_is_empty
from helpers.bot import bot, dispatcher
import handlers

USE_WEBHOOKS = False


async def check_webhook():
    logger.debug('check_webhook')
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def on_startup(app):
    logger.debug('on_startup')
    logger.debug(f'{handlers}')
    logger.warning('Start up!')

    # Настраиваем БД
    db.setup(config.db_filename)
    # Настраиваем загрузчик из гугль-таблиц
    google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
    # Подгружаем данные, если база пуста
    update_from_google_if_db_is_empty()

    if USE_WEBHOOKS:
        await check_webhook()
    await bot.post_logging_message('Бот начал свою работу')


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.debug('on_shutdown')
    logger.warning('Shutting down..')
    await bot.post_logging_message('Бот остановил свою работу')
    # Remove webhook.
    await bot.delete_webhook()
    # Close all connections.
    # await bot.close()
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    db.disconnect()
    logger.warning('Bye!')


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    logger.setLevel(DEBUG)
    logging.getLogger('aiogram').setLevel(DEBUG)
    from aiogram.contrib.middlewares.logging import LoggingMiddleware

    dispatcher.middleware.setup(LoggingMiddleware())
    # В режиме отладки запускаем без вебхуков
    start_polling(dispatcher, on_startup=on_startup, on_shutdown=on_shutdown)
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    USE_WEBHOOKS = True
    WEBHOOK_URL = "https://{}:{}/{}/".format(config.webhook_host, config.webhook_port, config.telegram_bot_token)
    # Create app
    app = web.Application()
    app.dispatcher = dispatcher
    configure_app(dispatcher, app, path='/{token}/', route_name='telegram_webhook_handler')
    # Setup event handlers.
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # app will be started by gunicorn, so no need to start_webhook
    # start_webhook(
    #     dispatcher=dispatcher,
    #     webhook_path='/',
    #     on_startup=on_startup,
    #     on_shutdown=on_shutdown,
    #     host=config.webhook_host,
    #     port=config.webhook_port,
    # )

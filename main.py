# -*- coding: utf-8 -*-
import logging
from aiogram.dispatcher.webhook import configure_app, web
from aiogram.utils.executor import start_polling
import asyncio
from aiohttp import WSCloseCode
from random import uniform
import handlers
import zoom_events_parser
import tags_service
import web_app
import game_web_app

from helpers.config import config, logger, DEBUG
from helpers.loader_from_google_spreadsheets import google_spreadsheet_loader
from helpers.obj_classes import db, update_from_google_if_db_is_empty
from helpers.bot import bot, dispatcher
from helpers.nats_brocker import vmsh_nats
from helpers.consts import NATS_GAME_MAP_UPDATE, NATS_GAME_STUDENT_UPDATE

USE_WEBHOOKS = False


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
    bot.username = (await bot.me).username

    # Подключаемся к NATS
    await vmsh_nats.setup()
    await vmsh_nats.subscribe(NATS_GAME_MAP_UPDATE, game_web_app.nats_handle_map_update)
    await vmsh_nats.subscribe(NATS_GAME_STUDENT_UPDATE, game_web_app.nats_handle_student_update)

    await bot.post_logging_message(f'Бот начал свою работу')


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.debug('on_shutdown')
    logger.warning('Shutting down..')
    # Remove webhook.
    await bot.delete_webhook()
    # Пишем, что останавливаемся
    await bot.post_logging_message('Бот остановил свою работу')
    # Останавливаем все websocket'ы
    for user_id, websockets in game_web_app.user_id_to_websocket.items():
        for ws in set(websockets):
            ref = ws()
            if ref:
                await ref.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown')
    # Завершаем, если вдруг что-то ещё живо
    if USE_WEBHOOKS:
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
    # Close all connections.
    # Здесь какая-то ерунда, зачем-то выводится вот такое предупреждение:
    # https://github.com/aiogram/aiogram/blob/a852b9559612e3b9d542588a4539e64c50393a9c/aiogram/bot/base.py#L208
    if bot._session:
        await bot._session.close()
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    await vmsh_nats.disconnect()
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
    # Дополнительные хендлеры
    app.add_routes(zoom_events_parser.routes)
    app.add_routes(tags_service.routes)
    app.add_routes(web_app.routes)
    app.add_routes(game_web_app.routes)
    # app will be started by gunicorn, so no need to start_webhook
    # start_webhook(
    #     dispatcher=dispatcher,
    #     webhook_path='/',
    #     on_startup=on_startup,
    #     on_shutdown=on_shutdown,
    #     host=config.webhook_host,
    #     port=config.webhook_port,
    # )

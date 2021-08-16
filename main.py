# -*- coding: utf-8 -*-
import logging
from aiogram.dispatcher.webhook import configure_app, web
from aiogram.utils.executor import start_polling
from config import DEBUG
from loader_from_google_spreadsheets import google_spreadsheet_loader
from obj_classes import User, db, FromGoogleSpreadsheet
from bot import *

if config.production_mode:
    logger.info(('*' * 50 + '\n') * 5)
    logger.info('Production mode')
    logger.info('*' * 50)
else:
    logger.info('Developer mode')

USE_WEBHOOKS = False


async def check_webhook():
    logger.debug('check_webhook')
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def on_startup(dispatcher):
    logger.debug('on_startup')
    logger.warning('Start up!')

    if USE_WEBHOOKS:
        await check_webhook()
    await bot_post_logging_message('Бот начал свою работу')


async def on_shutdown(dispatcher):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.debug('on_shutdown')
    logger.warning('Shutting down..')
    await bot_post_logging_message('Бот остановил свою работу')
    # Remove webhook.
    await bot.delete_webhook()
    # Close all connections.
    await bot.close()
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    db.disconnect()
    logger.warning('Bye!')


# Настраиваем БД
db.setup(config.db_filename)
# Настраиваем загрузчик из гугль-таблиц
google_spreadsheet_loader.setup(config.dump_filename, config.google_sheets_key, config.google_cred_json)

# Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы (иначе даже админ не сможет залогиниться)
all_teachers = list(User.all_teachers())
if len(all_teachers) == 0:
    FromGoogleSpreadsheet.update_all()
    all_teachers = list(User.all_teachers())
logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')

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

"""
Для студентов
start — 
sos — 
exit_waitlist — 
level_novice — 
level_pro — 

Для учителей
set_level
recheck

Для админов
broadcast
reset_state
set_sleep_state
update_all
update_teachers
update_problems
update_students
stat
"""

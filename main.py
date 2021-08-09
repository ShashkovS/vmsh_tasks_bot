# -*- coding: utf-8 -*-
import logging
from aiogram.dispatcher import Dispatcher, filters
from aiogram.dispatcher.webhook import configure_app, types, web
from aiogram.utils.executor import start_polling
from config import config, logger, DEBUG
from loader_from_google_spreadsheets import google_spreadsheet_loader
from db_methods import db
from message_handlers import *
from mh_for_admin import *
from bot import *

if config.production_mode:
    logger.info(('*' * 50 + '\n') * 5)
    logger.info('Production mode')
    logger.info('*' * 50)
else:
    logger.info('Developer mode')

USE_WEBHOOKS = False

callbacks_processors = {
    CALLBACK_PROBLEM_SELECTED: prc_problems_selected_callback,
    CALLBACK_SHOW_LIST_OF_LISTS: prc_show_list_of_lists_callback,
    CALLBACK_LIST_SELECTED: prc_list_selected_callback,
    CALLBACK_ONE_OF_TEST_ANSWER_SELECTED: prc_one_of_test_answer_selected_callback,
    CALLBACK_GET_QUEUE_TOP: prc_get_queue_top_callback,
    CALLBACK_INS_ORAL_PLUSSES: prc_ins_oral_plusses,
    CALLBACK_SET_VERDICT: prc_set_verdict_callback,
    CALLBACK_CANCEL_TASK_SUBMISSION: prc_cancel_task_submission_callback,
    CALLBACK_GET_WRITTEN_TASK: prc_get_written_task_callback,
    CALLBACK_TEACHER_CANCEL: prc_teacher_cancel_callback,
    CALLBACK_WRITTEN_TASK_SELECTED: prc_written_task_selected_callback,
    CALLBACK_WRITTEN_TASK_OK: prc_written_task_ok_callback,
    CALLBACK_WRITTEN_TASK_BAD: prc_written_task_bad_callback,
    CALLBACK_GET_OUT_OF_WAITLIST: prc_get_out_of_waitlist_callback,
    CALLBACK_ADD_OR_REMOVE_ORAL_PLUS: prc_add_or_remove_oral_plus_callback,
    CALLBACK_FINISH_ORAL_ROUND: prc_finish_oral_round_callback,
    CALLBACK_STUDENT_SELECTED: prc_student_selected_callback,
}


async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    logger.debug('inline_kb_answer_callback_handler')
    if query.message:
        user = User.get_by_chat_id(query.message.chat.id)
        if not user:
            try:
                await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
            except:
                pass  # Ошибки здесь не важны
            await start(query.message)
            return
        callback_type = query.data[0]
        callback_processor = callbacks_processors.get(callback_type, None)
        try:
            await callback_processor(query, user)
        except Exception as e:
            error_text = traceback.format_exc()
            logger.error(f'SUPERSHIT: {e}')
            await bot_post_logging_message(error_text)


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
    logger.warning('Start up!')
    if USE_WEBHOOKS:
        await check_webhook()

    # Для студентов
    dispatcher.register_message_handler(start, commands=['start'])
    dispatcher.register_message_handler(sos, commands=['sos'])
    dispatcher.register_message_handler(exit_waitlist, commands=['exit_waitlist'])
    dispatcher.register_message_handler(level_novice, commands=['level_novice'])
    dispatcher.register_message_handler(level_pro, commands=['level_pro'])

    # Для учителей
    dispatcher.register_message_handler(set_student_level, commands=['set_level'])
    dispatcher.register_message_handler(recheck, filters.RegexpCommandsFilter(regexp_commands=['recheck.*']))

    # Для админов
    dispatcher.register_message_handler(broadcast, commands=['broadcast_wibkn96x', 'broadcast'])
    dispatcher.register_message_handler(set_get_task_info_for_all_students, commands=['reset_state_jvcykgny', 'reset_state'])
    dispatcher.register_message_handler(set_sleep_state_for_all_students, commands=['set_sleep_state'])
    dispatcher.register_message_handler(update_all_internal_data, commands=['update_all_quaLtzPE', 'update_all'])
    dispatcher.register_message_handler(update_teachers, commands=['update_teachers'])
    dispatcher.register_message_handler(update_problems, commands=['update_problems'])
    dispatcher.register_message_handler(update_students, commands=['update_students'])
    dispatcher.register_message_handler(calc_last_lesson_stat, commands=['stat'])

    # Принимаем всё
    dispatcher.register_message_handler(process_regular_message, content_types=["any"])

    # Коллбеки
    dispatcher.register_callback_query_handler(inline_kb_answer_callback_handler)
    await bot_post_logging_message('Бот начал свою работу')


async def on_shutdown(app):
    logger.debug('on_shutdown')
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
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

# Если в базе нет ни одного учителя, то принудительно грузим всё из таблицы
all_teachers = list(User.all_teachers())
if len(all_teachers) == 0:
    FromGoogleSpreadsheet.update_all()
    all_teachers = list(User.all_teachers())
logger.info(f'В базе в текущий момент {len(all_teachers)} учителей')

# Запускаем API телеграм-бота
dispatcher = Dispatcher(bot)

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
    configure_app(dispatcher, app, path='/{token}/', route_name='telegram_webhook_handler')
    # Setup event handlers.
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    # app will be started by gunicorn

"""
Секретные команды для учителя:
/broadcast
/reset_stat
/recheck token problem
/update_all
/update_teachers
/update_problems
/set_sleep_state
/set_level
"""

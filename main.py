import logging
import os
import io
import datetime
from state_helper import *
from aiogram import Bot
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.webhook import configure_app, types, web
from aiogram.utils.executor import start_polling
import db_helper

logging.basicConfig(level=logging.INFO)

API_TOKEN = open('creds/telegram_bot_key').read().strip()
SOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solutions')
USE_WEBHOOKS = False

# Для каждого бота своя база
db_name = str(abs(hash(API_TOKEN))) + '.db'
db, users, problems = db_helper.init_db_and_objects(db_name)

# Запускаем API телеграм-бота
bot = Bot(API_TOKEN)
dispatcher = Dispatcher(bot)


async def start(message: types.Message):
    set_state(message.chat.id, START_DIALOG_STATE)
    set_state(message.chat.id, GET_USER_INFO_STATE)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль",
    )


async def update_all_internal_data(message: types.Message):
    global db, users, problems
    db, users, problems = db_helper.init_db_and_objects()
    await bot.send_message(
        chat_id=message.chat.id,
        text="Данные обновлены",
    )


async def prc_get_user_info_state(message: types.Message):
    user = users.get_by_token(message.text)
    if user is None:
        await bot.send_message(
            chat_id=message.chat.id,
            text="Неправильно, попробуйте еще раз. Пароль был вам выслан по электронной почте, он имеет вид «pa1ro1»",
        )
    else:
        print('user', user)
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"ОК, Добро пожаловать, {user.name} {user.surname}",
        )
        set_state(message.chat.id, GET_TASK_INFO_STATE)
        set_id(message.chat.id, user.id)
        await prc_get_task_info_state(message)


async def prc_WTF(message: types.Message):
    await bot.send_message(
        chat_id=message.chat.id,
        text="Всё сломалось, бот запутался в текущей ситации :(",
    )


def build_problems_keyboard(lesson_num: int):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for problem in problems.get_by_lesson(lesson_num):
        task_button = types.InlineKeyboardButton(
            text=f"{problem}",
            callback_data=f"t_{problem.id}"
        )
        keyboard_markup.add(task_button)
    to_lessons_button = types.InlineKeyboardButton(
        text="К списку всех листков",
        callback_data="a"
    )
    keyboard_markup.add(to_lessons_button)
    return keyboard_markup


def build_lessons_keyboard():
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for lesson in problems.get_all_lessons():
        lesson_button = types.InlineKeyboardButton(
            text=f"Листок {lesson}",
            callback_data=f"l_{lesson}",
        )
        keyboard_markup.add(lesson_button)
    return keyboard_markup


async def prc_get_task_info_state(message):
    await bot.send_message(
        chat_id=message.chat.id,
        text="Сейчас нужно выбрать задачу, которую Вы хотите отправить",
    )
    await bot.send_message(
        chat_id=message.chat.id,
        text="Вот задачи текущего листка:",
        reply_markup=build_problems_keyboard(problems.get_last_lesson()),
    )


async def prc_sending_solution_state(message: types.Message):
    downloaded = []
    text = message.text
    if text:
        downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
    for photo in message.photo:
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
        print(file_info, photo, filename)
    if message.document:
        file_id = message.document.file_id
        file_info = await bot.get_file(file_id)
        filename = message.document.file_name
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
        print(file_info, file_id, filename)
    for bin_data, filename in downloaded:
        ext = filename[filename.rfind('.') + 1:]
        file_name = os.path.join(SOLS_PATH, get_id(message.chat.id), *get_data(message.chat.id),
                                 datetime.datetime.now().isoformat().replace(':', '') + '.' + ext)
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        with open(file_name, 'wb') as file:
            file.write(bin_data.read())
    await bot.send_message(
        chat_id=message.chat.id,
        text="Принято на проверку"
    )
    set_state(message.chat.id, GET_TASK_INFO_STATE)
    await prc_get_task_info_state(message)


state_processors = {
    GET_USER_INFO_STATE: prc_get_user_info_state,
    GET_TASK_INFO_STATE: prc_get_task_info_state,
    SENDING_SOLUTION_STATE: prc_sending_solution_state,
}


async def process_regular_message(message: types.Message):
    cur_chat_state = get_state(message.chat.id)
    state_processor = state_processors.get(cur_chat_state, prc_WTF)
    await state_processor(message)


async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    print(query)
    if query.message:
        if query.data[0] == 't':
            await bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                                reply_markup=None)
            problem_id = int(query.data[2:])
            await bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text=f"Выбрана задача {problems.by_id(problem_id)}. Теперь отправьте фотографии или скан вашего решения.")
            set_state(query.message.chat.id, SENDING_SOLUTION_STATE, problem_id)
        elif query.data[0] == 'l':

            await bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text="Теперь выберите задачу")
            await bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                                reply_markup=build_problems_keyboard(query.data[2:]))
        elif query.data[0] == 'a':
            await bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text="Вот список всех листков:")
            await bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                                reply_markup=build_lessons_keyboard())


async def check_webhook():
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def on_startup(app):
    logging.warning('Start up!')
    if USE_WEBHOOKS:
        await check_webhook()
    dispatcher.register_message_handler(start, commands=['start'])
    dispatcher.register_message_handler(update_all_internal_data, commands=['update_all_quaLtzPE'])
    dispatcher.register_message_handler(process_regular_message, content_types=["photo", "document", "text"])
    dispatcher.register_callback_query_handler(inline_kb_answer_callback_handler)


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logging.warning('Shutting down..')
    # Remove webhook.
    await bot.delete_webhook()
    # Close all connections.
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    logging.warning('Bye!')


# Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
# А вот в режиме отладки можно запустить и без вебхуков
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    start_polling(dispatcher, on_startup=on_startup, on_shutdown=on_shutdown)
else:
    USE_WEBHOOKS = True
    WEBHOOK_HOST = 'vmshtasksbot.proj179.ru'
    WEBHOOK_PORT = 443
    WEBHOOK_URL = "https://{}:{}/{}/".format(WEBHOOK_HOST, WEBHOOK_PORT, API_TOKEN)
    # Create app
    app = web.Application()
    configure_app(dispatcher, app, path='/{token}/', route_name='telegram_webhook_handler')
    # Setup event handlers.
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # app will be started by gunicorn

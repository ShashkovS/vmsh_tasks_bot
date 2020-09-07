import telebot
import logging
import tasks_helper
import os
from state_helper import *

# logger = telebot.logger
# telebot.logger.setLevel(logging.DEBUG)  # Outputs debug messages to console.

key = open('creds/telegram_bot_key').read().strip()
bot = telebot.TeleBot(key)
del key


@bot.message_handler(commands=['start'])
def start(message):
    set_state(message.chat.id, START_DIALOG_STATE)
    bot.send_message(message.chat.id, "Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введи свой пароль")
    set_state(message.chat.id, GETTING_USER_INFO_STATE)


@bot.message_handler(commands=['update_all_quaLtzPE'])
def update_all(message):
    tasks_helper.build_lesson_list()
    bot.send_message(message.chat.id, "Данные обновлены")


@bot.message_handler(func=lambda message: get_state(message.chat.id) == GETTING_USER_INFO_STATE)
def get_pass(message):
    if message.text == "qwerty":
        bot.send_message(message.chat.id, "ОК, Добро пожаловать, Акакий Акакиевич")
        set_state(message.chat.id, GETTING_TASK_INFO_STATE)
        set_id(message.chat.id, message.text)
        get_task(message)
    else:
        bot.send_message(message.chat.id, "Неправильно, попробуйте еще раз")


def build_lessons_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()

    for lesson in tasks_helper.get_all_lessons():
        lesson_button = telebot.types.InlineKeyboardButton(text="Листок {}".format(lesson.number),
                                                           callback_data='l_{}'.format(lesson.number))
        keyboard.add(lesson_button)
    return keyboard


def build_tasks_keyboard(lesson_num: int):
    keyboard = telebot.types.InlineKeyboardMarkup()
    for task in tasks_helper.get_lesson_tasks(lesson_num):
        task_button = telebot.types.InlineKeyboardButton(text="{}".format(task),
                                                         callback_data="t_({},{})".format(lesson_num, task.name))
        keyboard.add(task_button)
    to_lessons = telebot.types.InlineKeyboardButton(text="К списку всех листков", callback_data="a")
    keyboard.add(to_lessons)
    return keyboard


@bot.message_handler(func=lambda message: get_state(message.chat.id) == GETTING_TASK_INFO_STATE)
def get_task(message):
    bot.send_message(message.chat.id, "Сейчас нужно выбрать задачу, которую Вы хотите отправить")
    bot.send_message(message.chat.id, "Вот задачи последнего листка:",
                     reply_markup=build_tasks_keyboard(tasks_helper.get_last_lesson()))


@bot.callback_query_handler(lambda call: True)
def callback_query_tasks(call):
    if call.message:
        if call.data[0] == 't':
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          reply_markup=None)
            task_id = call.data[3:-1].split(',')
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Выбрана задача {}. Теперь отправьте фотографии или скан вашего решения.".
                                  format(tasks_helper.get_task(*task_id)))
            set_state(call.message.chat.id, SENDING_PHOTO_STATE, task_id)
        elif call.data[0] == 'l':

            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Теперь выберите задачу")
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          reply_markup=build_tasks_keyboard(call.data[2:]))
        elif call.data[0] == 'a':
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вот список всех листков:")
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          reply_markup=build_lessons_keyboard())


@bot.message_handler(func=lambda message: get_state(message.chat.id) == SENDING_PHOTO_STATE,
                     content_types=["document"])
def get_solution_file(message):
    file_info = bot.get_file(message.document.file_id)
    # print(message.document.file_name)
    downloaded_file = bot.download_file(file_info.file_path)
    file_name = "solutions/{}/{}/{}/{}".format(get_id(message.chat.id), *get_data(message.chat.id),
                                               message.document.file_name)
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'wb') as file:
        file.write(downloaded_file)
    bot.send_message(message.chat.id, "Принято на проверку")
    set_state(message.chat.id, GETTING_TASK_INFO_STATE)
    get_task(message)


@bot.message_handler(func=lambda message: get_state(message.chat.id) == SENDING_PHOTO_STATE,
                     content_types=["photo"])
def get_solution_photo(message):
    file_info = bot.get_file(message.photo[0].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_name = "solutions/{}/{}/{}/1.png".format(get_id(message.chat.id), *get_data(message.chat.id))
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'wb') as file:
        file.write(downloaded_file)
    bot.send_message(message.chat.id, "Принято на проверку")
    set_state(message.chat.id, GETTING_TASK_INFO_STATE)
    get_task(message)


@bot.message_handler(func=lambda message: get_state(message.chat.id) == SENDING_PHOTO_STATE,
                     content_types=["text"])
def get_solution_text(message):
    file_name = "solutions/{}/{}/{}/1.txt".format(get_id(message.chat.id), *get_data(message.chat.id))
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'w') as file:
        file.write(message.text)
    bot.send_message(message.chat.id, "Принято на проверку")
    set_state(message.chat.id, GETTING_TASK_INFO_STATE)
    get_task(message)


@bot.message_handler()
def what(message):
    print("WTF")
    print(message)


if __name__ == "__main__":
    print(os.getcwd())
    bot.infinity_polling()

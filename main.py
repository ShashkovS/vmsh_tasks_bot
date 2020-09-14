# -*- coding: utf-8 -*-
import logging
import os
import io
import datetime
import db_helper
import hashlib
import re
import asyncio
from consts import *
import aiogram
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.webhook import configure_app, types, web
from aiogram.utils.executor import start_polling
from aiogram.utils.exceptions import MessageNotModified

logging.basicConfig(level=logging.INFO)

if os.environ.get('PROD', None) == 'true':
    logging.info('*' * 50)
    logging.info('Production mode')
    logging.info('*' * 50)
    API_TOKEN = open('creds_prod/telegram_bot_key_prod').read().strip()
    WEBHOOK_HOST = 'vmsh179bot.proj179.ru'
    WEBHOOK_PORT = 443
else:
    logging.info('Developer mode')
    API_TOKEN = open('creds/telegram_bot_key').read().strip()
    WEBHOOK_HOST = 'vmshtasksbot.proj179.ru'
    WEBHOOK_PORT = 443
SOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solutions')
USE_WEBHOOKS = False

# Для каждого бота своя база
db_name = hashlib.md5(API_TOKEN.encode('utf-8')).hexdigest() + '.db'
db, users, problems, states = db_helper.init_db_and_objects(db_name)

# Запускаем API телеграм-бота
bot = aiogram.Bot(API_TOKEN)
dispatcher = Dispatcher(bot)


async def bot_edit_message_text(*args, **kwargs):
    try:
        await bot.edit_message_text(*args, **kwargs)
    except MessageNotModified as e:
        logging.error(f'SHIT: {e}')


async def bot_edit_message_reply_markup(*args, **kwargs):
    try:
        await bot.edit_message_reply_markup(*args, **kwargs)
    except MessageNotModified as e:
        logging.error(f'SHIT: {e}')


async def bot_answer_callback_query(*args, **kwargs):
    try:
        await bot.answer_callback_query(*args, **kwargs)
    except Exception as e:
        logging.error(f'SHIT: {e}')


async def update_all_internal_data(message: types.Message):
    global db, users, problems, states
    db, users, problems, states = db_helper.init_db_and_objects(db_name, refresh=True)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Данные обновлены",
    )


async def prc_get_user_info_state(message: types.Message, user: db_helper.User):
    user = users.get_by_token(message.text)
    if user is None:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🔁 Неправильно, попробуйте еще раз. Пароль был вам выслан по электронной почте, он имеет вид «pa1ro1»",
        )
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"🤖 ОК, Добро пожаловать, {user.name} {user.surname}",
        )
        users.set_chat_id(user, message.chat.id)
        states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        await process_regular_message(message)


async def prc_WTF(message: types.Message, user: db_helper.User):
    await bot.send_message(
        chat_id=message.chat.id,
        text="☢️ Всё сломалось, бот запутался в текущей ситации :(. Начнём сначала!",
    )
    logging.error(f"prc_WTF: {user!r} {message!r}")
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


def build_problems_keyboard(lesson_num: int, user: db_helper.User):
    solved = db.check_student_solved(user.id, lesson_num)
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for problem in problems.get_by_lesson(lesson_num):
        tick = '✅' if problem.id in solved else '⬜'
        task_button = types.InlineKeyboardButton(
            text=f"{tick} {problem}",
            callback_data=f"{CALLBACK_PROBLEM_SELECTED}_{problem.id}"
        )
        keyboard_markup.add(task_button)
    # Пока отключаем эту фичу
    # to_lessons_button = types.InlineKeyboardButton(
    #     text="К списку всех листков",
    #     callback_data=f"{CALLBACK_SHOW_LIST_OF_LISTS}"
    # )
    # keyboard_markup.add(to_lessons_button)
    return keyboard_markup


def build_lessons_keyboard():
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for lesson in problems.all_lessons:
        lesson_button = types.InlineKeyboardButton(
            text=f"Листок {lesson}",
            callback_data=f"{CALLBACK_LIST_SELECTED}_{lesson}",
        )
        keyboard_markup.add(lesson_button)
    return keyboard_markup


def build_test_answers_keyboard(choices):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for choice in choices:
        lesson_button = types.InlineKeyboardButton(
            text=choice,
            callback_data=f"{CALLBACK_ONE_OF_TEST_ANSWER_SELECTED}_{choice}",
        )
        keyboard_markup.add(lesson_button)
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK_CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup


def build_cancel_task_submission_keyboard():
    keyboard_markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=CALLBACK_CANCEL_TASK_SUBMISSION,
    )
    keyboard_markup.add(cancel_button)
    return keyboard_markup


async def prc_get_task_info_state(message, user: db_helper.User):
    await bot.send_message(
        chat_id=message.chat.id,
        text="❓ Нажимайте на задачу, чтобы сдать её",
        reply_markup=build_problems_keyboard(problems.last_lesson, user),
    )


async def prc_sending_solution_state(message: types.Message, user: db_helper.User):
    downloaded = []
    text = message.text
    if text:
        downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
    # for photo in message.photo:
    if message.photo:
        file_info = await bot.get_file(message.photo[-1].file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
    if message.document:
        print(message.document.file_size)
        if message.document.file_size > 5 * 1024 * 1024:
            await bot.send_message(chat_id=message.chat.id,
                                   text=f"❌ Размер файла превышает ограничение в 10 мегабайт")
            return
        file_id = message.document.file_id
        file_info = await bot.get_file(file_id)
        filename = message.document.file_name
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
    for bin_data, filename in downloaded:
        ext = filename[filename.rfind('.') + 1:]
        file_name = os.path.join(SOLS_PATH, str(user.id), str(states.get_by_user_id(user.id)['problem_id']),
                                 datetime.datetime.now().isoformat().replace(':', '') + '.' + ext)
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        db.add_message_to_log(False, message.message_id, message.chat.id, user.id, None, message.text, file_name)
        with open(file_name, 'wb') as file:
            file.write(bin_data.read())
    await bot.send_message(
        chat_id=message.chat.id,
        text="Принято на проверку"
    )
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_sending_test_answer_state(message: types.Message, user: db_helper.User):
    state = states.get_by_user_id(user.id)
    problem_id = state['problem_id']
    problem = problems.get_by_id(problem_id)
    student_answer = (message.text or '').strip()
    # Сначала проверим, проходит ли ответ валидацию регуляркой (если она указана)
    if problem.ans_type == ANS_TYPE_SELECT_ONE and student_answer not in problem.cor_ans.split(';'):
        await bot.send_message(chat_id=message.chat.id,
                               text=f"❌ Выберите один из вариантов: {', '.join(problem.ans_validation.split(';'))}")
        return
    elif problem.ans_type != ANS_TYPE_SELECT_ONE and problem.ans_validation and not re.fullmatch(problem.ans_validation,
                                                                                                 student_answer):
        await bot.send_message(chat_id=message.chat.id,
                               text=f"❌ {problem.validation_error}")
        return
    correct_answer = problem.cor_ans.strip()
    if student_answer == correct_answer:
        db.add_result(user.id, problem.id, problem.list, None, VERDICT_SOLVED, student_answer)
        await bot.send_message(chat_id=message.chat.id,
                               text=f"✔️ {problem.congrat}")
    else:
        db.add_result(user.id, problem.id, problem.list, None, VERDICT_WRONG_ANSWER, student_answer)
        await bot.send_message(chat_id=message.chat.id,
                               text=f"❌ {problem.wrong_ans}")
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_wait_sos_request_state(message: types.Message, user: db_helper.User):
    try:
        await bot.forward_message('@vmsh_bot_sos_channel', message.chat.id, message.message_id)
    except:
        # Если бот в этот канал не добавлен, то всё упадёт
        pass
    await bot.send_message(chat_id=message.chat.id, text=f"Переслал сообщение.")
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


state_processors = {
    STATE_GET_USER_INFO: prc_get_user_info_state,
    STATE_GET_TASK_INFO: prc_get_task_info_state,
    STATE_SENDING_SOLUTION: prc_sending_solution_state,
    STATE_SENDING_TEST_ANSWER: prc_sending_test_answer_state,
    STATE_WAIT_SOS_REQUEST: prc_wait_sos_request_state,
}


async def process_regular_message(message: types.Message):
    user = users.get_by_chat_id(message.chat.id)
    if not user:
        cur_chat_state = STATE_GET_USER_INFO
    else:
        cur_chat_state = states.get_by_user_id(user.id)['state']

        if not message.document and not message.photo:
            db.add_message_to_log(False, message.message_id, message.chat.id, user.id, None, message.text, None)
    state_processor = state_processors.get(cur_chat_state, prc_WTF)
    await state_processor(message, user)


async def start(message: types.Message):
    user = users.get_by_chat_id(message.chat.id)
    if not user:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль",
        )
    else:
        await process_regular_message(message)


async def sos(message: types.Message):
    user = users.get_by_chat_id(message.chat.id)
    if not user:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Привет! Без пароля я не знаю, кому помогать... Пожалуйста, введите свой пароль",
        )
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Так, опишите вашу проблему. И я перешлю это сообщение живому человеку.",
        )
        states.set_by_user_id(user.id, STATE_WAIT_SOS_REQUEST)


async def prc_problems_selected_callback(query: types.CallbackQuery, user: db_helper.User):
    user = users.get_by_chat_id(query.message.chat.id)
    state = states.get_by_user_id(user.id)
    problem_id = int(query.data[2:])
    problem = problems.get_by_id(problem_id)
    # В зависимости от типа задачи разное поведение
    if problem.prob_type == PROB_TYPE_TEST:
        # Если это выбор из нескольких вариантов, то нужно сделать клавиатуру
        if problem.ans_type == ANS_TYPE_SELECT_ONE:
            await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text=f"Выбрана задача {problem}.\nВыберите ответ — один из следующих вариантов:",
                                        reply_markup=build_test_answers_keyboard(problem.ans_validation.split(';')))
        else:
            await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text=f"Выбрана задача {problem}.\nТеперь введите ответ{ANS_HELP_DESCRIPTIONS[problem.ans_type]}",
                                        reply_markup=build_cancel_task_submission_keyboard())
        states.set_by_user_id(user.id, STATE_SENDING_TEST_ANSWER, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type == PROB_TYPE_WRITTEN:
        await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                    text=f"Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 вашего решения.",
                                    reply_markup=build_cancel_task_submission_keyboard())
        states.set_by_user_id(user.id, STATE_SENDING_SOLUTION, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type == PROB_TYPE_ORALLY:
        await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                    text=f"Выбрана задача {problem}. Это — устная задача. Её нужно сдавать в zoom-конференции: https://us02web.zoom.us/j/89206741729?pwd=WE1ZUGxpMDRoMlF5UHJLSkpDeU1rQT09, Идентификатор конференции: 892 0674 1729, Код доступа: 535079 после 17:00. После того, как вы решили устную задачу, для ускорения сдачи нужно записать ответ и основные шаги решения на бумаге. Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. Когда у вас всё готово, вы заходите в zoom-конференцию (ссылка на которую появится в 17:00, обратите внимание: не сразу!). Пожалуйста, при входе поставьте актуальную подпись: фамилию и имя школьника. Как только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. После окончания сдачи нужно выйти из конференции. Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. Мы постараемся успеть выделить время каждому, но не уверены, что это получится сразу на первых занятиях",
                                    reply_markup=None)
        states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        await bot_answer_callback_query(query.id)
        await asyncio.sleep(1)
        await process_regular_message(query.message)


async def prc_list_selected_callback(query: types.CallbackQuery, user: db_helper.User):
    list_num = int(query.data[2:])
    user = users.get_by_chat_id(query.message.chat.id)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Теперь выберите задачу",
                                reply_markup=build_problems_keyboard(list_num, user))
    await bot_answer_callback_query(query.id)


async def prc_show_list_of_lists_callback(query: types.CallbackQuery, user: db_helper.User):
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Вот список всех листков:",
                                reply_markup=build_lessons_keyboard())
    await bot_answer_callback_query(query.id)


async def prc_one_of_test_answer_selected_callback(query: types.CallbackQuery, user: db_helper.User):
    state = states.get_by_user_id(user.id)
    if state.get('state', None) != STATE_SENDING_TEST_ANSWER:
        print('WRONG STATE', state, STATE_SENDING_TEST_ANSWER, 'STATE_SENDING_TEST_ANSWER')
        return
    selected_answer = query.data[2:]
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot.send_message(chat_id=query.message.chat.id, text=f"Выбран вариант {selected_answer}.")
    state = states.get_by_user_id(user.id)
    problem_id = state['problem_id']
    problem = problems.get_by_id(problem_id)
    if problem is None:
        logging.error('Сломался приём задач :(')
        states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        await bot_answer_callback_query(query.id)
        await asyncio.sleep(1)
        await process_regular_message(query.message)
        return
    correct_answer = problem.cor_ans
    # await bot.send_message(chat_id=query.message.chat.id,
    #                        text=f"Выбран вариант {selected_answer}.")
    if selected_answer == correct_answer:
        db.add_result(user.id, problem.id, problem.list, None, VERDICT_SOLVED, selected_answer)
        await bot.send_message(chat_id=query.message.chat.id,
                               text=f"✔️ {problem.congrat}")
    else:
        db.add_result(user.id, problem.id, problem.list, None, VERDICT_WRONG_ANSWER, selected_answer)
        await bot.send_message(chat_id=query.message.chat.id,
                               text=f"❌ {problem.wrong_ans}")
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await bot_answer_callback_query(query.id)
    await asyncio.sleep(1)
    await process_regular_message(query.message)


async def prc_cancel_task_submission_callback(query: types.CallbackQuery, user: db_helper.User):
    states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    # await bot.send_message(
    #     chat_id=message.chat.id,
    #     text="❓ Нажимайте на задачу, чтобы сдать её",
    #     reply_markup=build_problems_keyboard(problems.last_lesson, user),
    # )
    await bot_edit_message_text(message_id=query.message.message_id, chat_id=query.message.chat.id,
                                text="❓ Нажимайте на задачу, чтобы сдать её",
                                reply_markup=build_problems_keyboard(problems.last_lesson, user))
    await bot_answer_callback_query(query.id)


callbacks_processors = {
    CALLBACK_PROBLEM_SELECTED: prc_problems_selected_callback,
    CALLBACK_SHOW_LIST_OF_LISTS: prc_show_list_of_lists_callback,
    CALLBACK_LIST_SELECTED: prc_list_selected_callback,
    CALLBACK_ONE_OF_TEST_ANSWER_SELECTED: prc_one_of_test_answer_selected_callback,
    CALLBACK_CANCEL_TASK_SUBMISSION: prc_cancel_task_submission_callback
}


async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    if query.message:
        user = users.get_by_chat_id(query.message.chat.id)
        if not user:
            try:
                await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                                    reply_markup=None)
            except:
                pass  # Ошибки здесь не важны
            await start(query.message)
            return
        callback_type = query.data[0]
        callback_processor = callbacks_processors.get(callback_type, None)
        await callback_processor(query, user)


async def check_webhook():
    # Set webhook
    webhook = await bot.get_webhook_info()  # Get current webhook status
    if webhook.url != WEBHOOK_URL:  # If URL is bad
        if not webhook.url:  # If URL doesnt match current - remove webhook
            await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)  # Set new URL for webhook


async def on_startup(app):
    await gen_conduit()
    logging.warning('Start up!')
    if USE_WEBHOOKS:
        await check_webhook()
    dispatcher.register_message_handler(start, commands=['start'])
    dispatcher.register_message_handler(sos, commands=['sos'])
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


async def gen_conduit(*args, **kwargs):
    rows = db.get_all_solved()
    students = sorted({(row['token'], row['surname'], row['name']) for row in rows}, key=lambda x: (x[1], x[2]))
    problems = sorted({(row['list'], row['prob'], row['item']) for row in rows})
    table = [[''] * len(problems) for i in range(len(students))]
    for row in rows:
        student = (row['token'], row['surname'], row['name'])
        problem = (row['list'], row['prob'], row['item'])
        row_n = students.index(student)
        col_n = problems.index(problem)
        table[row_n][col_n] = '1'
    s_table = ['token\tsuname\tname\t' + '\t'.join(str(x[0]) + '.' + str(x[1]) + x[2] for x in problems)]
    for row, student in zip(table, students):
        s_table.append(student[0] + '\t' + student[1] + '\t' + student[2] + '\t'.join(row))
    return '\n'.join(s_table)


# Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
# А вот в режиме отладки можно запустить и без вебхуков
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    start_polling(dispatcher, on_startup=on_startup, on_shutdown=on_shutdown)
else:
    USE_WEBHOOKS = True
    WEBHOOK_URL = "https://{}:{}/{}/".format(WEBHOOK_HOST, WEBHOOK_PORT, API_TOKEN)
    # Create app
    app = web.Application()
    configure_app(dispatcher, app, path='/{token}/', route_name='telegram_webhook_handler')
    # Setup event handlers.
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # app will be started by gunicorn

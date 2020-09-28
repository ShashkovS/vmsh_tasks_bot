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
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)

if os.environ.get('PROD', None) == 'true':
    logging.info(('*' * 50 + '\n') * 5)
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
WHITEBOARD_LINK = "https://www.shashkovs.ru/jitboard.html?{}"
USE_WEBHOOKS = False

# Для каждого бота своя база
db_name = hashlib.md5(API_TOKEN.encode('utf-8')).hexdigest() + '.db'
db, users, problems, states, written_queue, waitlist = db_helper.init_db_and_objects(db_name)

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
    global db, users, problems, states, written_queue, waitlist
    db, users, problems, states, written_queue, waitlist = db_helper.init_db_and_objects(db_name, refresh=True)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Данные обновлены",
    )
    user = users.get_by_chat_id(message.chat.id)
    if user.type == USER_TYPE_STUDENT:
        states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    elif user.type == USER_TYPE_TEACHER:
        states.set_by_user_id(user.id, STATE_TEACHER_SELECT_ACTION)
    await process_regular_message(message)


async def prc_get_user_info_state(message: types.Message, user: db_helper.User):
    user = users.get_by_token(message.text)
    if user is None:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🔁 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль.\nПароль был вам выслан по электронной почте, он имеет вид «pa1ro1»",
        )
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"🤖 ОК, Добро пожаловать, {user.name} {user.surname}",
        )
        users.set_chat_id(user, message.chat.id)
        if user.type == USER_TYPE_STUDENT:
            states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        elif user.type == USER_TYPE_TEACHER:
            states.set_by_user_id(user.id, STATE_TEACHER_SELECT_ACTION)
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


def build_problems_keyboard(lesson_num: int, student: db_helper.User):
    solved = db.check_student_solved(student.id, student.level, lesson_num)
    being_checked = db.check_student_sent_written(student.id, lesson_num)
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for problem in problems.get_by_lesson(student.level, lesson_num):
        if problem.id in solved:
            tick = '✅'
        elif problem.id in being_checked:
            tick = '❓'
        elif problem.prob_type == PROB_TYPE_ORALLY and states.get_by_user_id(student.id)['oral_problem_id'] is not None:
            tick = '⌛'
        else:
            tick = '⬜'
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
    logging.error('Здесь не добавлена обработка level')
    # TODO add level
    # for lesson in problems.all_lessons:
    #     lesson_button = types.InlineKeyboardButton(
    #         text=f"Листок {lesson}",
    #         callback_data=f"{CALLBACK_LIST_SELECTED}_{lesson}",
    #     )
    #     keyboard_markup.add(lesson_button)
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


def build_exit_waitlist_keyboard():
    keyboard_markup = types.ReplyKeyboardMarkup(selective=True, resize_keyboard=True)
    exit_button = types.KeyboardButton(
        text="/exit_waitlist Выйти из очереди"
    )
    keyboard_markup.add(exit_button)
    return keyboard_markup


def build_teacher_actions_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    get_written_task_button = types.InlineKeyboardButton(
        text="Проверить письменную задачу",
        callback_data=CALLBACK_GET_WRITTEN_TASK
    )
    keyboard.add(get_written_task_button)
    get_queue_top_button = types.InlineKeyboardButton(
        text="Вызвать школьника на устную сдачу",
        callback_data=CALLBACK_GET_QUEUE_TOP
    )
    keyboard.add(get_queue_top_button)
    return keyboard


def build_teacher_select_written_problem_keyboard(top: list):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    for row in top:
        student = users.get_by_id(row['student_id'])
        problem = problems.get_by_id(row['problem_id'])
        task_button = types.InlineKeyboardButton(
            text=f"{problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) {student.surname} {student.name}",
            callback_data=f"{CALLBACK_WRITTEN_TASK_SELECTED}_{student.id}_{problem.id}"
        )
        keyboard_markup.add(task_button)
    cancel = types.InlineKeyboardButton(
        text="Отмена",
        callback_data=f"{CALLBACK_TEACHER_CANCEL}"
    )
    keyboard_markup.add(cancel)
    return keyboard_markup


def build_written_task_checking_verdict_keyboard(student: db_helper.User, problem: db_helper.Problem):
    keyboard_markup = types.InlineKeyboardMarkup(row_width=7)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"✔ Засчитать задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})",
        callback_data=f"{CALLBACK_WRITTEN_TASK_OK}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отклонить и переслать все сообщения выше студенту {student.surname} {student.name}",
        callback_data=f"{CALLBACK_WRITTEN_TASK_BAD}_{student.id}_{problem.id}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"Отменить всю эту проверку и всё забыть",
        callback_data=f"{CALLBACK_TEACHER_CANCEL}_{student.id}_{problem.id}"
    ))
    return keyboard_markup


def build_student_in_conference_keyboard():
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"✔ Беседа окончена",
        callback_data=f"{CALLBACK_GET_OUT_OF_WAITLIST}"
    ))
    keyboard_markup.add(types.InlineKeyboardButton(
        text=f"❌ Отказаться от устной сдачи",
        callback_data=f"{CALLBACK_GET_OUT_OF_WAITLIST}"
    ))
    return keyboard_markup


async def prc_teacher_select_action(message: types.Message, teacher: db_helper.User):
    await bot.send_message(chat_id=message.chat.id, text="Выберите действие",
                           reply_markup=build_teacher_actions_keyboard())


async def prc_get_task_info_state(message, student: db_helper.User):
    slevel = '(уровень «Продолжающие»)' if student.level == 'п' else '(уровень «Начинающие»)'
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"❓ Нажимайте на задачу, чтобы сдать её {slevel}",
        reply_markup=build_problems_keyboard(problems.last_lesson, student),
    )


async def prc_sending_solution_state(message: types.Message, student: db_helper.User):
    problem_id = states.get_by_user_id(student.id)['problem_id']
    problem = problems.get_by_id(problem_id)
    downloaded = []
    file_name = None
    text = message.text
    if text:
        downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
        downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
    # for photo in message.photo:
    if message.photo:
        file_info = await bot.get_file(message.photo[-1].file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
    if message.document:
        if message.document.file_size > 5 * 1024 * 1024:
            await bot.send_message(chat_id=message.chat.id,
                                   text=f"❌ Размер файла превышает ограничение в 5 мегабайт")
            return
        file_id = message.document.file_id
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        filename = file_info.file_path
        downloaded.append((downloaded_file, filename))
    for bin_data, filename in downloaded:
        ext = filename[filename.rfind('.') + 1:]
        cur_ts = datetime.datetime.now().isoformat().replace(':', '-')
        file_name = os.path.join(SOLS_PATH,
                                 f'{student.token} {student.surname} {student.name}',
                                 f'{problem.lesson}',
                                 f'{problem.lesson}{problem.level}_{problem.prob}{problem.item}_{cur_ts}.{ext}')
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        db.add_message_to_log(False, message.message_id, message.chat.id, student.id, None, message.text, file_name)
        with open(file_name, 'wb') as file:
            file.write(bin_data.read())
    written_queue.add_to_queue(student.id, problem.id)
    written_queue.add_to_discussions(student.id, problem.id, None, text, file_name, message.chat.id, message.message_id)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Принято на проверку"
    )
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_teacher_is_checking_task_state(message: types.Message, teacher: db_helper.User):
    problem_id = states.get_by_user_id(teacher.id)['problem_id']
    student_id = states.get_by_user_id(teacher.id)['last_student_id']
    written_queue.add_to_discussions(student_id, problem_id, teacher.id, message.text, None, message.chat.id, message.message_id)
    await bot.send_message(chat_id=message.chat.id, text="Ок, записал")


async def prc_sending_test_answer_state(message: types.Message, student: db_helper.User):
    state = states.get_by_user_id(student.id)
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
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_SOLVED, student_answer)
        await bot.send_message(chat_id=message.chat.id,
                               text=f"✔️ {problem.congrat}")
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_WRONG_ANSWER, student_answer)
        await bot.send_message(chat_id=message.chat.id,
                               text=f"❌ {problem.wrong_ans}")
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_wait_sos_request_state(message: types.Message, student: db_helper.User):
    try:
        await bot.forward_message('@vmsh_bot_sos_channel', message.chat.id, message.message_id)
    except:
        # Если бот в этот канал не добавлен, то всё упадёт
        pass
    await bot.send_message(chat_id=message.chat.id, text=f"Переслал сообщение.")
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


def build_verdict_keyboard(plus_ids: set, student):
    lesson_num = problems.last_lesson
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    plus_ids_str = ','.join(map(str, plus_ids))
    for problem in problems.get_by_lesson(student.level, lesson_num):
        if problem.prob_type == PROB_TYPE_ORALLY:
            tick = '✅' if problem.id in plus_ids else ''
            task_button = types.InlineKeyboardButton(
                text=f"{tick} {problem}",
                callback_data=f"{CALLBACK_ADD_OR_REMOVE_ORAL_PLUS}_{problem.id}_{plus_ids_str}"
            )
            keyboard_markup.add(task_button)
    ready_button = types.InlineKeyboardButton(
        text="Готово (завершить сдачу и внести в кондуит)",
        callback_data=f"{CALLBACK_FINISH_ORAL_ROUND}_{plus_ids_str}"
    )
    keyboard_markup.add(ready_button)
    return keyboard_markup


async def prc_teacher_accepted_queue(message: types.message, teacher: db_helper.User):
    state = states.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = users.get_by_id(student_id)
    await bot.send_message(chat_id=message.chat.id,
                           text="Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)",
                           reply_markup=build_verdict_keyboard(plus_ids=set(), student=student))


async def prc_student_is_in_conference_state(message: types.message, student: db_helper.User):
    # Ничего не делаем, ждём callback'а
    pass


state_processors = {
    STATE_GET_USER_INFO: prc_get_user_info_state,
    STATE_GET_TASK_INFO: prc_get_task_info_state,
    STATE_SENDING_SOLUTION: prc_sending_solution_state,
    STATE_SENDING_TEST_ANSWER: prc_sending_test_answer_state,
    STATE_WAIT_SOS_REQUEST: prc_wait_sos_request_state,
    STATE_TEACHER_SELECT_ACTION: prc_teacher_select_action,
    STATE_TEACHER_IS_CHECKING_TASK: prc_teacher_is_checking_task_state,
    STATE_TEACHER_ACCEPTED_QUEUE: prc_teacher_accepted_queue,
    STATE_STUDENT_IS_IN_CONFERENCE: prc_student_is_in_conference_state,
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
    if user:
        states.set_by_user_id(user.id, STATE_GET_USER_INFO)
    await bot.send_message(
        chat_id=message.chat.id,
        text="🤖 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль",
    )


async def recheck(message: types.Message):
    teacher = users.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE_TEACHER:
        return
    match = re.fullmatch(r'/recheck_xd5fqk\s+(\w{6})\s+(\d+)([а-я])\.(\d+)([а-я]?)\s*', message.text or '')
    if not match:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Пришлите запрос на перепроверку в формате «/recheck_xd5fqk token problem», например «/recheck_xd5fqk aa9bb4 3н.11а»",
        )
    else:
        token, lst, level, prob, item = match.groups()
        student = users.get_by_token(token)
        problem = problems.get_by_key(level, int(lst), int(prob), item)
        if not student:
            await bot.send_message(chat_id=message.chat.id, text=f"🤖 Студент с токеном {token} не найден")
        if not problem:
            await bot.send_message(chat_id=message.chat.id, text=f"🤖 Задача {lst}{level}.{prob}{item} не найдена")
        if student and problem:
            written_queue.add_to_queue(student.id, problem.id, ts=datetime.datetime(1, 1, 1))
            await bot.send_message(chat_id=message.chat.id, text=f"Переотправили на проверку")


async def broadcast(message: types.Message):
    teacher = users.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE_TEACHER:
        return
    text = message.text.splitlines()
    try:
        cmd, tokens, *broadcast_message = text
    except:
        return
    broadcast_message = '\n'.join(broadcast_message)
    tokens = re.split('\W+', tokens)
    if tokens == ['all_students']:
        tokens = [user.token for user in users if user.type == USER_TYPE_STUDENT]
    elif tokens == ['all_teachers']:
        tokens = [user.token for user in users if user.type == USER_TYPE_TEACHER]
    for token in tokens:
        student = users.get_by_token(token)
        if not student or not student.chat_id:
            continue
        try:
            broad_message = await bot.send_message(
                chat_id=student.chat_id,
                text=broadcast_message,
            )
            db.add_message_to_log(True, broad_message.message_id, broad_message.chat.id, student.id, None, broadcast_message, None)
        except (aiogram.utils.exceptions.ChatNotFound,
                aiogram.utils.exceptions.MessageToForwardNotFound,
                aiogram.utils.exceptions.BotBlocked,
                aiogram.utils.exceptions.ChatIdIsEmpty,) as e:
            logging.error(f'Школьник удалил себя?? WTF? {student.chat_id}\n{e}')
        await asyncio.sleep(.05)  # 20 messages per second (Limit: 30 messages per second)


async def level_novice(message: types.Message):
    student = users.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу начинающих",
        )
        student.set_level('н')
        states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await process_regular_message(message)


async def level_pro(message: types.Message):
    student = users.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу продолжающих",
        )
        student.set_level('п')
        states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
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


async def prc_problems_selected_callback(query: types.CallbackQuery, student: db_helper.User):
    student = users.get_by_chat_id(query.message.chat.id)
    # state = states.get_by_user_id(user.id)
    problem_id = int(query.data[2:])
    problem = problems.get_by_id(problem_id)
    if not problem:
        await bot_answer_callback_query(query.id)
        states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await process_regular_message(query.message)
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
        states.set_by_user_id(student.id, STATE_SENDING_TEST_ANSWER, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type == PROB_TYPE_WRITTEN:
        await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                    text=f"Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 вашего решения.",
                                    reply_markup=build_cancel_task_submission_keyboard())
        states.set_by_user_id(student.id, STATE_SENDING_SOLUTION, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type == PROB_TYPE_ORALLY:
        # await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
        #                             text=f"Выбрана устная задача. Её нужно сдавать после 17:00 в zoom-конференции. Желательно перед сдачей записать ответ и основные шаги решения на бумаге. Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. Когда у вас всё готово, заходите в zoom-конференцию, идентификатор конференции: 834 3300 5508, код доступа: 179179. Пожалуйста, при входе поставьте актуальную подпись: ваши фамилию и имя. Как только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. После окончания сдачи нужно выйти из конференции. Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. Мы постараемся выделить время каждому, но не уверены, что это получится сразу на первых занятиях.",
        #                             disable_web_page_preview=True)
        # states.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        # await bot_answer_callback_query(query.id)
        # await asyncio.sleep(1)
        # await process_regular_message(query.message)
        state = states.get_by_user_id(student.id)
        if state['oral_problem_id'] is not None:
            await bot.send_message(chat_id=query.message.chat.id,
                                   text="Вы уже стоите в очереди на устную сдачу\. Дождитесь, когда освободится один из преподавателей\. Тогда можно будет сдать сразу несколько задач\.",
                                   parse_mode="MarkdownV2")
            await bot_answer_callback_query(query.id)
        else:
            try:
                await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
            except:
                pass
            waitlist.enter(student.id, problem.id)
            await bot.send_message(chat_id=query.message.chat.id,
                                   text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
                                   parse_mode="MarkdownV2",
                                   reply_markup=build_exit_waitlist_keyboard())
            await bot_answer_callback_query(query.id)
            await asyncio.sleep(4)
            await process_regular_message(query.message)


async def prc_list_selected_callback(query: types.CallbackQuery, student: db_helper.User):
    list_num = int(query.data[2:])
    student = users.get_by_chat_id(query.message.chat.id)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Теперь выберите задачу",
                                reply_markup=build_problems_keyboard(list_num, student))
    await bot_answer_callback_query(query.id)


async def prc_show_list_of_lists_callback(query: types.CallbackQuery, student: db_helper.User):
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Вот список всех листков:",
                                reply_markup=build_lessons_keyboard())
    await bot_answer_callback_query(query.id)


async def prc_one_of_test_answer_selected_callback(query: types.CallbackQuery, student: db_helper.User):
    state = states.get_by_user_id(student.id)
    if state.get('state', None) != STATE_SENDING_TEST_ANSWER:
        logging.info('WRONG STATE', state, STATE_SENDING_TEST_ANSWER, 'STATE_SENDING_TEST_ANSWER')
        return
    selected_answer = query.data[2:]
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot.send_message(chat_id=query.message.chat.id, text=f"Выбран вариант {selected_answer}.")
    state = states.get_by_user_id(student.id)
    problem_id = state['problem_id']
    problem = problems.get_by_id(problem_id)
    if problem is None:
        logging.error('Сломался приём задач :(')
        states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await bot_answer_callback_query(query.id)
        await asyncio.sleep(1)
        await process_regular_message(query.message)
        return
    correct_answer = problem.cor_ans
    # await bot.send_message(chat_id=query.message.chat.id,
    #                        text=f"Выбран вариант {selected_answer}.")
    if selected_answer == correct_answer:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_SOLVED, selected_answer)
        await bot.send_message(chat_id=query.message.chat.id,
                               text=f"✔️ {problem.congrat}")
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_WRONG_ANSWER, selected_answer)
        await bot.send_message(chat_id=query.message.chat.id,
                               text=f"❌ {problem.wrong_ans}")
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await bot_answer_callback_query(query.id)
    await asyncio.sleep(1)
    await process_regular_message(query.message)


async def prc_cancel_task_submission_callback(query: types.CallbackQuery, student: db_helper.User):
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    # await bot.send_message(
    #     chat_id=message.chat.id,
    #     text="❓ Нажимайте на задачу, чтобы сдать её",
    #     reply_markup=build_problems_keyboard(problems.last_lesson, user),
    # )
    await bot_edit_message_text(message_id=query.message.message_id, chat_id=query.message.chat.id,
                                text="❓ Нажимайте на задачу, чтобы сдать её",
                                reply_markup=build_problems_keyboard(problems.last_lesson, student))
    await bot_answer_callback_query(query.id)


async def prc_get_written_task_callback(query: types.CallbackQuery, teacher: db_helper.User):
    # Так, препод указал, что хочет проверять письменные задачи
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    top = written_queue.take_top()
    if not top:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ничего себе! Все письменные задачи проверены!")
        states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
        await bot_answer_callback_query(query.id)
        await process_regular_message(query.message)
    else:
        # Даём преподу 10 топовых задач на выбор
        await bot.send_message(chat_id=teacher.chat_id, text="Выберите задачу для проверки",
                               reply_markup=build_teacher_select_written_problem_keyboard(top))
        # build_teacher_actions_keyboard


async def prc_teacher_cancel_callback(query: types.CallbackQuery, teacher: db_helper.User):
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def prc_written_task_selected_callback(query: types.CallbackQuery, teacher: db_helper.User):
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    chat_id = query.message.chat.id
    _, student_id, problem_id = query.data.split('_')
    student = users.get_by_id(int(student_id))
    problem = problems.get_by_id(int(problem_id))
    await bot_answer_callback_query(query.id)
    # Блокируем задачу
    is_unlocked = written_queue.mark_being_checked(student.id, problem.id)
    if not is_unlocked:
        await bot.send_message(chat_id=chat_id, text='Эту задачу уже кто-то взялся проверять.')
        states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
        await process_regular_message(query.message)
        return
    await bot_edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                text=f"Проверяем задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})\n"
                                     f"Школьник {student.token} {student.surname} {student.name}"
                                     f"⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",
                                reply_markup=None)
    discussion = written_queue.get_discussion(student.id, problem.id)
    for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не привысить лимит
        # Пока временно делаем только forward'ы. Затем нужно будет изолировать учителя от студента
        forward_success = False
        if row['chat_id'] and row['tg_msg_id']:
            try:
                await bot.forward_message(chat_id, row['chat_id'], row['tg_msg_id'])
                forward_success = True
            except (aiogram.utils.exceptions.ChatNotFound, aiogram.utils.exceptions.MessageToForwardNotFound):
                await bot.send_message(chat_id=chat_id, text='Сообщение было удалено...')
        if forward_success:
            pass
        elif row['text']:
            await bot.send_message(chat_id=chat_id, text=row['text'])
        elif row['attach_path']:
            # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
            path = row['attach_path'].replace('/web/vmsh179bot/vmsh179bot/', '')
            input_file = types.input_file.InputFile(path)
            await bot.send_photo(chat_id=chat_id, photo=input_file)
    states.set_by_user_id(teacher.id, STATE_TEACHER_IS_CHECKING_TASK, problem.id, last_teacher_id=teacher.id, last_student_id=student.id)
    await bot.send_message(chat_id=chat_id,
                           text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n'
                                'Напишите комментарий или скриншот 📸 вашей проверки (или просто поставьте плюс)',
                           reply_markup=build_written_task_checking_verdict_keyboard(student, problem))


async def prc_written_task_ok_callback(query: types.CallbackQuery, teacher: db_helper.User):
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = users.get_by_id(int(student_id))
    problem = problems.get_by_id(int(problem_id))
    # Помечаем задачу как решённую и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_SOLVED, None)
    written_queue.delete_from_queue(student.id, problem.id)
    await bot_answer_callback_query(query.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'✔ Отлично, поставили плюсик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}!')
    states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    student_chat_id = users.get_by_id(student.id).chat_id
    try:
        discussion = written_queue.get_discussion(student.id, problem.id)
        # Находим последнее сообщение школьника
        last_pup_post = max([rn for rn in range(len(discussion)) if discussion[rn]['teacher_id'] is None] + [-2])
        teacher_comments = discussion[last_pup_post + 1:]
        if not teacher_comments:
            await bot.send_message(chat_id=student_chat_id,
                                   text=f"Задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) проверили и поставили плюсик!",
                                   disable_notification=True)
        else:
            await bot.send_message(chat_id=student_chat_id,
                                   text=f"Задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) проверили и поставили плюсик!\n"
                                        f"Вот комментарии:\n"
                                        f"⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",
                                   disable_notification=True)
            for row in teacher_comments:
                # Пока временно делаем только forward'ы. Затем нужно будет изолировать учителя от студента
                if row['chat_id'] and row['tg_msg_id']:
                    await bot.forward_message(student_chat_id, row['chat_id'], row['tg_msg_id'], disable_notification=True)
                elif row['text']:
                    await bot.send_message(chat_id=student_chat_id, text=row['text'], disable_notification=True)
                elif row['attach_path']:
                    # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
                    input_file = types.input_file.InputFile(row['attach_path'])
                    await bot.send_photo(chat_id=student_chat_id, photo=input_file, disable_notification=True)
            await bot.send_message(chat_id=student_chat_id,
                                   text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n',
                                   disable_notification=True)
    except (aiogram.utils.exceptions.ChatNotFound,
            aiogram.utils.exceptions.MessageToForwardNotFound,
            aiogram.utils.exceptions.BotBlocked,
            aiogram.utils.exceptions.ChatIdIsEmpty,) as e:
        logging.error(f'Школьник удалил себя?? WTF? {student_chat_id}\n{e}')
    await process_regular_message(query.message)


async def prc_written_task_bad_callback(query: types.CallbackQuery, teacher: db_helper.User):
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = users.get_by_id(int(student_id))
    problem = problems.get_by_id(int(problem_id))
    # Помечаем решение как неверное и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_WRONG_ANSWER, None)
    written_queue.delete_from_queue(student.id, problem.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'❌ Эх, поставили минусик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}!')

    # Пересылаем переписку школьнику
    student_chat_id = users.get_by_id(student.id).chat_id
    try:
        discussion = written_queue.get_discussion(student.id, problem.id)
        await bot.send_message(chat_id=student_chat_id,
                               text=f"Задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) проверили и сделали замечания:\n"
                                    f"Пересылаю всю переписку.\n"
                                    f"⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",
                               disable_notification=True)
        for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не привысить лимит
            # Пока временно делаем только forward'ы. Затем нужно будет изолировать учителя от студента
            if row['chat_id'] and row['tg_msg_id']:
                await bot.forward_message(student_chat_id, row['chat_id'], row['tg_msg_id'], disable_notification=True)
            elif row['text']:
                await bot.send_message(chat_id=student_chat_id, text=row['text'], disable_notification=True)
            elif row['attach_path']:
                # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
                input_file = types.input_file.InputFile(row['attach_path'])
                await bot.send_photo(chat_id=student_chat_id, photo=input_file, disable_notification=True)
        await bot.send_message(chat_id=student_chat_id,
                               text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n',
                               disable_notification=True)
    except (aiogram.utils.exceptions.ChatNotFound,
            aiogram.utils.exceptions.MessageToForwardNotFound,
            aiogram.utils.exceptions.BotBlocked,
            aiogram.utils.exceptions.ChatIdIsEmpty,) as e:
        logging.error(f'Школьник удалил себя?? WTF? {student_chat_id}\n{e}')
    states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def prc_get_queue_top_callback(query: types.CallbackQuery, teacher: db_helper.User):
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    top = waitlist.top(1)
    if not top:
        # Если в очереди пусто, то шлём сообщение и выходим.
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Сейчас очередь пуста. Повторите через пару минут.")
        await bot_answer_callback_query(query.id)
        await prc_teacher_select_action(query.message, teacher)
        return

    student = users.get_by_id(top[0]['student_id'])
    problem = problems.get_by_id(top[0]['problem_id'])
    states.set_by_user_id(teacher.id, STATE_TEACHER_ACCEPTED_QUEUE, oral_problem_id=problem.id, last_student_id=student.id)
    waitlist.leave(student.id)

    params = {
        'studentId': student.id,
        'teacherId': teacher.id,
        'problemId': problem.id,
        'displayName': f"{student.name} {student.surname}"
    }
    student_link = WHITEBOARD_LINK.format(urlencode(params))
    params['displayName'] = f"{teacher.name} {teacher.middlename} {teacher.surname}"
    teacher_link = WHITEBOARD_LINK.format(urlencode(params))
    # Вообще школьник мог успеть прогнать бота и запретить ему писать
    try:
        await bot.send_message(chat_id=student.chat_id,
                               text=f"<b>До вас дошла очередь</b> на сдачу задачи\n{problem}\n"
                                    f"<b><a href=\"{student_link}\">Войдите в конференцию</a></b>.",
                               reply_markup=types.ReplyKeyboardRemove(),
                               parse_mode='HTML')
        states.set_by_user_id(student.id, STATE_STUDENT_IS_IN_CONFERENCE, oral_problem_id=problem.id, last_teacher_id=teacher.id)
        await bot.send_message(chat_id=student.chat_id, text="Нажмите по окончанию.",
                               reply_markup=build_student_in_conference_keyboard(),
                               parse_mode='HTML')
    except (aiogram.utils.exceptions.ChatNotFound,
            aiogram.utils.exceptions.MessageToForwardNotFound,
            aiogram.utils.exceptions.BotBlocked,
            aiogram.utils.exceptions.ChatIdIsEmpty,) as e:
        logging.error(f'Школьник удалил себя?? WTF? {student.chat_id}\n{e}')
        # Снимаем со школьника статус сдачи
        states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    else:
        await bot_answer_callback_query(query.id, show_alert=True)
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"<b>Ваш ученик: {student}.\n"
                                    f"{problem}.\n"
                                    f"<a href=\"{teacher_link}\">Войдите в конференцию</a></b>",
                               parse_mode='HTML')
    await bot_answer_callback_query(query.id)
    await process_regular_message(message=query.message)


async def prc_set_verdict_callback(query: types.CallbackQuery, teacher: db_helper.User):
    state = states.get_by_user_id(teacher.id)
    problem_id = state['oral_problem_id']
    # TODO !!!
    if problem_id is None:
        logging.info("WAT problem_id is None")
        return
    problem = problems.get_by_id(problem_id)
    verdict = int(query.data.split('_')[1])
    student_id = state['last_student_id']
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot_answer_callback_query(query.id)
    states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    db.add_result(student_id, problem_id, problem.level, problem.lesson, teacher.id, verdict, '')
    await process_regular_message(query.message)


async def prc_get_out_of_waitlist_callback(query: types.CallbackQuery, student: db_helper.User):
    state = states.get_by_user_id(student.id)
    teacher = users.get_by_id(state['last_teacher_id'])
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    waitlist.leave(student.id)
    states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    if teacher:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ученик {student.surname} {student.name} {student.token} завершил устную сдачу.\n")
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def prc_add_or_remove_oral_plus_callback(query: types.CallbackQuery, teacher: db_helper.User):
    _, problem_id, selected_ids = query.data.split('_')
    problem_id = int(problem_id)
    selected_ids = set() if not selected_ids else {int(prb_id) for prb_id in selected_ids.split(',')}
    selected_ids.symmetric_difference_update({problem_id})
    state = states.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = users.get_by_id(student_id)
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=build_verdict_keyboard(plus_ids=selected_ids, student=student))
    await bot_answer_callback_query(query.id)


async def prc_finish_oral_round_callback(query: types.CallbackQuery, teacher: db_helper.User):
    _, selected_ids = query.data.split('_')
    selected_ids = set() if not selected_ids else {int(prb_id) for prb_id in selected_ids.split(',')}
    state = states.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = users.get_by_id(student_id)
    pluses = [problems.get_by_id(prb_id) for prb_id in selected_ids]
    human_readable_pluses = [f'{plus.lesson}{plus.level}.{plus.prob}{plus.item}' for plus in pluses]
    # Проставляем плюсики
    for problem in pluses:
        db.add_result(student_id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_SOLVED, None)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text=f"Школьник: {student.token} {student.surname} {student.name}\n"
                                     f"Поставлены плюсы за задачи: {', '.join(human_readable_pluses)}",
                                reply_markup=None)
    try:
        student_state = states.get_by_user_id(student.id)
        student_message = await bot.send_message(chat_id=student.chat_id,
                                                 text=f"В результате устного приёма вам поставили плюсики за задачи: {', '.join(human_readable_pluses)}",
                                                 disable_notification=True)
        if student_state['state'] == STATE_STUDENT_IS_IN_CONFERENCE:
            states.set_by_user_id(student.id, STATE_GET_TASK_INFO)
            await process_regular_message(student_message)
    except (aiogram.utils.exceptions.ChatNotFound,
            aiogram.utils.exceptions.MessageToForwardNotFound,
            aiogram.utils.exceptions.BotBlocked,
            aiogram.utils.exceptions.ChatIdIsEmpty,) as e:
        logging.error(f'Школьник удалил себя?? WTF? {student.chat_id}\n{e}')
    await bot_answer_callback_query(query.id)
    states.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await process_regular_message(query.message)


callbacks_processors = {
    CALLBACK_PROBLEM_SELECTED: prc_problems_selected_callback,
    CALLBACK_SHOW_LIST_OF_LISTS: prc_show_list_of_lists_callback,
    CALLBACK_LIST_SELECTED: prc_list_selected_callback,
    CALLBACK_ONE_OF_TEST_ANSWER_SELECTED: prc_one_of_test_answer_selected_callback,
    CALLBACK_GET_QUEUE_TOP: prc_get_queue_top_callback,
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


async def exit_waitlist(message: types.Message):
    user = users.get_by_chat_id(message.chat.id)
    waitlist.leave(user.id)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Вы успешно покинули очередь.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await process_regular_message(message)


async def on_startup(app):
    logging.warning('Start up!')
    if USE_WEBHOOKS:
        await check_webhook()
    dispatcher.register_message_handler(start, commands=['start'])
    dispatcher.register_message_handler(sos, commands=['sos'])
    dispatcher.register_message_handler(broadcast, commands=['broadcast_wibkn96x'])
    dispatcher.register_message_handler(recheck, commands=['recheck_xd5fqk'])
    dispatcher.register_message_handler(update_all_internal_data, commands=['update_all_quaLtzPE'])
    dispatcher.register_message_handler(exit_waitlist, commands=['exit_waitlist'])
    dispatcher.register_message_handler(level_novice, commands=['level_novice'])
    dispatcher.register_message_handler(level_pro, commands=['level_pro'])
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
    db.disconnect()
    logging.warning('Bye!')


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

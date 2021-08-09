import os
import io
import datetime
import re
import asyncio
import traceback
import aiogram
from aiogram.dispatcher.webhook import types
from urllib.parse import urlencode

from consts import *
from config import logger, config
from obj_classes import User, Problem, State, Waitlist, WrittenQueue, Result, db
from bot import bot, bot_edit_message_text, bot_edit_message_reply_markup, bot_answer_callback_query, bot_post_logging_message
import keyboards

SOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solutions')
WHITEBOARD_LINK = "https://www.shashkovs.ru/jitboard.html?{}"
GLOBALS_FOR_TEST_FUNCTION_CREATION = {
    '__builtins__': None, 're': re,
    'bool': bool, 'float': float, 'int': int, 'list': list, 'range': range, 'set': set, 'str': str, 'tuple': tuple,
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'enumerate': enumerate, 'format': format, 'len': len,
    'max': max, 'min': min, 'round': round, 'sorted': sorted, 'sum': sum, 'map': map,
}


async def prc_get_user_info_state(message: types.Message, user: User):
    logger.debug('prc_get_user_info_state')
    user = User.get_by_token(message.text)
    if user is None:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🔁 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль.\n"
                 "Пароль был вам выслан по электронной почте, он имеет вид «pa1ro1»",
        )
    else:
        User.set_chat_id(user, message.chat.id)
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"🤖 ОК, Добро пожаловать, {user.name} {user.surname}",
        )
        if user.type == USER_TYPE_STUDENT:
            State.set_by_user_id(user.id, STATE_GET_TASK_INFO)
        elif user.type == USER_TYPE_TEACHER:
            State.set_by_user_id(user.id, STATE_TEACHER_SELECT_ACTION)
        await process_regular_message(message)


async def prc_WTF(message: types.Message, user: User):
    logger.debug('prc_WTF')
    await bot.send_message(
        chat_id=message.chat.id,
        text="☢️ Всё сломалось, бот запутался в текущей ситации :(. Начнём сначала!",
    )
    logger.error(f"prc_WTF: {user!r} {message!r}")
    State.set_by_user_id(user.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_teacher_select_action(message: types.Message, teacher: User):
    logger.debug('prc_teacher_select_action')
    await bot.send_message(chat_id=message.chat.id, text="Выберите действие",
                           reply_markup=keyboards.build_teacher_actions())


async def prc_get_task_info_state(message, student: User):
    logger.debug('prc_get_task_info_state')
    # alarm = ''
    # Попытка сдать решение без выбранной задачи
    # if message.num_processed <= 1:
    #     if message.photo or message.document:
    #         alarm = '❗❗❗ Файл НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n' \
    #                 '(Можно посылать несколько фотографий решения, для этого каждый раз нужно выбирать задачу.)'
    #     elif message.text and len(message.text) > 20:
    #         alarm = '❗❗❗ Текст НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n'
    #     if alarm:
    #         await bot.send_message(chat_id=message.chat.id, text=alarm,)
    #         await asyncio.sleep(3)

    slevel = '(уровень «Продолжающие»)' if student.level == STUDENT_PRO else '(уровень «Начинающие»)'
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"❓ Нажимайте на задачу, чтобы сдать её {slevel}",
        reply_markup=keyboards.build_problems(Problem.last_lesson_num(), student),
    )


async def prc_sending_solution_state(message: types.Message, student: User):
    logger.debug('prc_sending_solution_state')
    problem_id = State.get_by_user_id(student.id)['problem_id']
    problem = Problem.get_by_id(problem_id)
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
    WrittenQueue.add_to_queue(student.id, problem.id)
    WrittenQueue.add_to_discussions(student.id, problem.id, None, text, file_name, message.chat.id, message.message_id)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Принято на проверку"
    )
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_teacher_is_checking_task_state(message: types.Message, teacher: User):
    logger.debug('prc_teacher_is_checking_task_state')
    problem_id = State.get_by_user_id(teacher.id)['problem_id']
    student_id = State.get_by_user_id(teacher.id)['last_student_id']
    WrittenQueue.add_to_discussions(student_id, problem_id, teacher.id, message.text, None, message.chat.id,
                                    message.message_id)
    await bot.send_message(chat_id=message.chat.id, text="Ок, записал")


def check_test_ans_rate_limit(student_id: int, problem_id: int):
    logger.debug('check_test_ans_rate_limit')
    per_day, per_hour = db.check_num_answers(student_id, problem_id)
    text_to_student = None
    if per_hour >= 3:
        text_to_student = '💤⌛ В течение одного часа бот не принимает больше 3 ответов. Отправьте ваш ответ в начале следующего часа.'
    elif per_day >= 6:
        text_to_student = '💤⌛ В течение одного дня бот не принимает больше 6 ответов. Отправьте ваш ответ завтра.'
    return text_to_student


async def prc_sending_test_answer_state(message: types.Message, student: User, check_functions_cache={}):
    logger.debug('prc_sending_test_answer_state')
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    text_to_student = check_test_ans_rate_limit(student.id, problem_id)
    if text_to_student:
        await bot.send_message(chat_id=message.chat.id, text=text_to_student)
        await asyncio.sleep(1)
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        logger.info(f'Ограничили студанта: {student.id}')
        await process_regular_message(message)
        return
    problem = Problem.get_by_id(problem_id)
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

    answer_is_correct = False
    # Здесь мы проверяем ответ в зависимости от того, как проверять
    # TODO сделать нормально
    if problem.cor_ans_checker == 'py_func':
        func_code = problem.cor_ans
        func_name = re.search(r'\s*def\s+(\w+)', func_code)[1]
        if func_name in check_functions_cache:
            test_func = check_functions_cache[func_name]
        else:
            locs = {}
            # О-о-очень опасный кусок :)
            exec(func_code, GLOBALS_FOR_TEST_FUNCTION_CREATION, locs)
            func_name, test_func = locs.popitem()
            check_functions_cache[func_name] = test_func
        result = additional_message = answer_is_correct = None
        try:
            result = test_func(student_answer)
            answer_is_correct, additional_message = result
        except Exception as e:
            error_text = f'PYCHECKER_ERROR: {traceback.format_exc()}\nFUNC_CODE:\n{func_code.replace(" ", "_")}\nENTRY:\n{student_answer}\nRESULT:\n{result!r}'
            logger.error(f'PYCHECKER_ERROR: {e}\nFUNC_CODE:\n{func_code}\nRESULT:\n{result!r}')
            await bot_post_logging_message(error_text)

        if additional_message:
            await bot.send_message(chat_id=message.chat.id, text=additional_message)
    else:
        # Ура! Простое обычное понятное сравнение!
        correct_answer = re.sub(r'[^а-яёa-z0-9+\-()*/^;]+', ' ', problem.cor_ans.lower())
        student_answer = re.sub(r'[^а-яёa-z0-9+\-()*/^]+', ' ', student_answer.lower())
        if ';' not in correct_answer:
            answer_is_correct = (student_answer == correct_answer)
        else:
            correct_answer = list(ans.strip() for ans in correct_answer.split(';'))
            answer_is_correct = student_answer in correct_answer

    if answer_is_correct:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_SOLVED, student_answer, RES_TYPE_TEST)
        text_to_student = f"✔️ {problem.congrat}"
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_WRONG_ANSWER, student_answer, RES_TYPE_TEST)
        text_to_student = f"❌ {problem.wrong_ans}"
    if os.environ.get('EXAM', None) == 'true':
        text_to_student = 'Ответ принят на проверку.'
    await bot.send_message(chat_id=message.chat.id, text=text_to_student)
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


async def prc_wait_sos_request_state(message: types.Message, student: User):
    logger.debug('prc_wait_sos_request_state')
    try:
        await bot.forward_message(config.sos_channel, message.chat.id, message.message_id)
    except:
        logger.info(f'Не удалось переслать SOS-сообщение в канал {config.sos_channel}')
    await bot.send_message(chat_id=message.chat.id, text=f"Переслал сообщение.")
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)

async def prc_teacher_accepted_queue(message: types.message, teacher: User):
    logger.debug('prc_teacher_accepted_queue')
    state = State.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = User.get_by_id(student_id)
    await bot.send_message(chat_id=message.chat.id,
                           text="Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)",
                           reply_markup=keyboards.build_verdict(plus_ids=set(), minus_ids=set(), student=student))


async def prc_teacher_writes_student_name_state(message: types.message, teacher: User):
    logger.debug('prc_teacher_writes_student_name_state')
    name_to_find = message.text or ''
    await bot.send_message(chat_id=message.chat.id,
                           text="Выберите школьника для внесения задач",
                           reply_markup=keyboards.build_select_student(name_to_find))


async def prc_student_is_sleeping_state(message: types.message, student: User):
    logger.debug('prc_student_is_sleeping_state')
    await bot.send_message(chat_id=message.chat.id,
                           text="🤖 Приём задач ботом окончен до начала следующего занятия.\n"
                                "Заходите в канал @vmsh_179_5_6_2020 кружка за новостями и решениями.")


async def prc_student_is_in_conference_state(message: types.message, student: User):
    logger.debug('prc_student_is_in_conference_state')
    # Ничего не делаем, ждём callback'а
    pass



state_processors = {
    STATE_GET_USER_INFO: prc_get_user_info_state,
    STATE_GET_TASK_INFO: prc_get_task_info_state,
    STATE_SENDING_SOLUTION: prc_sending_solution_state,
    STATE_SENDING_TEST_ANSWER: prc_sending_test_answer_state,
    STATE_WAIT_SOS_REQUEST: prc_wait_sos_request_state,
    STATE_STUDENT_IS_IN_CONFERENCE: prc_student_is_in_conference_state,
    STATE_STUDENT_IS_SLEEPING: prc_student_is_sleeping_state,
    STATE_TEACHER_SELECT_ACTION: prc_teacher_select_action,
    STATE_TEACHER_IS_CHECKING_TASK: prc_teacher_is_checking_task_state,
    STATE_TEACHER_ACCEPTED_QUEUE: prc_teacher_accepted_queue,
    STATE_TEACHER_WRITES_STUDENT_NAME: prc_teacher_writes_student_name_state,
}


async def process_regular_message(message: types.Message):
    logger.debug('process_regular_message')
    # Сначала проверяем, что этот тип сообщений мы вообще поддерживаем
    alarm = None
    if message.document and message.document.mime_type.startswith('image'):
        alarm = '❗❗❗ Бот принимает только сжатые фото: отправляйте картинки по одной, ставьте галочку «Сжать/Compress»'
    elif not message.text and not message.photo:
        alarm = '❗❗❗ Бот принимает только текстовые сообщения и фотографии решений.'
    if alarm:
        try:
            await bot.send_message(chat_id=message.chat.id, text=alarm)
        except Exception as e:
            logger.error(f'SHIT: {e}')
        return
    # Ок, теперь обрабатываем сообщение

    # Может так статься, что сообщение будет ходить кругами по функциям и будет обработано несколько раз.
    # Некоторым функциям это может быть важно
    # message.num_processed = getattr(message, 'num_processed', 0) + 1
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        cur_chat_state = STATE_GET_USER_INFO
    else:
        cur_chat_state = State.get_by_user_id(user.id)['state']

        if not message.document and not message.photo:
            db.add_message_to_log(False, message.message_id, message.chat.id, user.id, None, message.text, None)
    state_processor = state_processors.get(cur_chat_state, prc_WTF)
    try:
        await state_processor(message, user)
    except Exception as e:
        error_text = traceback.format_exc()
        logger.error(f'SUPERSHIT: {e}')
        await bot_post_logging_message(error_text)


async def start(message: types.Message):
    logger.debug('start')
    user = User.get_by_chat_id(message.chat.id)
    if user:
        State.set_by_user_id(user.id, STATE_GET_USER_INFO)
    await bot.send_message(
        chat_id=message.chat.id,
        text="🤖 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль",
    )


async def recheck(message: types.Message):
    logger.debug('recheck')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE_TEACHER:
        return
    match = re.fullmatch(r'/recheck(?:_xd5fqk)?[\s_]+([a-zA-Z0-9]+)[\s_]+(\d+)([а-я])\.(\d+)([а-я]?)\s*',
                         message.text or '')
    if not match:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Пришлите запрос на перепроверку в формате\n«/recheck token problem», например «/recheck aa9bb4 3н.11а»",
        )
    else:
        token, lst, level, prob, item = match.groups()
        student = User.get_by_token(token)
        problem = Problem.get_by_key(level, int(lst), int(prob), item)
        if not student:
            await bot.send_message(chat_id=message.chat.id, text=f"🤖 Студент с токеном {token} не найден")
        if not problem:
            await bot.send_message(chat_id=message.chat.id, text=f"🤖 Задача {lst}{level}.{prob}{item} не найдена")
        if student and problem:
            message = await bot.send_message(chat_id=message.chat.id, text=f"Переотправили на проверку")
            await forward_discussion_and_start_checking(message.chat.id, message.message_id, student, problem, teacher)


async def set_student_level(message: types.Message):
    logger.debug('set_student_level')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE_TEACHER:
        return
    text = message.text.split()
    try:
        cmd, token, new_level = text
    except:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"/set_level token н/п",
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Студент с токеном {token} не найден",
        )
    if new_level == STUDENT_NOVICE:
        student.set_level(STUDENT_NOVICE)
        stud_msg = "Вы переведены в группу начинающих"
    elif new_level == STUDENT_PRO:
        student.set_level(STUDENT_PRO)
        stud_msg = "Вы переведены в группу продолжающих"
    else:
        return
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"Студент с токеном {token} переведён",
    )
    if student.chat_id:
        try:
            await bot.send_message(chat_id=student.chat_id, text=stud_msg)
        except:
            pass


async def level_novice(message: types.Message):
    logger.debug('level_novice')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу начинающих",
        )
        student.set_level(STUDENT_NOVICE)
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await process_regular_message(message)


async def level_pro(message: types.Message):
    logger.debug('level_pro')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу продолжающих",
        )
        student.set_level(STUDENT_PRO)
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await process_regular_message(message)


async def sos(message: types.Message):
    logger.debug('sos')
    user = User.get_by_chat_id(message.chat.id)
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
        State.set_by_user_id(user.id, STATE_WAIT_SOS_REQUEST)


async def prc_problems_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_problems_selected_callback')
    student = User.get_by_chat_id(query.message.chat.id)
    state = State.get_by_user_id(student.id)
    if state.get('state', None) == STATE_STUDENT_IS_SLEEPING:
        await bot_answer_callback_query(query.id)
        return
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    if not problem:
        await bot_answer_callback_query(query.id)
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await process_regular_message(query.message)
    # В зависимости от типа задачи разное поведение
    if problem.prob_type == PROB_TYPE_TEST:
        # Если это выбор из нескольких вариантов, то нужно сделать клавиатуру
        if problem.ans_type == ANS_TYPE_SELECT_ONE:
            await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text=f"Выбрана задача {problem}.\nВыберите ответ — один из следующих вариантов:",
                                        reply_markup=keyboards.build_test_answers(problem.ans_validation.split(';')))
        else:
            await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        text=f"Выбрана задача {problem}.\nТеперь введите ответ{ANS_HELP_DESCRIPTIONS[problem.ans_type]}",
                                        reply_markup=keyboards.build_cancel_task_submission())
        State.set_by_user_id(student.id, STATE_SENDING_TEST_ANSWER, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type in (PROB_TYPE_WRITTEN, PROB_TYPE_WRITTEN_BEFORE_ORALLY):
        await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                    text=f"Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 вашего решения.",
                                    reply_markup=keyboards.build_cancel_task_submission())
        State.set_by_user_id(student.id, STATE_SENDING_SOLUTION, problem_id)
        await bot_answer_callback_query(query.id)
    elif problem.prob_type == PROB_TYPE_ORALLY:
        await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                    text=f"Выбрана устная задача. "
                                         f"Её нужно сдавать в zoom-конференции. "
                                    # f"Желательно перед сдачей записать ответ и основные шаги решения на бумаге. "
                                    # f"Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. "
                                    # f"\nКогда у вас всё готово, "
                                         f"<b>Заходите в zoom-конференцию, идентификатор конференции:"
                                         f"\n87370688149, код доступа: 179179</b>. "
                                         f"\nПожалуйста, при входе поставьте актуальную подпись: ваши фамилию и имя. "
                                         f"Как только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. "
                                         f"После окончания сдачи нужно выйти из конференции. "
                                         f"Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. "
                                         f"Мы постараемся выделить время каждому, но ожидание может быть достаточно долгим.",
                                    disable_web_page_preview=True,
                                    parse_mode='HTML')
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await bot_answer_callback_query(query.id)
        await asyncio.sleep(5)
        await process_regular_message(query.message)

        # state = states.get_by_user_id(student.id)
        # if state['oral_problem_id'] is not None:
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы уже стоите в очереди на устную сдачу\. " \
        #                                 "Дождитесь, когда освободится один из преподавателей\. " \
        #                                 "Тогда можно будет сдать сразу несколько задач\.",
        #                            parse_mode="MarkdownV2")
        #     await bot_answer_callback_query(query.id)
        # else:
        #     try:
        #         await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
        #     except:
        #         pass
        #     waitlist.enter(student.id, problem.id)
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
        #                            parse_mode="MarkdownV2",
        #                            reply_markup=keyboards.build_exit_waitlist())
        #     await bot_answer_callback_query(query.id)
        #     await asyncio.sleep(4)
        #     await process_regular_message(query.message)


async def prc_list_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_list_selected_callback')
    list_num = int(query.data[2:])
    student = User.get_by_chat_id(query.message.chat.id)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Теперь выберите задачу",
                                reply_markup=keyboards.build_problems(list_num, student))
    await bot_answer_callback_query(query.id)


async def prc_show_list_of_lists_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_show_list_of_lists_callback')
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Вот список всех листков:",
                                reply_markup=keyboards.build_lessons())
    await bot_answer_callback_query(query.id)


async def prc_one_of_test_answer_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_one_of_test_answer_selected_callback')
    state = State.get_by_user_id(student.id)
    if state.get('state', None) != STATE_SENDING_TEST_ANSWER:
        logger.info('WRONG STATE', state, STATE_SENDING_TEST_ANSWER, 'STATE_SENDING_TEST_ANSWER')
        return
    selected_answer = query.data[2:]
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot.send_message(chat_id=query.message.chat.id, text=f"Выбран вариант {selected_answer}.")
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    text_to_student = check_test_ans_rate_limit(student.id, problem_id)
    if text_to_student:
        await bot.send_message(chat_id=query.message.chat.id, text=text_to_student)
        await asyncio.sleep(1)
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        logger.info(f'Ограничили студанта: {student.id}')
        await process_regular_message(query.message)
        return
    problem = Problem.get_by_id(problem_id)
    if problem is None:
        logger.error('Сломался приём задач :(')
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
        await bot_answer_callback_query(query.id)
        await asyncio.sleep(1)
        await process_regular_message(query.message)
        return
    correct_answer = problem.cor_ans
    # await bot.send_message(chat_id=query.message.chat.id,
    #                        text=f"Выбран вариант {selected_answer}.")
    if selected_answer == correct_answer:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_SOLVED, selected_answer, RES_TYPE_TEST)
        text_to_student = f"✔️ {problem.congrat}"
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT_WRONG_ANSWER, selected_answer, RES_TYPE_TEST)
        text_to_student = f"❌ {problem.wrong_ans}"
    if os.environ.get('EXAM', None) == 'true':
        text_to_student = 'Ответ принят на проверку.'
    await bot.send_message(chat_id=query.message.chat.id, text=text_to_student)
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    await bot_answer_callback_query(query.id)
    await asyncio.sleep(1)
    await process_regular_message(query.message)


async def prc_cancel_task_submission_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_cancel_task_submission_callback')
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    # await bot.send_message(
    #     chat_id=message.chat.id,
    #     text="❓ Нажимайте на задачу, чтобы сдать её",
    #     reply_markup=keyboards.build_problems(problems.last_lesson, user),
    # )
    await bot_edit_message_text(message_id=query.message.message_id, chat_id=query.message.chat.id,
                                text="❓ Нажимайте на задачу, чтобы сдать её",
                                reply_markup=keyboards.build_problems(Problem.last_lesson_num(), student))
    await bot_answer_callback_query(query.id)


async def prc_get_written_task_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_written_task_callback')
    # Так, препод указал, что хочет проверять письменные задачи
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    top = WrittenQueue.take_top(teacher.id)
    if not top:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ничего себе! Все письменные задачи проверены!")
        State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
        await bot_answer_callback_query(query.id)
        await process_regular_message(query.message)
    else:
        # Даём преподу 10 топовых задач на выбор
        await bot.send_message(chat_id=teacher.chat_id, text="Выберите задачу для проверки",
                               reply_markup=keyboards.build_teacher_select_written_problem(top))
        # keyboards.build_teacher_actions


async def prc_teacher_cancel_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_teacher_cancel_callback')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def forward_discussion_and_start_checking(chat_id, message_id, student, problem, teacher):
    logger.debug('forward_discussion_and_start_checking')
    await bot_edit_message_text(chat_id=chat_id, message_id=message_id,
                                text=f"Проверяем задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})\n"
                                     f"Школьник {student.token} {student.surname} {student.name}\n"
                                     f"⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",
                                reply_markup=None)
    discussion = WrittenQueue.get_discussion(student.id, problem.id)
    for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не привысить лимит
        # Пока временно делаем только forward'ы. Затем нужно будет изолировать учителя от студента
        forward_success = False
        if row['chat_id'] and row['tg_msg_id']:
            try:
                await bot.forward_message(chat_id, row['chat_id'], row['tg_msg_id'])
                forward_success = True
            except aiogram.utils.exceptions.TelegramAPIError:
                await bot.send_message(chat_id=chat_id, text='Сообщение было удалено...')
        if forward_success:
            pass
        elif row['text']:
            await bot.send_message(chat_id=chat_id, text=row['text'])
        elif row['attach_path']:
            # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
            path = row['attach_path'].replace('/web/vmsh179bot/vmsh179bot/', '')
            file, _, ext = path.rpartition('.')
            if ext and ext.lower() in ('jpg', 'png'):
                input_file = types.input_file.InputFile(path)
                await bot.send_photo(chat_id=chat_id, photo=input_file)
            elif ext.lower() == 'txt':
                text = open(row['attach_path'], 'r', encoding='utf-8').read()
                await bot.send_message(chat_id=chat_id, text=text)
            else:
                # Хм... Странный файл
                try:
                    await bot.send_document(chat_id=chat_id, document=types.input_file.InputFile(path))
                except:
                    pass
    State.set_by_user_id(teacher.id, STATE_TEACHER_IS_CHECKING_TASK, problem.id, last_teacher_id=teacher.id,
                         last_student_id=student.id)
    await bot.send_message(chat_id=chat_id,
                           text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n'
                                'Напишите комментарий или скриншот 📸 вашей проверки (или просто поставьте плюс)',
                           reply_markup=keyboards.build_written_task_checking_verdict(student, problem))


async def prc_written_task_selected_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_selected_callback')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    chat_id = query.message.chat.id
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    await bot_answer_callback_query(query.id)
    # Блокируем задачу
    is_unlocked = WrittenQueue.mark_being_checked(student.id, problem.id, teacher.id)
    if not is_unlocked:
        await bot.send_message(chat_id=chat_id, text='Эту задачу уже кто-то взялся проверять.')
        State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
        await process_regular_message(query.message)
        return
    await forward_discussion_and_start_checking(chat_id, query.message.message_id, student, problem, teacher)


async def prc_written_task_ok_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_ok_callback')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем задачу как решённую и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_SOLVED, None, RES_TYPE_WRITTEN)
    WrittenQueue.delete_from_queue(student.id, problem.id)
    await bot_answer_callback_query(query.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'👍 Отлично, поставили плюсик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}! Для исправления:\n'
                                f'<pre>/recheck {student.token} {problem.lesson}{problem.level}.{problem.prob}{problem.item}</pre>',
                           parse_mode='HTML')
    State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    student_chat_id = User.get_by_id(student.id).chat_id
    try:
        discussion = WrittenQueue.get_discussion(student.id, problem.id)
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
                    await bot.forward_message(student_chat_id, row['chat_id'], row['tg_msg_id'],
                                              disable_notification=True)
                elif row['text']:
                    await bot.send_message(chat_id=student_chat_id, text=row['text'], disable_notification=True)
                elif row['attach_path']:
                    # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
                    input_file = types.input_file.InputFile(row['attach_path'])
                    await bot.send_photo(chat_id=student_chat_id, photo=input_file, disable_notification=True)
            await bot.send_message(chat_id=student_chat_id,
                                   text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n',
                                   disable_notification=True)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student_chat_id}\n{e}')
    await process_regular_message(query.message)


async def prc_written_task_bad_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_bad_callback')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем решение как неверное и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_WRONG_ANSWER, None, RES_TYPE_WRITTEN)
    db.delete_plus(student_id, problem.id, VERDICT_WRONG_ANSWER)
    WrittenQueue.delete_from_queue(student.id, problem.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'❌ Эх, поставили минусик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} '
                                f'школьнику {student.token} {student.surname} {student.name}! Для исправления:\n'
                                f'<pre>/recheck {student.token} {problem.lesson}{problem.level}.{problem.prob}{problem.item}</pre>',
                           parse_mode='HTML')

    # Пересылаем переписку школьнику
    student_chat_id = User.get_by_id(student.id).chat_id
    try:
        discussion = WrittenQueue.get_discussion(student.id, problem.id)
        await bot.send_message(chat_id=student_chat_id,
                               text=f"Задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}) проверили и сделали замечания:\n"
                                    f"Пересылаю всю переписку.\n"
                                    f"⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",
                               disable_notification=True)
        for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не привысить лимит
            # Пока временно делаем только forward'ы. Затем нужно будет изолировать учителя от студента
            if row['chat_id'] and row['tg_msg_id']:
                try:
                    await bot.forward_message(student_chat_id, row['chat_id'], row['tg_msg_id'],
                                              disable_notification=True)
                except aiogram.utils.exceptions.BadRequest as e:
                    logger.error(f'Почему-то не отфорвардилось... {student_chat_id}\n{e}')
            elif row['text']:
                await bot.send_message(chat_id=student_chat_id, text=row['text'], disable_notification=True)
            elif row['attach_path']:
                # TODO Pass a file_id as String to send a photo that exists on the Telegram servers (recommended)
                input_file = types.input_file.InputFile(row['attach_path'])
                await bot.send_photo(chat_id=student_chat_id, photo=input_file, disable_notification=True)
        await bot.send_message(chat_id=student_chat_id,
                               text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n',
                               disable_notification=True)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student_chat_id}\n{e}')
    State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def prc_get_queue_top_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_queue_top_callback')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    top = Waitlist.top(1)
    if not top:
        # Если в очереди пусто, то шлём сообщение и выходим.
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Сейчас очередь пуста. Повторите через пару минут.")
        await bot_answer_callback_query(query.id)
        await prc_teacher_select_action(query.message, teacher)
        return

    student = User.get_by_id(top[0]['student_id'])
    problem = Problem.get_by_id(top[0]['problem_id'])
    State.set_by_user_id(teacher.id, STATE_TEACHER_ACCEPTED_QUEUE, oral_problem_id=problem.id,
                         last_student_id=student.id)
    Waitlist.leave(student.id)

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
        State.set_by_user_id(student.id, STATE_STUDENT_IS_IN_CONFERENCE, oral_problem_id=problem.id,
                             last_teacher_id=teacher.id)
        await bot.send_message(chat_id=student.chat_id, text="Нажмите по окончанию.",
                               reply_markup=keyboards.build_student_in_conference(),
                               parse_mode='HTML')
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
        # Снимаем со школьника статус сдачи
        State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    else:
        await bot_answer_callback_query(query.id, show_alert=True)
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"<b>Ваш ученик: {student}.\n"
                                    f"{problem}.\n"
                                    f"<a href=\"{teacher_link}\">Войдите в конференцию</a></b>",
                               parse_mode='HTML')
    await bot_answer_callback_query(query.id)
    await process_regular_message(message=query.message)


async def prc_ins_oral_plusses(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_ins_oral_plusses')
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot.send_message(chat_id=teacher.chat_id,
                           text=f"Введите фамилию школьника (можно начало фамилии)")
    await bot_answer_callback_query(query.id)
    State.set_by_user_id(teacher.id, STATE_TEACHER_WRITES_STUDENT_NAME)


async def prc_set_verdict_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_set_verdict_callback')
    state = State.get_by_user_id(teacher.id)
    problem_id = state['oral_problem_id']
    # TODO !!!
    if problem_id is None:
        logger.info("WAT problem_id is None")
        return
    problem = Problem.get_by_id(problem_id)
    verdict = int(query.data.split('_')[1])
    student_id = state['last_student_id']
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    await bot_answer_callback_query(query.id)
    State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    db.add_result(student_id, problem_id, problem.level, problem.lesson, teacher.id, verdict, '', RES_TYPE_ZOOM)
    await process_regular_message(query.message)


async def prc_get_out_of_waitlist_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_get_out_of_waitlist_callback')
    state = State.get_by_user_id(student.id)
    teacher = User.get_by_id(state['last_teacher_id'])
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    Waitlist.leave(student.id)
    State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
    if teacher:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ученик {student.surname} {student.name} {student.token} завершил устную сдачу.\n")
    await bot_answer_callback_query(query.id)
    await process_regular_message(query.message)


async def prc_student_selected_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_student_selected_callback')
    _, student_id = query.data.split('_')
    student_id = int(student_id)
    student = User.get_by_id(student_id)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None,
                                text=f"Вносим плюсики школьнику:\n"
                                     f"{student.surname} {student.name} {student.token} уровень {student.level}")
    await bot.send_message(chat_id=query.message.chat.id,
                           text="Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)",
                           reply_markup=keyboards.build_verdict(plus_ids=set(), minus_ids=set(), student=student))
    State.set_by_user_id(teacher.id, STATE_TEACHER_WRITES_STUDENT_NAME, last_student_id=student.id)
    await bot_answer_callback_query(query.id)


async def prc_add_or_remove_oral_plus_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_add_or_remove_oral_plus_callback')
    _, problem_id, plus_ids, minus_ids = query.data.split('_')
    problem_id = int(problem_id)
    plus_ids = set() if not plus_ids else {int(prb_id) for prb_id in plus_ids.split(',')}
    minus_ids = set() if not minus_ids else {int(prb_id) for prb_id in minus_ids.split(',')}
    # TODO
    if problem_id in plus_ids:
        plus_ids.discard(problem_id)
        minus_ids.add(problem_id)
    elif problem_id in minus_ids:
        minus_ids.discard(problem_id)
    else:
        plus_ids.add(problem_id)
    state = State.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = User.get_by_id(student_id)
    await bot_edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=keyboards.build_verdict(plus_ids=plus_ids, minus_ids=minus_ids,
                                                                             student=student))
    await bot_answer_callback_query(query.id)


async def prc_finish_oral_round_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_finish_oral_round_callback')
    _, plus_ids, minus_ids = query.data.split('_')
    plus_ids = set() if not plus_ids else {int(prb_id) for prb_id in plus_ids.split(',')}
    minus_ids = set() if not minus_ids else {int(prb_id) for prb_id in minus_ids.split(',')}
    state = State.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = User.get_by_id(student_id)
    if not student:
        teacher_message = await bot.send_message(chat_id=query.message.chat.id,
                                                 text=f"Что-то в боте сломалось и результат оценки не засчитан. :( Попробуйте ещё раз.")
        await bot_answer_callback_query(query.id)
        State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
        await process_regular_message(teacher_message)
        return

    pluses = [Problem.get_by_id(prb_id) for prb_id in plus_ids]
    minuses = [Problem.get_by_id(prb_id) for prb_id in minus_ids]
    human_readable_pluses = [f'{plus.lesson}{plus.level}.{plus.prob}{plus.item}' for plus in pluses]
    human_readable_minuses = [f'{plus.lesson}{plus.level}.{plus.prob}{plus.item}' for plus in minuses]
    # Проставляем плюсики
    for problem in pluses:
        db.add_result(student_id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_SOLVED, None, RES_TYPE_ZOOM)
    for problem in minuses:
        db.delete_plus(student_id, problem.id, VERDICT_WRONG_ANSWER)
        db.add_result(student_id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT_WRONG_ANSWER, None, RES_TYPE_ZOOM)
    await bot_edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text=f"Школьник: {student.token} {student.surname} {student.name}\n"
                                     f"\nПоставлены плюсы за задачи: {', '.join(human_readable_pluses)}"
                                     f"\nПоставлены минусы за задачи: {', '.join(human_readable_minuses)}",
                                reply_markup=None)
    try:
        student_state = State.get_by_user_id(student.id)
        student_message = await bot.send_message(chat_id=student.chat_id,
                                                 text=f"В результате устного приёма вам поставили плюсики за задачи: {', '.join(human_readable_pluses)}",
                                                 disable_notification=True)
        if student_state['state'] == STATE_STUDENT_IS_IN_CONFERENCE:
            State.set_by_user_id(student.id, STATE_GET_TASK_INFO)
            await process_regular_message(student_message)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
    await bot_answer_callback_query(query.id)
    State.set_by_user_id(teacher.id, STATE_TEACHER_SELECT_ACTION)
    await process_regular_message(query.message)


async def exit_waitlist(message: types.Message):
    logger.debug('exit_waitlist')
    user = User.get_by_chat_id(message.chat.id)
    Waitlist.leave(user.id)
    await bot.send_message(
        chat_id=message.chat.id,
        text="Вы успешно покинули очередь.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await process_regular_message(message)

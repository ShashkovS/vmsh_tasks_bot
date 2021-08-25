import os
import io
import datetime
import re
import asyncio
import traceback
from aiogram.dispatcher.webhook import types

from helpers.consts import *
from helpers.config import logger, config
from helpers.obj_classes import User, Problem, State, Waitlist, WrittenQueue, db
from helpers.bot import bot, reg_callback, dispatcher, reg_state
from handlers import student_keyboards
from handlers.main_handlers import process_regular_message
from helpers.checkers import ANS_CHECKER, ANS_REGEX

SOLS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../solutions')
WHITEBOARD_LINK = "https://www.shashkovs.ru/jitboard.html?{}"
GLOBALS_FOR_TEST_FUNCTION_CREATION = {
    '__builtins__': None, 're': re,
    'bool': bool, 'float': float, 'int': int, 'list': list, 'range': range, 'set': set, 'str': str, 'tuple': tuple,
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'enumerate': enumerate, 'format': format, 'len': len,
    'max': max, 'min': min, 'round': round, 'sorted': sorted, 'sum': sum, 'map': map,
}
is_py_func = re.compile(r'^\s*def \w+\s*\(')


@reg_state(STATE.GET_TASK_INFO)
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

    slevel = f'(уровень «{student.level.slevel}»)'
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"❓ Нажимайте на задачу, чтобы сдать её {slevel}",
        reply_markup=student_keyboards.build_problems(Problem.last_lesson_num(), student),
    )


@reg_state(STATE.SENDING_SOLUTION)
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
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


def check_test_ans_rate_limit(student_id: int, problem_id: int):
    logger.debug('check_test_ans_rate_limit')
    per_day, per_hour = db.check_num_answers(student_id, problem_id)
    text_to_student = None
    if per_hour >= 3:
        text_to_student = '💤⌛ В течение одного часа бот не принимает больше 3 ответов. Отправьте ваш ответ в начале следующего часа.'
    elif per_day >= 6:
        text_to_student = '💤⌛ В течение одного дня бот не принимает больше 6 ответов. Отправьте ваш ответ завтра.'
    return text_to_student


@reg_state(STATE.SENDING_TEST_ANSWER)
async def prc_sending_test_answer_state(message: types.Message, student: User, check_functions_cache={}):
    logger.debug('prc_sending_test_answer_state')
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    text_to_student = check_test_ans_rate_limit(student.id, problem_id)
    if text_to_student:
        await bot.send_message(chat_id=message.chat.id, text=text_to_student)
        await asyncio.sleep(1)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        logger.info(f'Ограничили студанта: {student.id}')
        await process_regular_message(message)
        return
    problem = Problem.get_by_id(problem_id)
    student_answer = (message.text or '').strip()
    # Если тип ответа — выбор из нескольких вариантов ответа, про проверим, если ответ среди вариантов
    if problem.ans_type == ANS_TYPE.SELECT_ONE and student_answer[:24] not in [ans.strip()[:24] for ans in problem.cor_ans.split(';')]:  # TODO 24!!!
        await bot.send_message(chat_id=message.chat.id,
                               text=f"❌ Выберите один из вариантов: {', '.join(problem.ans_validation.split(';'))}")
        return
    # Сначала проверим, проходит ли ответ валидацию регуляркой (для стандартных типов или если она указана)
    elif problem.ans_type != ANS_TYPE.SELECT_ONE:
        validation_regex = (problem.ans_validation and re.compile(problem.ans_validation)) or ANS_REGEX.get(problem.ans_type, None)
        if validation_regex and not validation_regex.fullmatch(student_answer):
            await bot.send_message(chat_id=message.chat.id,
                                   text=f"❌ {problem.validation_error}")
            return

    # Здесь мы проверяем ответ в зависимости от того, как проверять
    if is_py_func.match(problem.cor_ans):
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
            await bot.post_logging_message(error_text)

        if additional_message:
            await bot.send_message(chat_id=message.chat.id, text=additional_message)
    else:
        # Здесь у нас сравнение при помощи чекера. Типа равенство чисел или дробей там, или последовательностей/множеств
        checker = ANS_CHECKER[problem.ans_type]
        correct_answer = problem.cor_ans
        if ';' not in correct_answer:
            answer_is_correct = checker(student_answer, correct_answer)
        else:
            answer_is_correct = any(checker(student_answer, one_correct) for one_correct in correct_answer.split(';'))

    if answer_is_correct:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT.SOLVED, student_answer, RES_TYPE.TEST)
        text_to_student = f"✔️ {problem.congrat}"
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT.WRONG_ANSWER, student_answer, RES_TYPE.TEST)
        text_to_student = f"❌ {problem.wrong_ans}"
    if os.environ.get('EXAM', None) == 'true':
        text_to_student = 'Ответ принят на проверку.'
    await bot.send_message(chat_id=message.chat.id, text=text_to_student)
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


@reg_state(STATE.WAIT_SOS_REQUEST)
async def prc_wait_sos_request_state(message: types.Message, student: User):
    logger.debug('prc_wait_sos_request_state')
    try:
        await bot.forward_message(config.sos_channel, message.chat.id, message.message_id)
    except:
        logger.info(f'Не удалось переслать SOS-сообщение в канал {config.sos_channel}')
    await bot.send_message(chat_id=message.chat.id, text=f"Переслал сообщение.")
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


@reg_state(STATE.STUDENT_IS_SLEEPING)
async def prc_student_is_sleeping_state(message: types.message, student: User):
    logger.debug('prc_student_is_sleeping_state')
    await bot.send_message(chat_id=message.chat.id,
                           text="🤖 Приём задач ботом окончен до начала следующего занятия.\n"
                                "Заходите в канал @vmsh_179_5_6_2020 кружка за новостями и решениями.")


@reg_state(STATE.STUDENT_IS_IN_CONFERENCE)
async def prc_student_is_in_conference_state(message: types.message, student: User):
    logger.debug('prc_student_is_in_conference_state')
    # Ничего не делаем, ждём callback'а
    pass


@dispatcher.message_handler(commands=['level_novice'])
async def level_novice(message: types.Message):
    logger.debug('level_novice')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу начинающих",
        )
        student.set_level(LEVEL.NOVICE)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await process_regular_message(message)


@dispatcher.message_handler(commands=['level_pro'])
async def level_pro(message: types.Message):
    logger.debug('level_pro')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу продолжающих",
        )
        student.set_level(LEVEL.PRO)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await process_regular_message(message)


@dispatcher.message_handler(commands=['level_expert'])
async def level_expert(message: types.Message):
    logger.debug('level_expert')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу экспертов",
        )
        student.set_level(LEVEL.EXPERT)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await process_regular_message(message)


@dispatcher.message_handler(commands=['sos'])
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
        State.set_by_user_id(user.id, STATE.WAIT_SOS_REQUEST)


@reg_callback(CALLBACK.PROBLEM_SELECTED)
async def prc_problems_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_problems_selected_callback')
    student = User.get_by_chat_id(query.message.chat.id)
    state = State.get_by_user_id(student.id)
    if state.get('state', None) == STATE.STUDENT_IS_SLEEPING:
        await bot.answer_callback_query_ig(query.id)
        return
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    if not problem:
        await bot.answer_callback_query_ig(query.id)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await process_regular_message(query.message)
        return
    # В зависимости от типа задачи разное поведение
    elif problem.prob_type == PROB_TYPE.TEST:
        # Если это выбор из нескольких вариантов, то нужно сделать клавиатуру
        if problem.ans_type == ANS_TYPE.SELECT_ONE:
            await bot.send_message(chat_id=query.message.chat.id,
                                   text=f"Выбрана задача {problem}.\nВыберите ответ — один из следующих вариантов:",
                                   reply_markup=student_keyboards.build_test_answers(problem.ans_validation.split(';')))
        else:
            await bot.send_message(chat_id=query.message.chat.id,
                                   text=f"Выбрана задача {problem}.\nТеперь введите ответ{problem.ans_type.descr}",
                                   reply_markup=student_keyboards.build_cancel_task_submission())
        State.set_by_user_id(student.id, STATE.SENDING_TEST_ANSWER, problem_id)
        await bot.answer_callback_query_ig(query.id)
    elif problem.prob_type in (PROB_TYPE.WRITTEN, PROB_TYPE.WRITTEN_BEFORE_ORALLY):
        await bot.send_message(chat_id=query.message.chat.id,
                               text=f"Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 вашего решения.",
                               reply_markup=student_keyboards.build_cancel_task_submission())
        State.set_by_user_id(student.id, STATE.SENDING_SOLUTION, problem_id)
        await bot.answer_callback_query_ig(query.id)
    elif problem.prob_type == PROB_TYPE.ORALLY:
        await bot.send_message(chat_id=query.message.chat.id,
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
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await bot.answer_callback_query_ig(query.id)
        await asyncio.sleep(5)
        await process_regular_message(query.message)

        # state = states.get_by_user_id(student.id)
        # if state['oral_problem_id'] is not None:
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы уже стоите в очереди на устную сдачу\. " \
        #                                 "Дождитесь, когда освободится один из преподавателей\. " \
        #                                 "Тогда можно будет сдать сразу несколько задач\.",
        #                            parse_mode="MarkdownV2")
        #     await bot.answer_callback_query_ig(query.id)
        # else:
        #     try:
        #         await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
        #     except:
        #         pass
        #     waitlist.enter(student.id, problem.id)
        #     await bot.send_message(chat_id=query.message.chat.id,
        #                            text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
        #                            parse_mode="MarkdownV2",
        #                            reply_markup=student_keyboards.build_exit_waitlist())
        #     await bot.answer_callback_query_ig(query.id)
        #     await asyncio.sleep(4)
        #     await process_regular_message(query.message)


@reg_callback(CALLBACK.LIST_SELECTED)
async def prc_list_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_list_selected_callback')
    list_num = int(query.data[2:])
    student = User.get_by_chat_id(query.message.chat.id)
    await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Теперь выберите задачу",
                                reply_markup=student_keyboards.build_problems(list_num, student))
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.SHOW_LIST_OF_LISTS)
async def prc_show_list_of_lists_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_show_list_of_lists_callback')
    await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                text="Вот список всех листков:",
                                reply_markup=student_keyboards.build_lessons())
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.ONE_OF_TEST_ANSWER_SELECTED)
async def prc_one_of_test_answer_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_one_of_test_answer_selected_callback')
    state = State.get_by_user_id(student.id)
    if state.get('state', None) != STATE.SENDING_TEST_ANSWER:
        logger.info('WRONG STATE', state, STATE.SENDING_TEST_ANSWER, 'STATE.SENDING_TEST_ANSWER')
        return
    selected_answer = query.data[2:]
    await bot.send_message(chat_id=query.message.chat.id, text=f"Выбран вариант {selected_answer}.")
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    text_to_student = check_test_ans_rate_limit(student.id, problem_id)
    if text_to_student:
        await bot.send_message(chat_id=query.message.chat.id, text=text_to_student)
        await asyncio.sleep(1)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        # Удаляем варианты после изменения state'а. Иначе можно «зависнуть»
        await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
        logger.info(f'Ограничили студанта: {student.id}')
        await process_regular_message(query.message)
        return
    problem = Problem.get_by_id(problem_id)
    if problem is None:
        logger.error('Сломался приём задач :(')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        # Удаляем варианты после изменения state'а. Иначе можно «зависнуть»
        await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
        await bot.answer_callback_query_ig(query.id)
        await asyncio.sleep(1)
        await process_regular_message(query.message)
        return
    correct_answer = problem.cor_ans
    # await bot.send_message(chat_id=query.message.chat.id,
    #                        text=f"Выбран вариант {selected_answer}.")
    if selected_answer[:24] == correct_answer[:24] or selected_answer[:24] in [ans.strip()[:24] for ans in correct_answer.split(';')]:  # TODO 24!!!
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT.SOLVED, selected_answer, RES_TYPE.TEST)
        text_to_student = f"✔️ {problem.congrat}"
    else:
        db.add_result(student.id, problem.id, problem.level, problem.lesson, None, VERDICT.WRONG_ANSWER, selected_answer, RES_TYPE.TEST)
        text_to_student = f"❌ {problem.wrong_ans}"
    if os.environ.get('EXAM', None) == 'true':
        text_to_student = 'Ответ принят на проверку.'
    await bot.send_message(chat_id=query.message.chat.id, text=text_to_student)
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    # Удаляем варианты после изменения state'а. Иначе можно «зависнуть»
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    await bot.answer_callback_query_ig(query.id)
    await asyncio.sleep(1)
    await process_regular_message(query.message)


@reg_callback(CALLBACK.CANCEL_TASK_SUBMISSION)
async def prc_cancel_task_submission_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_cancel_task_submission_callback')
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    try:
        await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except:
        pass
    await bot.answer_callback_query_ig(query.id)
    await process_regular_message(query.message)


@reg_callback(CALLBACK.GET_OUT_OF_WAITLIST)
async def prc_get_out_of_waitlist_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_get_out_of_waitlist_callback')
    state = State.get_by_user_id(student.id)
    teacher = User.get_by_id(state['last_teacher_id'])
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                        reply_markup=None)
    Waitlist.leave(student.id)
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    if teacher:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ученик {student.surname} {student.name} {student.token} завершил устную сдачу.\n")
    await bot.answer_callback_query_ig(query.id)
    await process_regular_message(query.message)


@dispatcher.message_handler(commands=['exit_waitlist'])
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

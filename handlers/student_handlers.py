import os
import re
import asyncio
import traceback
from typing import Tuple, Optional

import aiogram.utils.exceptions
from aiogram.dispatcher.webhook import types
from aiogram.utils.exceptions import BadRequest

from helpers.consts import *
from helpers.config import logger, config
from helpers.obj_classes import User, Problem, State, Waitlist, WrittenQueue, Result, db
from helpers.bot import bot, reg_callback, dispatcher, reg_state
from handlers import student_keyboards
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
MAX_CALLBACK_PAYLOAD_HOOK_LIMIT = 24


async def post_problem_keyboard(chat_id: int, student: User, *, blocked=False):
    prev_keyboard = db.get_last_keyboard(student.id)
    if prev_keyboard:
        try:
            await bot.edit_message_reply_markup_ig(chat_id=prev_keyboard['chat_id'], message_id=prev_keyboard['tg_msg_id'], reply_markup=None)
        except:
            pass
    if not blocked:
        text = f"❓ Нажимайте на задачу, чтобы сдать её\n(выбран уровень «{student.level.slevel}», здесь <a href=\"{student.level.url}\">условия</a>)"
    else:
        text = f"🤖 Приём задач ботом окончен до начала следующего занятия."
    keyb_msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=student_keyboards.build_problems(Problem.last_lesson_num(student.level), student),
    )
    db.set_last_keyboard(student.id, keyb_msg.chat.id, keyb_msg.message_id)


async def refresh_last_student_keyboard(student: User) -> bool:
    if not student:
        return False
    prev_keyboard = db.get_last_keyboard(student.id)
    if prev_keyboard:
        await bot.edit_message_reply_markup_ig(
            chat_id=prev_keyboard['chat_id'],
            message_id=prev_keyboard['tg_msg_id'],
            reply_markup=student_keyboards.build_problems(Problem.last_lesson_num(student.level), student)
        )
        return True
    return False


async def sleep_and_send_problems_keyboard(chat_id: int, student: User, sleep=1):
    if sleep > 0:
        await asyncio.sleep(sleep)
    await post_problem_keyboard(chat_id, student)


@reg_state(STATE.GET_TASK_INFO)
async def prc_get_task_info_state(message, student: User):
    logger.debug('prc_get_task_info_state')
    # Возможно, тут прилетел хвост галереи, которую мы успешно уже обработали.
    if message.media_group_id and db.media_group_check(message.media_group_id):
        await prc_sending_solution_state(message, student)
        return
    # Обрабатываем как обычно
    alarm = ''
    # Попытка сдать решение без выбранной задачи
    if message.photo or message.document:
        alarm = '❗❗❗ Файл НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n' \
                '(Можно посылать несколько фотографий решения в виде галереи, либо каждый раз нужно выбирать задачу.)'
    elif message.text and len(message.text) > 20:
        alarm = '❗❗❗ Текст НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n'
    sleep = 0
    if alarm:
        await bot.send_message(chat_id=message.chat.id, text=alarm, )
        sleep = 8
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student, sleep=sleep))


@reg_state(STATE.SENDING_SOLUTION)
async def prc_sending_solution_state(message: types.Message, student: User):
    logger.debug('prc_sending_solution_state')
    # Особый случай — это медиа-группы. Если несколько картинок  в одном сообщении,
    # то к нам в бот они придут в виде нескольких сообщений с одинаковым media_group_id.
    # Поэтому если media_group_id задан, то для первого сообщения нужно сохранить, к какой он задаче,
    # а потом уже брать id задачи из сохранённого
    next_media_group_message = False
    if message.media_group_id:
        problem_id = db.media_group_check(message.media_group_id)
        if problem_id:
            next_media_group_message = True
        else:
            problem_id = State.get_by_user_id(student.id)['problem_id']
            duplicate = db.media_group_add(message.media_group_id, problem_id)
            # Могло так случиться, что в другом потоке в параллель добавили
            if duplicate:
                problem_id = db.media_group_check(message.media_group_id)
                next_media_group_message = True
    else:
        problem_id = State.get_by_user_id(student.id)['problem_id']
    file_name = None
    text = message.text

    # Перестали сохранять файлы к себе, вроде в этом нет необходимости
    # downloaded = []
    # if text:
    #     downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
    #     downloaded.append((io.BytesIO(text.encode('utf-8')), 'text.txt'))
    # # for photo in message.photo:
    # if message.photo:
    #     file_info = await bot.get_file(message.photo[-1].file_id)
    #     downloaded_file = await bot.download_file(file_info.file_path)
    #     filename = file_info.file_path
    #     downloaded.append((downloaded_file, filename))
    # if message.document:
    #     if message.document.file_size > 5 * 1024 * 1024:
    #         await bot.send_message(chat_id=message.chat.id,
    #                                text=f"❌ Размер файла превышает ограничение в 5 мегабайт")
    #         return
    #     file_id = message.document.file_id
    #     file_info = await bot.get_file(file_id)
    #     downloaded_file = await bot.download_file(file_info.file_path)
    #     filename = file_info.file_path
    #     downloaded.append((downloaded_file, filename))
    # for bin_data, filename in downloaded:
    #     ext = filename[filename.rfind('.') + 1:]
    #     cur_ts = datetime.datetime.now().isoformat().replace(':', '-')
    #     file_name = os.path.join(SOLS_PATH,
    #                              f'{student.token} {student.surname} {student.name}',
    #                              f'{problem.lesson}',
    #                              f'{problem.lesson}{problem.level}_{problem.prob}{problem.item}_{cur_ts}.{ext}')
    #     os.makedirs(os.path.dirname(file_name), exist_ok=True)
    #     db.add_message_to_log(False, message.message_id, message.chat.id, student.id, None, message.text, file_name)
    #     with open(file_name, 'wb') as file:
    #         file.write(bin_data.read())
    WrittenQueue.add_to_discussions(student.id, problem_id, None, text, file_name, message.chat.id, message.message_id)
    if not next_media_group_message:
        WrittenQueue.add_to_queue(student.id, problem_id)
        await bot.send_message(
            chat_id=message.chat.id,
            text="Принято на проверку" if (problem_id > 0) else "Вопрос записан"
        )
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id,   student))


def check_test_ans_rate_limit(student_id: int, problem_id: int):
    logger.debug('check_test_ans_rate_limit')
    per_day, per_hour = db.check_num_answers(student_id, problem_id)
    text_to_student = None
    if per_hour >= 3:
        text_to_student = '💤⌛ В течение одного часа бот не принимает больше 3 ответов. Отправьте ваш ответ в начале следующего часа.'
    elif per_day >= 6:
        text_to_student = '💤⌛ В течение одного дня бот не принимает больше 6 ответов. Отправьте ваш ответ завтра.'
    return text_to_student


def run_py_func_checker(problem: Problem, student_answer: str, *, check_functions_cache={}) -> Tuple[bool, Optional[str], Optional[str]]:
    func_code = problem.cor_ans_checker
    func_name = re.search(r'\s*def\s+(\w+)', func_code)[1]
    if func_name in check_functions_cache:
        test_func = check_functions_cache[func_name]
    else:
        locs = {}
        # О-о-очень опасный кусок :)
        exec(func_code, GLOBALS_FOR_TEST_FUNCTION_CREATION, locs)
        func_name, test_func = locs.popitem()
        check_functions_cache[func_name] = test_func
    result = additional_message = answer_is_correct = error_text = None
    try:
        result = test_func(student_answer)
        answer_is_correct, additional_message = result
    except Exception as e:
        error_text = f'PYCHECKER_ERROR: {traceback.format_exc()}\nFUNC_CODE:\n{func_code.replace(" ", "_")}\nENTRY:\n{student_answer}\nRESULT:\n{result!r}'
        logger.error(f'PYCHECKER_ERROR: {e}\nFUNC_CODE:\n{func_code}\nRESULT:\n{result!r}')
    return answer_is_correct, additional_message, error_text


@unique
class ANS_CHECK_VERDICT(IntEnum):
    INCORRECT_SELECT = -2
    VALIDATION_NOT_PASSED = -3
    RATE_LIMIT = -4
    CORRECT = 1
    WRONG = -1


def check_test_problem_answer(problem: Problem, student: Optional[User], student_answer: str, *, check_functions_cache={}) -> Tuple[
    ANS_CHECK_VERDICT, Optional[str], Optional[str]]:
    logger.debug('check_test_problem_answer')
    answer_is_correct = additional_message = error_text = None
    if student_answer is None:
        student_answer = ''

    # Проверяем на перебор
    if student:  # При перепроверке данная проверка не выполняется
        text_to_student = check_test_ans_rate_limit(student.id, problem.id) if student.type == USER_TYPE.STUDENT else None
        if text_to_student:
            return ANS_CHECK_VERDICT.RATE_LIMIT, text_to_student, error_text

    # Если тип ответа — выбор из нескольких вариантов ответа, то это «простой» особый случай
    if problem.ans_type == ANS_TYPE.SELECT_ONE:
        student_answer_cut = student_answer.strip()[:MAX_CALLBACK_PAYLOAD_HOOK_LIMIT].strip().lower()
        if student_answer_cut in [ans.strip()[:MAX_CALLBACK_PAYLOAD_HOOK_LIMIT].strip().lower() for ans in problem.cor_ans.split(';')]:
            return ANS_CHECK_VERDICT.CORRECT, additional_message, error_text
        if student_answer_cut not in [ans.strip()[:MAX_CALLBACK_PAYLOAD_HOOK_LIMIT].strip().lower() for ans in problem.ans_validation.split(';')]:
            return ANS_CHECK_VERDICT.INCORRECT_SELECT, additional_message, error_text
        return ANS_CHECK_VERDICT.WRONG, additional_message, error_text

    # Сначала проверим, проходит ли ответ валидацию регуляркой (для стандартных типов или если она указана)
    validation_regex = (problem.ans_validation and re.compile(problem.ans_validation)) or ANS_REGEX.get(problem.ans_type, None)
    if validation_regex and not validation_regex.fullmatch(student_answer):
        return ANS_CHECK_VERDICT.VALIDATION_NOT_PASSED, additional_message, error_text
    # Здесь мы проверяем ответ в зависимости от того, как проверять
    if problem.cor_ans_checker and is_py_func.match(problem.cor_ans_checker):
        answer_is_correct, additional_message, error_text = run_py_func_checker(problem, student_answer)
    else:
        # Здесь у нас сравнение при помощи чекера. Типа равенство чисел или дробей там, или последовательностей/множеств
        checker = ANS_CHECKER[problem.ans_type]
        correct_answer = problem.cor_ans
        if problem.ans_type != ANS_TYPE.POLYNOMIAL:
            if ';' not in correct_answer:
                answer_is_correct = checker(student_answer, correct_answer)
            else:
                answer_is_correct = any(checker(student_answer, one_correct) for one_correct in correct_answer.split(';'))
        elif problem.ans_type == ANS_TYPE.POLYNOMIAL:
            # Чтобы давать информативное сообщение об ошибке, мы выдаём вход, на котором ответы отличаются.
            valid, func_values = checker(student_answer)
            if not valid:
                answer_is_correct = False
                additional_message = func_values
            else:
                _, corr_func_values = checker(correct_answer)
                answer_is_correct = True
                for x, (stv, crv) in enumerate(zip(func_values, corr_func_values)):
                    if abs(stv - crv) > 1e-8:
                        answer_is_correct = False
                        additional_message = f'При n={x} получилось {stv}, а должно было получиться {crv}'
                        break
    if answer_is_correct:
        return ANS_CHECK_VERDICT.CORRECT, additional_message, error_text
    return ANS_CHECK_VERDICT.WRONG, additional_message, error_text


async def check_answer_and_react(chat_id: int, problem: Problem, student: User, student_answer: str):
    check_verict, additional_message, error_text = check_test_problem_answer(problem, student, student_answer)
    if error_text:
        await bot.post_logging_message(error_text)
    if additional_message:
        await bot.send_message(chat_id=chat_id, text=additional_message)
    if check_verict == ANS_CHECK_VERDICT.INCORRECT_SELECT:
        await bot.send_message(chat_id=chat_id, text=f"❌ Выберите один из вариантов: {', '.join(problem.ans_validation.split(';'))}")
    elif check_verict == ANS_CHECK_VERDICT.VALIDATION_NOT_PASSED:
        await bot.send_message(chat_id=chat_id, text=f"❌ {problem.validation_error}")
    elif check_verict == ANS_CHECK_VERDICT.RATE_LIMIT:
        logger.info(f'Ограничили студента: {student.id}')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(chat_id, student))
    else:
        if check_verict == ANS_CHECK_VERDICT.CORRECT:
            Result.add(student, problem, None, VERDICT.SOLVED, student_answer, RES_TYPE.TEST)
            text_to_student = f"✔️ {problem.congrat}"
        # elif check_verict == ANS_CHECK_VERDICT.WRONG:
        else:
            Result.add(student, problem, None, VERDICT.WRONG_ANSWER, student_answer, RES_TYPE.TEST)
            text_to_student = f"❌ {problem.wrong_ans}"
        if os.environ.get('EXAM', None) == 'true':
            text_to_student = 'Ответ принят на проверку.'
        await bot.send_message(chat_id=chat_id, text=text_to_student)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(chat_id, student))


@reg_state(STATE.SENDING_TEST_ANSWER)
async def prc_sending_test_answer_state(message: types.Message, student: User, check_functions_cache={}):
    logger.debug('prc_sending_test_answer_state')
    state = State.get_by_user_id(student.id)
    problem_id = state['problem_id']
    problem = Problem.get_by_id(problem_id)
    student_answer = (message.text or '').strip()
    await check_answer_and_react(message.chat.id, problem, student, student_answer)


@reg_state(STATE.WAIT_SOS_REQUEST)
async def prc_wait_sos_request_state(message: types.Message, student: User):
    logger.debug('prc_wait_sos_request_state')
    state = State.get_by_user_id(student.id)
    problem_id = state.get("problem_id", None)
    if problem_id:
        problem = Problem.get_by_id(problem_id)
        problem_text = f"{problem}"
    else:
        problem_text = ""
    try:
        await bot.send_message(config.sos_channel, parse_mode="HTML",
                               text=f'<pre>{student.surname} {student.name} {student.level} {student.token} {ONLINE_MODE(student.online).__str__()[12:]}</pre>{problem_text}')
        await bot.forward_message(config.sos_channel, message.chat.id, message.message_id)
    except:
        logger.info(f'Не удалось переслать SOS-сообщение в канал {config.sos_channel}')
    await bot.send_message(chat_id=message.chat.id, text=f"Переслал сообщение.")
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


@reg_state(STATE.STUDENT_IS_SLEEPING)
async def prc_student_is_sleeping_state(message: types.message, student: User):
    logger.debug('prc_student_is_sleeping_state')
    if student.level == LEVEL.NOVICE:
        channel = '@vmsh_179_5_7_2022'
    elif student.level == LEVEL.PRO:
        channel = '@vmsh_179_5_7_2022'
    elif student.level == LEVEL.EXPERT:
        channel = '@vmsh_179_5_7_2022'
    elif student.level == LEVEL.GR8:
        channel = '@vmsh_179_8_2022'
    await bot.send_message(chat_id=message.chat.id if message else student.chat_id,
                           text="🤖 Приём задач ботом окончен до начала следующего занятия.\n"
                                f"Заходите в канал {channel} кружка за новостями и решениями.")


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
        student.set_level(LEVEL.NOVICE)
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу начинающих. "
                 "Успехов в занятиях! "
                 "Вопросы можно задавать в группе @vmsh_179_5_7_2022_chat.",
        )
        if State.get_by_user_id(student.id).get('state', None) != STATE.STUDENT_IS_SLEEPING:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


@dispatcher.message_handler(commands=['level_pro'])
async def level_pro(message: types.Message):
    logger.debug('level_pro')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу продолжающих. "
                 "Следите за сложностью, если не получается больше половины задач, то лучше перейти в группу «начинающих». "
                 "Это будет комфортнее и полезнее!",
        )
        student.set_level(LEVEL.PRO)
        if State.get_by_user_id(student.id).get('state', None) != STATE.STUDENT_IS_SLEEPING:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


@dispatcher.message_handler(commands=['level_expert'])
async def level_expert(message: types.Message):
    logger.debug('level_expert')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу экспертов. "
                 "Здесь будут сложные задачи, не переборщите со сложностью :) "
                 "Успехов!",
        )
        student.set_level(LEVEL.EXPERT)
        if State.get_by_user_id(student.id).get('state', None) != STATE.STUDENT_IS_SLEEPING:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


@dispatcher.message_handler(commands=['level_gr8'])
async def level_expert(message: types.Message):
    logger.debug('level_gr8')
    student = User.get_by_chat_id(message.chat.id)
    if student:
        message = await bot.send_message(
            chat_id=message.chat.id,
            text="Вы переведены в группу восьмого класса. Обратите внимание, что эта группа для «опытных» учеников 8 класса. "
                 "Если будет сложновато, рекомендуем группы «Продолжающие» или «Эксперты». "
                 "Вот канал вашего класса: @vmsh_179_8_2022. "
                 "А вот группа для обсуждений: @vmsh_179_8_2022_chat",
        )
        student.set_level(LEVEL.GR8)
        if State.get_by_user_id(student.id).get('state', None) != STATE.STUDENT_IS_SLEEPING:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))


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
        sos_message = await bot.send_message(chat_id=message.chat.id,
                                             text="🤖 Какой у вас вопрос?",
                                             reply_markup=student_keyboards.build_student_sos_actions())
        bot.delete_messages_after(sos_message, 30)


@reg_callback(CALLBACK.PROBLEM_SOS)
async def prc_problem_sos_callback(query: types.CallbackQuery, student: User):
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    problem_sos_message = await bot.send_message(chat_id=query.message.chat.id,
                                                 text="🤖 По какой задаче у вас вопрос❓",
                                                 reply_markup=student_keyboards.build_problems(
                                                     Problem.last_lesson_num(student.level), student,
                                                     is_sos_question=True))
    bot.delete_messages_after(problem_sos_message, 30)
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.OTHER_SOS)
async def prc_problems_other_sos_callback(query: types.CallbackQuery, student: User):
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    State.set_by_user_id(student.id, STATE.WAIT_SOS_REQUEST)
    await bot.send_message(chat_id=query.message.chat.id,
                           text="Напишите ваш вопрос",
                           reply_markup=student_keyboards.build_cancel_task_submission())
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.SOS_PROBLEM_SELECTED)
async def prc_problem_sos_problem_selected_callback(query: types.CallbackQuery, student: User):
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    State.set_by_user_id(student.id, STATE.WAIT_SOS_REQUEST, problem_id=problem_id)
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f"Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 с вашим вопросом.",
                           reply_markup=student_keyboards.build_cancel_task_submission())
    State.set_by_user_id(student.id, STATE.SENDING_SOLUTION,
                         -problem_id)  # -problem_id - ВОПРОС по задаче, а не РЕШЕНИЕ
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.PROBLEM_SELECTED)
async def prc_problems_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_problems_selected_callback')
    state = State.get_by_user_id(student.id)
    if state.get('state', None) == STATE.STUDENT_IS_SLEEPING:
        await bot.answer_callback_query_ig(query.id)
        return
    problem_id = int(query.data[2:])
    problem = Problem.get_by_id(problem_id)
    # Удаляем сообщение с клавиатурой-списком задач
    await bot.delete_message_ig(chat_id=query.message.chat.id, message_id=query.message.message_id)
    db.del_last_keyboard(student.id)
    if not problem:
        await bot.answer_callback_query_ig(query.id)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return
    # В зависимости от типа задачи разное поведение
    elif problem.prob_type == PROB_TYPE.TEST:
        # Если это выбор из нескольких вариантов, то нужно сделать клавиатуру
        if problem.ans_type == ANS_TYPE.SELECT_ONE:
            await bot.send_message(chat_id=query.message.chat.id,
                                   text=f"Выбрана задача {problem}.\nВыберите ответ — один из следующих вариантов:",
                                   reply_markup=student_keyboards.build_test_answers(problem))
        else:
            answer_recommendation = problem.validation_error or f'Теперь введите ответ{problem.ans_type.descr}'
            await bot.send_message(chat_id=query.message.chat.id,
                                   text=f"Выбрана задача {problem}.\n{answer_recommendation}",
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
        instruction_url = r'https://t.me/vmsh_179_5_7_2022/55'
        hint = ''
        if problem.level != LEVEL.EXPERT:
            conf_id = '87196763644'
            passcode = '179179'
        else:
            conf_id = '87196763644'
            passcode = '179179'
            # conf_id = '83052557082'
            # passcode = 'exp179'
            # hint = 'КОНФЕРЕНЦИЯ КАКАЯ БЫЛА РАНЬШЕ!\n'
        text = (
            f"{hint}"
            f"Выбрана устная задача. "
            # f"Её нужно сдавать в zoom-конференции. "
            # f"Желательно перед сдачей записать ответ и основные шаги решения на бумаге. "
            # f"Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. "
            # f"\nКогда у вас всё готово, "
            f"\n<b>Заходите в zoom-конференцию («Войти» в zoom)"
            f"\nИдентификатор конференции: <pre>{conf_id}</pre>"
            f"\nкод доступа: <pre>{passcode}</pre></b>"
            f"\n\nПожалуйста, при входе поставьте подпись:"
            f"\n<b><pre>{student.level} {student.surname} {student.name}</pre></b>"
            f"\n(<a href=\"{instruction_url}\">инструкция</a>)"
            f"\n\nКак только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. "
            f"После окончания сдачи нужно выйти из конференции. "
            f"Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. "
            f"Мы постараемся выделить время каждому, но ожидание может быть достаточно долгим."
        )
        await bot.send_message(chat_id=query.message.chat.id,
                               text=text,
                               disable_web_page_preview=True,
                               parse_mode='HTML')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        await bot.answer_callback_query_ig(query.id)
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=5))

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
        #     asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=4))


#         # await bot.send_message(chat_id=query.message.chat.id,
#         #                        text=f"Выбрана устная задача. "
#         #                             f"Её нужно сдавать в zoom-конференции. "
#         #                        # f"Желательно перед сдачей записать ответ и основные шаги решения на бумаге. "
#         #                        # f"Делайте рисунок очень крупным, чтобы можно было показать его преподавателю через видеокамеру. "
#         #                        # f"\nКогда у вас всё готово, "
#         #                             f"<b>Заходите в zoom-конференцию, идентификатор конференции:"
#         #                             f"\n83488340620, код доступа: 179179</b>. "
#         #                             f"\nПожалуйста, при входе поставьте актуальную подпись: ваши фамилию и имя. "
#         #                             f"Как только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. "
#         #                             f"После окончания сдачи нужно выйти из конференции. "
#         #                             f"Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. "
#         #                             f"Мы постараемся выделить время каждому, но ожидание может быть достаточно долгим.",
#         #                        disable_web_page_preview=True,
#         #                        parse_mode='HTML')
#         # State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
#         # await bot.answer_callback_query_ig(query.id)
#         # asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=5))
#
#         state = State.get_by_user_id(student.id)
#         if state['oral_problem_id'] is not None:
#             await bot.send_message(chat_id=query.message.chat.id,
#                                    text="Вы уже стоите в очереди на устную сдачу\. " \
#                                         "Дождитесь, когда освободится один из преподавателей\. " \
#                                         "Тогда можно будет сдать сразу несколько задач\.",
#                                    parse_mode="MarkdownV2")
#             await bot.answer_callback_query_ig(query.id)
#         else:
#             try:
#                 await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
#             except:
#                 pass
#             Waitlist.enter(student.id, problem.id)
#             await bot.send_message(chat_id=query.message.chat.id,
#                                    text="Вы встали в очередь на устную сдачу\.\nЧтобы выйти из очереди, нажмите `/exit_waitlist`",
#                                    parse_mode="MarkdownV2",
#                                    reply_markup=student_keyboards.build_exit_waitlist())
#             await bot.answer_callback_query_ig(query.id)
#             asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=4))


@reg_callback(CALLBACK.LIST_SELECTED)
async def prc_list_selected_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_list_selected_callback')
    list_num = int(query.data[2:])
    student = User.get_by_chat_id(query.message.chat.id)
    await post_problem_keyboard(student.chat_id, student)
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
    problem = selected_answer = problem_id = None
    splitted = query.data.split('_', maxsplit=2)
    if len(splitted) == 3:
        _, problem_id, selected_answer = splitted
        problem = Problem.get_by_id(problem_id)

    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
    await bot.answer_callback_query_ig(query.id)

    if problem is None:
        logger.error('Сломался приём задач :(')
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        # Удаляем варианты после изменения state'а. Иначе можно «зависнуть»
        asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))
        return

    await bot.send_message(chat_id=query.message.chat.id, text=f"Выбран вариант {selected_answer}.")

    await check_answer_and_react(query.message.chat.id, problem, student, selected_answer)


@reg_callback(CALLBACK.CANCEL_TASK_SUBMISSION)
async def prc_cancel_task_submission_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_cancel_task_submission_callback')
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    try:
        await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
    except:
        pass
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student, sleep=0))


@reg_callback(CALLBACK.GET_OUT_OF_WAITLIST)
async def prc_get_out_of_waitlist_callback(query: types.CallbackQuery, student: User):
    logger.debug('prc_get_out_of_waitlist_callback')
    state = State.get_by_user_id(student.id)
    teacher = User.get_by_id(state['last_teacher_id'])
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    Waitlist.leave(student.id)
    db.delete_url_by_user_id(student.id)
    try:
        await bot.unpin_chat_message(chat_id=query.message.chat.id)
    except BadRequest:
        pass
    State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    if teacher:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ученик {student.surname} {student.name} {student.token} завершил устную сдачу.\n")
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(sleep_and_send_problems_keyboard(query.message.chat.id, student))


@dispatcher.message_handler(commands=['exit_waitlist'])
async def exit_waitlist(message: types.Message):
    logger.debug('exit_waitlist')
    user = User.get_by_chat_id(message.chat.id)
    Waitlist.leave(user.id)
    db.delete_url_by_user_id(user.id)
    try:
        await bot.unpin_chat_message(chat_id=message.chat.id)
    except BadRequest:
        pass
    await bot.send_message(
        chat_id=message.chat.id,
        text="Вы успешно покинули очередь на устную сдачу.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user))


@dispatcher.message_handler(commands=['set_zoom'])
async def set_zoom(message: types.Message):
    logger.debug('set_zoom')
    user = User.get_by_chat_id(message.chat.id)
    zoom_conf = re.search(r'https://[\w?=._/-]*zoom[\w?=._/-]*', message.text or '')
    if not zoom_conf:
        await bot.send_message(chat_id=message.chat.id,
                               text="Не смог найти в сообщении адрес конференции.")
        await bot.send_message(chat_id=message.chat.id,
                               text="Открываете приложение zoom и стартуете новую конференцию.<br>В левом верхнем углу зелёный щит. Кликаете на него и копируете ссылку на вашу конференцию.<br>Запускаете вмш-телеграм-бота и пишете команду с вашей ссылкой вида <br><code>/set_zoom https://us02web.zoom.us/j/123?pwd=ABC</code>",
                               parse_mode="HTML")
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user, sleep=5))
    else:
        zoom_url = zoom_conf.group()
        db.add_zoom_conf(user.id, zoom_url)
        msg = await bot.send_message(chat_id=message.chat.id,
                                     text=f"Ожидайте вашей очереди и не выходите из конференции {zoom_url}.\nВыполните команду /exit_waitlist для отмены.", )
        await bot.pin_chat_message(chat_id=message.chat.id, message_id=msg.message_id)
        asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user, sleep=5))

@dispatcher.message_handler(commands=['zq'])
async def stand_in_zoom_queue(message: types.Message):
    logger.debug('stand_in_zoom_queue')
    user = User.get_by_chat_id(message.chat.id)
    db.add_to_queue_by_id(user.id)
    await bot.send_message(chat_id=message.chat.id, text="Вы встали в zoom-очередь")
    asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, user, sleep=5))
    #    msg = await bot.send_message(chat_id=message.chat.id,
    #                                text=f"Ожидайте вашей очереди и не выходите из конференции {zoom_url}.\nВыполните команду /exit_waitlist для отмены.", )
    #    await bot.pin_chat_message(chat_id=message.chat.id, message_id=msg.message_id)

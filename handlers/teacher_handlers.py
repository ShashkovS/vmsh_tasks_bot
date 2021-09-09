import re
import aiogram
from aiogram.dispatcher.webhook import types
from aiogram.dispatcher import filters
from urllib.parse import urlencode
from Levenshtein import jaro_winkler

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, Problem, State, Waitlist, WrittenQueue, db
from helpers.bot import bot, reg_callback, dispatcher, reg_state
from handlers import teacher_keyboards
from handlers.main_handlers import process_regular_message


@reg_state(STATE.TEACHER_SELECT_ACTION)
async def prc_teacher_select_action(message: types.Message, teacher: User):
    logger.debug('prc_teacher_select_action')
    await bot.send_message(chat_id=message.chat.id, text="Выберите действие",
                           reply_markup=teacher_keyboards.build_teacher_actions())


@reg_state(STATE.TEACHER_IS_CHECKING_TASK)
async def prc_teacher_is_checking_task_state(message: types.Message, teacher: User):
    logger.debug('prc_teacher_is_checking_task_state')
    problem_id = State.get_by_user_id(teacher.id)['problem_id']
    student_id = State.get_by_user_id(teacher.id)['last_student_id']
    WrittenQueue.add_to_discussions(student_id, problem_id, teacher.id, message.text, None, message.chat.id,
                                    message.message_id)
    await bot.send_message(chat_id=message.chat.id, text="Ок, записал")


@reg_state(STATE.TEACHER_ACCEPTED_QUEUE)
async def prc_teacher_accepted_queue(message: types.message, teacher: User):
    logger.debug('prc_teacher_accepted_queue')
    state = State.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = User.get_by_id(student_id)
    await bot.send_message(chat_id=message.chat.id,
                           text="Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)",
                           reply_markup=teacher_keyboards.build_verdict_for_oral_problems(plus_ids=set(), minus_ids=set(), student=student,
                                                                                          online=teacher.online))


@reg_state(STATE.TEACHER_WRITES_STUDENT_NAME)
async def prc_teacher_writes_student_name_state(message: types.message, teacher: User):
    logger.debug('prc_teacher_writes_student_name_state')
    name_to_find = message.text or ''
    await bot.send_message(chat_id=message.chat.id,
                           text="Выберите школьника для внесения задач",
                           reply_markup=teacher_keyboards.build_select_student(name_to_find))


@dispatcher.message_handler(filters.RegexpCommandsFilter(regexp_commands=['recheck.*']))
async def recheck(message: types.Message):
    logger.debug('recheck')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    prob = prob_id = None
    if (match := re.fullmatch(r'/recheck(?:_xd5fqk)?[\s_]+([a-zA-Z0-9]+)[\s_]+(\d+)([а-я])\.(\d+)([а-я]?)\s*', message.text or '')):
        token, lst, level, prob, item = match.groups()
        problem = Problem.get_by_key(level, int(lst), int(prob), item)
    elif (match := re.fullmatch(r'/recheck(?:_xd5fqk)?_([^_]*)_([^_]*)', message.text or '')):
        token, prob_id = match.groups()
        problem = Problem.get_by_id(prob_id)
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🤖 Пришлите запрос на перепроверку в формате\n«/recheck token problem», например «/recheck aa9bb4 3н.11а»",
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id, text=f"🤖 Студент с токеном {token} не найден")
    if not problem and prob is not None:
        await bot.send_message(chat_id=message.chat.id, text=f"🤖 Задача {lst}{level}.{prob}{item} не найдена")
    if not problem and prob_id is not None:
        await bot.send_message(chat_id=message.chat.id, text=f"🤖 Задача с id {prob_id} не найдена")
    if student and problem:
        message = await bot.send_message(chat_id=message.chat.id, text=f"Переотправили на проверку")
        await forward_discussion_and_start_checking(message.chat.id, message.message_id, student, problem, teacher)


@dispatcher.message_handler(commands=['set_level'])
async def set_student_level(message: types.Message):
    logger.debug('set_student_level')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.split()
    try:
        cmd, token, new_level = text
    except:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"/set_level token н/п/э",
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Студент с токеном {token} не найден",
        )
    if new_level == LEVEL.NOVICE:
        student.set_level(LEVEL.NOVICE)
        stud_msg = "Вы переведены в группу начинающих"
    elif new_level == LEVEL.PRO:
        student.set_level(LEVEL.PRO)
        stud_msg = "Вы переведены в группу продолжающих"
    elif new_level == LEVEL.EXPERT:
        student.set_level(LEVEL.EXPERT)
        stud_msg = "Вы переведены в группу экспертов"
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


@reg_callback(CALLBACK.GET_WRITTEN_TASK)
async def prc_get_written_task_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_written_task_callback')
    # Так, препод указал, что хочет проверять письменные задачи
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    top = WrittenQueue.take_top(teacher.id)
    if not top:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Ничего себе! Все письменные задачи проверены!")
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        await bot.answer_callback_query_ig(query.id)
        await process_regular_message(query.message)
    else:
        # Даём преподу 10 топовых задач на выбор
        await bot.send_message(chat_id=teacher.chat_id, text="Выберите задачу для проверки",
                               reply_markup=teacher_keyboards.build_teacher_select_written_problem(top))
        # teacher_keyboards.build_teacher_actions


@reg_callback(CALLBACK.TEACHER_CANCEL)
async def prc_teacher_cancel_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_teacher_cancel_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    await process_regular_message(query.message)


async def forward_discussion_and_start_checking(chat_id, message_id, student, problem, teacher):
    logger.debug('forward_discussion_and_start_checking')
    await bot.edit_message_text_ig(chat_id=chat_id, message_id=message_id,
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
    State.set_by_user_id(teacher.id, STATE.TEACHER_IS_CHECKING_TASK, problem.id, last_teacher_id=teacher.id,
                         last_student_id=student.id)
    await bot.send_message(chat_id=chat_id,
                           text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n'
                                'Напишите комментарий или скриншот 📸 вашей проверки (или просто поставьте плюс)',
                           reply_markup=teacher_keyboards.build_written_task_checking_verdict(student, problem))


@reg_callback(CALLBACK.WRITTEN_TASK_SELECTED)
async def prc_written_task_selected_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_selected_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    chat_id = query.message.chat.id
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    await bot.answer_callback_query_ig(query.id)
    # Блокируем задачу
    is_unlocked = WrittenQueue.mark_being_checked(student.id, problem.id, teacher.id)
    if not is_unlocked:
        await bot.send_message(chat_id=chat_id, text='Эту задачу уже кто-то взялся проверять.')
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        await process_regular_message(query.message)
        return
    await forward_discussion_and_start_checking(chat_id, query.message.message_id, student, problem, teacher)


@reg_callback(CALLBACK.WRITTEN_TASK_OK)
async def prc_written_task_ok_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_ok_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем задачу как решённую и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT.SOLVED, None, RES_TYPE.WRITTEN)
    WrittenQueue.delete_from_queue(student.id, problem.id)
    await bot.answer_callback_query_ig(query.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'👍 Отлично, поставили плюсик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}! '
                                f'Для исправления: '
                                f'/recheck_{student.token}_{problem.id}',
                           parse_mode='HTML')
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
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
                    await bot.copy_message(student_chat_id, row['chat_id'], row['tg_msg_id'],
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


@reg_callback(CALLBACK.WRITTEN_TASK_BAD)
async def prc_written_task_bad_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_bad_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем решение как неверное и удаляем из очереди
    db.add_result(student.id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT.WRONG_ANSWER, None, RES_TYPE.WRITTEN)
    db.delete_plus(student_id, problem.id, VERDICT.WRONG_ANSWER)
    WrittenQueue.delete_from_queue(student.id, problem.id)
    await bot.send_message(chat_id=query.message.chat.id,
                           text=f'❌ Эх, поставили минусик за задачу {problem.lesson}{problem.level}.{problem.prob}{problem.item} '
                                f'школьнику {student.token} {student.surname} {student.name}! Для исправления: '
                                f'/recheck_{student.token}_{problem.id}',
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
                    await bot.copy_message(student_chat_id, row['chat_id'], row['tg_msg_id'],
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
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    await process_regular_message(query.message)


@reg_callback(CALLBACK.GET_QUEUE_TOP)
async def prc_get_queue_top_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_queue_top_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    top = Waitlist.top(1)
    if not top:
        # Если в очереди пусто, то шлём сообщение и выходим.
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"Сейчас очередь пуста. Повторите через пару минут.")
        await bot.answer_callback_query_ig(query.id)
        await prc_teacher_select_action(query.message, teacher)
        return

    student = User.get_by_id(top[0]['student_id'])
    problem = Problem.get_by_id(top[0]['problem_id'])
    State.set_by_user_id(teacher.id, STATE.TEACHER_ACCEPTED_QUEUE, oral_problem_id=problem.id,
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
        State.set_by_user_id(student.id, STATE.STUDENT_IS_IN_CONFERENCE, oral_problem_id=problem.id,
                             last_teacher_id=teacher.id)
        await bot.send_message(chat_id=student.chat_id, text="Нажмите по окончанию.",
                               reply_markup=teacher_keyboards.build_student_in_conference(),
                               parse_mode='HTML')
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
        # Снимаем со школьника статус сдачи
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
    else:
        await bot.answer_callback_query_ig(query.id, show_alert=True)
        await bot.send_message(chat_id=teacher.chat_id,
                               text=f"<b>Ваш ученик: {student}.\n"
                                    f"{problem}.\n"
                                    f"<a href=\"{teacher_link}\">Войдите в конференцию</a></b>",
                               parse_mode='HTML')
    await bot.answer_callback_query_ig(query.id)
    await process_regular_message(message=query.message)


@reg_callback(CALLBACK.INS_ORAL_PLUSSES)
async def prc_ins_oral_plusses(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_ins_oral_plusses')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    await bot.send_message(chat_id=teacher.chat_id,
                           text=f"Введите фамилию школьника (можно начало фамилии)")
    await bot.answer_callback_query_ig(query.id)
    State.set_by_user_id(teacher.id, STATE.TEACHER_WRITES_STUDENT_NAME)


@reg_callback(CALLBACK.SET_VERDICT)
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
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    await bot.answer_callback_query_ig(query.id)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    db.add_result(student_id, problem_id, problem.level, problem.lesson, teacher.id, verdict, '', RES_TYPE.ZOOM)
    await process_regular_message(query.message)


@reg_callback(CALLBACK.STUDENT_SELECTED)
async def prc_student_selected_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_student_selected_callback')
    _, student_id = query.data.split('_')
    student_id = int(student_id)
    student = User.get_by_id(student_id)
    await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None,
                                   text=f"Вносим плюсики школьнику:\n"
                                        f"{student.surname} {student.name} {student.token} уровень {student.level}")
    await bot.send_message(chat_id=query.message.chat.id,
                           text="Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)",
                           reply_markup=teacher_keyboards.build_verdict_for_oral_problems(plus_ids=set(), minus_ids=set(), student=student,
                                                                                          online=teacher.online))
    State.set_by_user_id(teacher.id, STATE.TEACHER_WRITES_STUDENT_NAME, last_student_id=student.id)
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.ADD_OR_REMOVE_ORAL_PLUS)
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
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=teacher_keyboards.build_verdict_for_oral_problems(plus_ids=plus_ids, minus_ids=minus_ids,
                                                                                                          student=student, online=teacher.online))
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.FINISH_ORAL_ROUND)
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
        await bot.answer_callback_query_ig(query.id)
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        await process_regular_message(teacher_message)
        return

    pluses = [Problem.get_by_id(prb_id) for prb_id in plus_ids]
    minuses = [Problem.get_by_id(prb_id) for prb_id in minus_ids]
    human_readable_pluses = [f'{plus.lesson}{plus.level}.{plus.prob}{plus.item}' for plus in pluses]
    human_readable_minuses = [f'{plus.lesson}{plus.level}.{plus.prob}{plus.item}' for plus in minuses]
    # Проставляем плюсики
    if teacher.online == ONLINE_MODE.SCHOOL:
        res_type = RES_TYPE.SCHOOL
    else:
        res_type = RES_TYPE.ZOOM
    for problem in pluses:
        db.add_result(student_id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT.SOLVED, None, res_type)
    for problem in minuses:
        db.delete_plus(student_id, problem.id, VERDICT.WRONG_ANSWER)
        db.add_result(student_id, problem.id, problem.level, problem.lesson, teacher.id, VERDICT.WRONG_ANSWER, None, res_type)
    # Формируем сообщение с итоговым результатом проверки
    text = f"Школьник: {student.token} {student.surname} {student.name}\n"
    if human_readable_pluses:
        text += f"\nПоставлены плюсы «+++» за задачи: {', '.join(human_readable_pluses)}"
    if human_readable_minuses:
        text += f"\nПоставлены минусы «−−−» за задачи: {', '.join(human_readable_minuses)}"
    await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                   text=text,
                                   reply_markup=None)
    # Посылаем сообщения школьнику о проверке
    try:
        student_state = State.get_by_user_id(student.id)
        student_message = await bot.send_message(chat_id=student.chat_id,
                                                 text=f"В результате устного приёма вам поставили плюсики за задачи: {', '.join(human_readable_pluses)}",
                                                 disable_notification=True)
        if student_state['state'] == STATE.STUDENT_IS_IN_CONFERENCE:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
            await process_regular_message(student_message)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
    await bot.answer_callback_query_ig(query.id)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await process_regular_message(query.message)


@dispatcher.message_handler(commands=['find_student'])
async def find_student(message: types.Message):
    logger.debug('find_student')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    search = None
    if (match := re.match(r'/find_student\s+(\S+)', message.text or '')):
        search = match.group(1)
    if not search:
        await bot.send_message(chat_id=message.chat.id, text=f"🤖 Введите часть фамилии", )
        return
    students = sorted(
        User.all_students(),
        key=lambda user: -jaro_winkler(search.lower(), f'{user.surname} {user.name} {user.token}'.lower(), 1 / 10)
    )
    if students:
        lines = [f'f"{student.surname} {student.name} {student.level} {student.token} {ONLINE_MODE(student.online).__str__()[12:]}"'
                 for student in students[:10]]
        await bot.send_message(chat_id=message.chat.id, parse_mode="HTML", text='<pre>' + '\n'.join(lines) + '</pre>')
    else:
        await bot.send_message(chat_id=message.chat.id, text='Не нашлось ни одного студента')


@dispatcher.message_handler(commands=['set_online'])
async def set_online(message: types.Message):
    logger.debug('set_online')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.split()
    try:
        cmd, token, new_online = text
    except:
        await bot.send_message(chat_id=message.chat.id, text=f"/set_online token online/school", )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id, text=f"Студент с токеном {token} не найден", )
    if new_online == ONLINE_MODE.ONLINE:
        student.set_online_mode(ONLINE_MODE.ONLINE)
    elif new_online == ONLINE_MODE.SCHOOL:
        student.set_online_mode(ONLINE_MODE.SCHOOL)
    else:
        return
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"Студент с токеном {token} переведён",
    )

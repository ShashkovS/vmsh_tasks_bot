import datetime
import re

import aiogram
import asyncio
from aiogram import F, types
from aiogram.filters import Command
from aiogram.utils.exceptions import BadRequest
from urllib.parse import urlencode
from Levenshtein import jaro_winkler
from random import randrange

from helpers.consts import *
from helpers.config import logger
from helpers.msg_texts import msgs
import db_methods as db
from helpers.features import VERDICT_MODE, FEATURES, RESULT_MODE
from models import User, Problem, State, Waitlist, WrittenQueue, Result
from helpers.bot import bot, reg_callback, router, reg_state
from handlers import teacher_keyboards, student_keyboards
from handlers.student_handlers import sleep_and_send_problems_keyboard, refresh_last_student_keyboard, WHITEBOARD_LINK
from handlers.main_handlers import process_regular_message  # TODO Удалить использование этой функции

CHECK_MILESTONES = {
    1: msgs.t_check_milestone1,
    10: msgs.t_check_milestone10,
    50: msgs.t_check_milestone50,
    100: msgs.t_check_milestone100,
    200: msgs.t_check_milestone200,
    300: msgs.t_check_milestone300,
    400: msgs.t_check_milestone400,
    500: msgs.t_check_milestone500,
    600: msgs.t_check_milestone600,
    700: msgs.t_check_milestone700,
    800: msgs.t_check_milestone800,
    900: msgs.t_check_milestone900,
    1000: msgs.t_check_milestone1000,
    1100: msgs.t_check_milestone1100,
    1200: msgs.t_check_milestone1200,
    1300: msgs.t_check_milestone1300,
    1400: msgs.t_check_milestone1400,
    1500: msgs.t_check_milestone1500,
    1600: msgs.t_check_milestone1600,
    1700: msgs.t_check_milestone1700,
    1800: msgs.t_check_milestone1800,
    1900: msgs.t_check_milestone1900,
    2000: msgs.t_check_milestone2000,
    2100: msgs.t_check_milestone2100,
    2200: msgs.t_check_milestone2200,
    2300: msgs.t_check_milestone2300,
    2400: msgs.t_check_milestone2400,
    2500: msgs.t_check_milestone2500,
}


def get_problem_lock(teacher_id: int):
    key = f'{teacher_id}_pl'
    value = db.sql.kv.get(key, None)
    return int(value) if value else None


def del_problem_lock(teacher_id: int):
    key = f'{teacher_id}_pl'
    db.sql.kv.pop(key, None)


def set_problem_lock(teacher_id: int, problem_id: int):
    key = f'{teacher_id}_pl'
    value = f'{problem_id}'
    db.sql.kv[key] = value


async def take_random_written_problem_and_start_check(teacher: User, problem: Problem):
    top = WrittenQueue.take_top_synonyms(teacher.id, problem.synonyms)
    # if top:
    # # Даём преподу 10 топовых задач на выбор
    # await bot.answer_callback_query_ig(query.id)
    # await bot.send_message(chat_id=teacher.chat_id, text="Выберите задачу для проверки",
    #                        reply_markup=teacher_keyboards.build_teacher_select_written_problem(top))
    while top:
        # Даём преподу случайную задачу
        choice = randrange(0, len(top))
        taken = top.pop(choice)
        student = User.get_by_id(taken['student_id'])
        problem = Problem.get_by_id(taken['problem_id'])
        # Блокируем задачу
        is_unlocked = WrittenQueue.mark_being_checked(student.id, problem.id, teacher.id)
        if not is_unlocked:
            continue
        await forward_discussion_and_start_checking(teacher.chat_id, None, student, problem, teacher)
        break
    else:
        del_problem_lock(teacher.id)
        await bot.send_message(chat_id=teacher.chat_id,
                               text=msgs.t_all_written_checked)
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        asyncio.create_task(prc_teacher_select_action(None, teacher))


@reg_state(STATE.TEACHER_SELECT_ACTION)
async def prc_teacher_select_action(message: types.Message, teacher: User, sleep_before=0):
    use_chat_id = (message and message.chat and message.chat.id) or (teacher and teacher.chat_id) or None
    if sleep_before > 0:
        await asyncio.sleep(sleep_before)
    logger.debug('prc_teacher_select_action')
    locked_problem_id = get_problem_lock(teacher.id)
    if locked_problem_id:
        problem = Problem.get_by_id(locked_problem_id)
    if not locked_problem_id or not problem:
        sos_count = db.written_task_queue.get_sos_tasks_count()
        prb_count = db.written_task_queue.get_written_tasks_count()
        text = msgs.t_select_action.format(prb_count=prb_count, sos_count=sos_count)
        keyb_msg = await bot.send_message(chat_id=use_chat_id, text=text,
                                          reply_markup=teacher_keyboards.build_teacher_actions(sos_count, prb_count))
        db.last_keyboard.update(teacher.id, keyb_msg.chat.id, keyb_msg.message_id)
    else:
        await take_random_written_problem_and_start_check(teacher, problem)


@reg_state(STATE.TEACHER_IS_CHECKING_TASK)
async def prc_teacher_is_checking_task_state(message: types.Message, teacher: User):
    logger.debug('prc_teacher_is_checking_task_state')
    teacher_state = State.get_by_user_id(teacher.id)
    problem_id = teacher_state['problem_id']
    student_id = teacher_state['last_student_id']
    wtd_id = WrittenQueue.add_to_discussions(student_id, problem_id, teacher.id, message.text, None, message.chat.id,
                                             message.message_id)
    teacher_state['info'].append(wtd_id)  # Добавляем id в список добавленных
    State.set_by_user_id(**teacher_state)
    prev_keyboard = db.last_keyboard.get(teacher.id)
    reply_markup = teacher_keyboards.build_written_task_checking_verdict(User.get_by_id(student_id),
                                                                         Problem.get_by_id(problem_id),
                                                                         teacher_state['info']) if (
            problem_id > 0) else teacher_keyboards.build_answer_verdict(User.get_by_id(student_id),
                                                                        Problem.get_by_id(-problem_id),
                                                                        teacher_state['info'])
    # await bot.send_message(chat_id=message.chat.id, text="Ок, записал")
    keyb_msg = await bot.send_message(chat_id=message.chat.id,
                                      text=msgs.t_ok_saved,
                                      reply_markup=reply_markup)
    if prev_keyboard:
        await bot.edit_message_reply_markup_ig(chat_id=prev_keyboard['chat_id'], message_id=prev_keyboard['tg_msg_id'],
                                               reply_markup=None)
    db.last_keyboard.update(teacher.id, keyb_msg.chat.id, keyb_msg.message_id)


@reg_state(STATE.TEACHER_ACCEPTED_QUEUE)
async def prc_teacher_accepted_queue(message: types.message, teacher: User, online=None, lesson_num=None, student: User = None):
    logger.debug('prc_teacher_accepted_queue')
    # при вызове из команды могут быть «силой» установлены параметры online, lesson_num, student_id
    if student is None:
        state = State.get_by_user_id(teacher.id)
        student_id = state['last_student_id']
        student = User.get_by_id(student_id)
    if not student:
        return
    if online is None:
        online = teacher.online

    reply_markup = teacher_keyboards.build_verdict_for_oral_problems(
        plus_ids=set(),
        minus_ids=set(),
        student=student,
        online=online,
        lesson_num=lesson_num,
    )
    mode_label = msgs.t_online_mode_school if teacher.online == ONLINE_MODE.SCHOOL else msgs.t_online_mode_online
    text = msgs.t_mark_oral_tasks_intro.format(mode_label=mode_label)
    await bot.send_message(chat_id=message.chat.id,
                           text=text,
                           reply_markup=reply_markup)


@router.message(F.text.regexp(r'^/?edtplus.*'))
async def edtplus(message: types.Message):
    logger.debug('edtplus')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    lesson = token = None
    if (match := re.fullmatch(r'/edtplus_([^_]*)_([^_]*)', message.text or '')):
        lesson = match.group(1)
        token = match.group(2)
    if lesson:
        try:
            lesson_num = int(lesson)
        except:
            lesson = None
    if not lesson or not lesson.isdecimal():
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.t_edtplus_format_hint,
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id,
                               text=msgs.t_student_with_token_not_found.format_map({'token': token}))
    state = State.get_by_user_id(teacher.id)
    State.set_by_user_id(teacher.id, state['state'], last_student_id=student.id)
    await prc_teacher_accepted_queue(message, teacher, online=ONLINE_MODE.SCHOOL, lesson_num=lesson_num, student=student)


@reg_state(STATE.TEACHER_WRITES_STUDENT_NAME)
async def prc_teacher_writes_student_name_state(message: types.message, teacher: User):
    logger.debug('prc_teacher_writes_student_name_state')
    name_to_find = message.text or ''
    await bot.send_message(chat_id=message.chat.id,
                           text=msgs.t_choose_student_for_pluses,
                           reply_markup=teacher_keyboards.build_select_student(name_to_find))


@router.message(F.text.regexp(r'^/?recheck.*'))
async def recheck(message: types.Message):
    logger.debug('recheck')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    prob = prob_id = None
    if (match := re.fullmatch(r'/recheck(?:_xd5fqk)?[\s_]+([a-zA-Z0-9]+)[\s_]+(\d+)([а-яА-Я]\w*)\.(\d+)([а-я]?)\s*',
                              message.text or '')):
        token, lst, level, prob, item = match.groups()
        problem = Problem.get_by_key(level, int(lst), int(prob), item)
    elif (match := re.fullmatch(r'/recheck(?:_xd5fqk)?_([^_]*)_([^_]*)', message.text or '')):
        token, prob_id = match.groups()
        problem = Problem.get_by_id(prob_id)
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.t_recheck_format_hint,
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id,
                               text=msgs.t_student_with_token_not_found.format_map({'token': token}))
    if not problem and prob is not None:
        await bot.send_message(chat_id=message.chat.id,
                               text=msgs.t_problem_not_found_key.format_map({'lst': lst, 'level': level, 'prob': prob, 'item': item}))
    if not problem and prob_id is not None:
        await bot.send_message(chat_id=message.chat.id,
                               text=msgs.t_problem_not_found_id.format_map({'prob_id': prob_id}))
    if student and problem:
        message = await bot.send_message(chat_id=message.chat.id, text=msgs.t_resend_for_checking)
        await forward_discussion_and_start_checking(message.chat.id, message.message_id, student, problem, teacher)


@router.message(Command('set_level', 'sl'))
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
            text=msgs.t_set_level_usage,
        )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.t_student_with_token_not_found.format_map({'token': token}),
        )
        return
    try:
        new_level_en = LEVEL(new_level)
    except ValueError:
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.t_level_not_exists.format_map({'new_level': new_level}),
        )
        return
    student.set_level(new_level_en)
    if new_level == LEVEL.NOVICE:
        stud_msg = msgs.you_are_in_novice_now
    elif new_level == LEVEL.PRO:
        stud_msg = msgs.you_are_in_pro_now
    elif new_level == LEVEL.EXPERT:
        stud_msg = msgs.you_are_expert_now
    elif new_level == LEVEL.GR8:
        stud_msg = msgs.you_are_grade8_now
    else:
        stud_msg = None
    await bot.send_message(
        chat_id=message.chat.id,
        text=msgs.t_student_level_changed.format_map({'token': token, 'new_level_en': new_level_en}),
    )
    if student.chat_id and stud_msg:
        try:
            await bot.send_message(chat_id=student.chat_id, text=stud_msg)
        except:
            pass


@reg_callback(CALLBACK.GET_SOS_TASK)
async def prc_get_written_task_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_written_task_callback')
    # Так, препод указал, что хочет проверять письменные задачи
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    top = WrittenQueue.take_sos_top(teacher.id)
    await bot.answer_callback_query_ig(query.id)
    if not top:
        await bot.send_message(chat_id=teacher.chat_id,
                               text=msgs.t_no_sos_questions)
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        asyncio.create_task(prc_teacher_select_action(None, teacher))
    else:
        # Даём преподу 10 топовых задач на выбор
        await bot.send_message(chat_id=teacher.chat_id, text=msgs.t_choose_question,
                               reply_markup=teacher_keyboards.build_teacher_select_written_problem(top))
        # teacher_keyboards.build_teacher_actions


@reg_callback(CALLBACK.SELECT_WRITTEN_TASK_TO_CHECK)
async def prc_SELECT_WRITTEN_TASK_TO_CHECK_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_SELECT_WRITTEN_TASK_TO_CHECK_callback')
    # Так, препод указал, что хочет проверять письменные задачи
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    rows = db.written_task_queue.get_written_tasks_count_by_synonyms()
    problems_and_counts = []
    for row in rows:
        first_problem_id = row['synonyms'].split(';')[0]
        problems_and_counts.append((Problem.get_by_id(first_problem_id), row['cnt'], row['days_waits']))
    sos_count = db.written_task_queue.get_sos_tasks_count()
    prb_count = db.written_task_queue.get_written_tasks_count()
    text = msgs.t_select_problem_to_check_counts.format_map({'prb_count': prb_count, 'sos_count': sos_count})
    await bot.send_message(chat_id=teacher.chat_id, text=text,
                           reply_markup=teacher_keyboards.build_select_problem_to_check(problems_and_counts))
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.CHECK_ONLY_SELECTED_WRITEN_TASK)
async def prc_CHECK_ONLY_SELECTED_WRITEN_TASK_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_CHECK_ONLY_SELECTED_WRITEN_TASK_callback')
    # Так, препод указал, что хочет только вот эту конкретную письменную задачу
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    problem_id = int(query.data[2:])
    set_problem_lock(teacher.id, problem_id)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    # Всё, теперь задача залочена,prc_teacher_select_action будет сама выбирать задачу
    asyncio.create_task(prc_teacher_select_action(None, teacher))


@reg_callback(CALLBACK.TEACHER_CANCEL)
async def prc_teacher_cancel_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_teacher_cancel_callback')
    _, _, wtd_ids_to_remove = query.data.partition('_del_')
    if wtd_ids_to_remove:
        wtd_ids_to_remove = list(map(int, wtd_ids_to_remove.split(',')))  # TODO А-а-а! ТРЕШНЯК!!!
        db.written_task_discussion.delete(wtd_ids_to_remove)
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    del_problem_lock(teacher.id)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(prc_teacher_select_action(None, teacher))


async def forward_discussion_and_start_checking(chat_id, message_id, student: User, problem: Problem, teacher: User,
                                                is_sos=False):
    logger.debug('forward_discussion_and_start_checking')
    if is_sos:
        text = msgs.t_question_on_problem.format_map({'problem': problem, 'student': student})
    else:
        text = msgs.t_checking_problem.format_map({'problem': problem, 'student': student})
    # Если передан message_id, то обновляем сообщение (там была кнопка). Если нет, то отправляем новое.
    if message_id:
        await bot.edit_message_text_ig(chat_id=chat_id, message_id=message_id, text=text, reply_markup=None)
    else:
        await bot.send_message(chat_id=chat_id, text=text)
    discussion = WrittenQueue.get_discussion(student.id,
                                             problem.id if (not is_sos) else (-problem.id))  # обрабатываем SOS
    for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не привысить лимит
        forward_success = False
        if row['chat_id'] and row['tg_msg_id']:
            try:
                await bot.forward_message(chat_id, row['chat_id'], row['tg_msg_id'])
                forward_success = True
            except aiogram.utils.exceptions.TelegramAPIError as e:
                logger.error(msgs.t_message_deleted + '\n%s', e)
                await bot.send_message(chat_id=chat_id, text=msgs.t_message_deleted)
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
    State.set_by_user_id(teacher.id, STATE.TEACHER_IS_CHECKING_TASK, problem.id if (not is_sos) else (-problem.id),
                         last_teacher_id=teacher.id,
                         last_student_id=student.id,
                         info=[])  # info — список сообщений, которые нужно удалить #добавил учёт SOS
    if is_sos:
        text = msgs.t_write_answer
        reply_markup = teacher_keyboards.build_answer_verdict(student, problem)
    else:
        text = msgs.t_write_checking_comment
        reply_markup = teacher_keyboards.build_written_task_checking_verdict(student, problem)
    keyb_msg = await bot.send_message(chat_id=chat_id,
                                      text=text,
                                      reply_markup=reply_markup,
                                      )
    db.last_keyboard.update(teacher.id, keyb_msg.chat.id, keyb_msg.message_id)


@reg_callback(CALLBACK.WRITTEN_TASK_SELECTED)
async def prc_written_task_selected_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_selected_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    chat_id = query.message.chat.id
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(abs(int(problem_id)))  # убираем знак, если вопрос
    await bot.answer_callback_query_ig(query.id)
    # Блокируем задачу
    is_unlocked = WrittenQueue.mark_being_checked(student.id, problem_id, teacher.id)
    if not is_unlocked:
        await bot.send_message(chat_id=chat_id, text=msgs.t_task_already_being_checked)
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        asyncio.create_task(prc_teacher_select_action(None, teacher))
        return
    if (int(problem_id) > 0):
        await forward_discussion_and_start_checking(chat_id, query.message.message_id, student, problem, teacher)
    else:
        await forward_discussion_and_start_checking(chat_id, query.message.message_id, student, problem, teacher,
                                                    is_sos=True)


async def forward_discussion_to_student(student: User, problem: Problem, verdict: VERDICT, result_id: int = None):
    """ Отправить студенту вердикт проверки и переслать переписку.
    Если задача решена, то пересылаются только последние комментарии учителя.
    Если не решена, то пересылается вся переписка, чтобы было понятно, о чём речь в целом.
    """
    # Обновляем студенту клавиатуру со списком задач
    await refresh_last_student_keyboard(student)
    # Получаем id сообщений с перепиской
    discussion = WrittenQueue.get_discussion(student.id, problem.id)
    # Находим последнее сообщение школьника
    last_pup_post = max([rn for rn in range(len(discussion)) if discussion[rn]['teacher_id'] is None] + [-2])
    last_teacher_messages = discussion[last_pup_post + 1:]
    solved = verdict in VERDICTS_SOLVED
    if solved:
        messages_to_forward = last_teacher_messages
    else:
        # Берём последние 20 сообщений, чтобы не превысить лимит
        messages_to_forward = discussion[-20:]
    text_problem_part = f"{msgs.t_forward_discussion_to_student_word} {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title})"

    if VERDICT_MODE == FEATURES.VERDICT_PLUS_MINUS:
        if solved and not messages_to_forward:
            text_vedict_part = msgs.t_verdict_plus_no_comments
        elif solved and messages_to_forward:
            text_vedict_part = msgs.t_verdict_plus_with_comments
        elif not solved and not last_teacher_messages:
            text_vedict_part = msgs.t_verdict_minus_no_comments
        else:
            text_vedict_part = msgs.t_verdict_minus_with_comments
    else:
        verdict_tick = VERDICT_TO_TICK[verdict]
        if last_teacher_messages:
            text_vedict_part = msgs.t_verdict_tick_with_comments.format_map({'verdict_tick': verdict_tick})
        else:
            text_vedict_part = msgs.t_verdict_tick_no_comments.format_map({'verdict_tick': verdict_tick})
    await bot.send_message(chat_id=student.chat_id, text=f"{text_problem_part} {text_vedict_part}",
                           disable_notification=True)
    try:
        for row in messages_to_forward:
            # Только пересылаем сообщения, без вариантов
            if row['teacher_id']:
                await bot.copy_message(student.chat_id, row['chat_id'], row['tg_msg_id'], disable_notification=True)
            else:
                await bot.forward_message(student.chat_id, row['chat_id'], row['tg_msg_id'], disable_notification=True)
        if solved:
            student_reaction_keyboard = None
        else:
            student_reaction_keyboard = student_keyboards.build_student_reaction_on_task_bad_verdict(result_id)
        if messages_to_forward:
            await bot.send_message(chat_id=student.chat_id,
                                   text='⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n',
                                   reply_markup=student_reaction_keyboard,
                                   disable_notification=True)

    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')


@reg_callback(CALLBACK.WRITTEN_TASK_OK)
async def prc_written_task_ok_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_ok_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    _, student_id, problem_id, set_verdict = query.data.split('_')
    set_verdict = VERDICT(int(set_verdict))
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем задачу как решённую и удаляем из очереди
    result_id = Result.add(student, problem, teacher, set_verdict, None, RES_TYPE.WRITTEN)
    plus, minus = db.result.check_stat(problem.lesson, teacher.id)
    tot_checked = plus + minus
    milestone = CHECK_MILESTONES.get(tot_checked, '')
    if milestone:
        milestone = f'\n=====\n{milestone}\n====='
    if VERDICT_MODE == FEATURES.VERDICT_PLUS_MINUS:
        text = msgs.t_verdict_plus_text.format(
            problem=problem, student=student, tot_checked=tot_checked, plus=plus, minus=minus, milestone=milestone
        )
    else:
        verdict_text = VERDICT_TO_TICK[set_verdict]
        text = msgs.t_verdict_some_text.format(
            problem=problem, student=student, tot_checked=tot_checked, plus=plus, minus=minus, milestone=milestone, verdict_text=verdict_text
        )

    WrittenQueue.delete_from_queue(student.id, problem.id)
    reaction_msg = await bot.send_message(chat_id=query.message.chat.id,
                                          text=text,
                                          reply_markup=teacher_keyboards.build_teacher_reaction_on_solution(result_id),
                                          parse_mode='HTML')
    bot.remove_markup_after(reaction_msg, 15)
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    if RESULT_MODE == FEATURES.RESULT_IMMEDIATELY:
        asyncio.create_task(refresh_last_student_keyboard(student))  # Обновляем студенту клавиатуру со списком задач
        asyncio.create_task(forward_discussion_to_student(student, problem, set_verdict, result_id=result_id))
    asyncio.create_task(prc_teacher_select_action(None, teacher, 1 if milestone else 0))


# TODO Обойтись одним колбеком
@reg_callback(CALLBACK.WRITTEN_TASK_BAD)
async def prc_written_task_bad_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_written_task_bad_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    _, student_id, problem_id, set_verdict = query.data.split('_')
    set_verdict = VERDICT(int(set_verdict))
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(int(problem_id))
    # Помечаем решение как неверное и удаляем из очереди
    result_id = Result.add(student, problem, teacher, set_verdict, None, RES_TYPE.WRITTEN)
    db.result.delete_plus(student_id, problem.id, RES_TYPE.WRITTEN, VERDICT.REJECTED_ANSWER)
    plus, minus = db.result.check_stat(problem.lesson, teacher.id)
    tot_checked = plus + minus
    milestone = CHECK_MILESTONES.get(tot_checked, '')
    if milestone:
        milestone = f'\n=====\n{milestone}\n====='
    WrittenQueue.delete_from_queue(student.id, problem.id)
    await refresh_last_student_keyboard(student)  # Обновляем студенту клавиатуру со списком задач
    text = msgs.t_verdict_minus_text.format(
        problem=problem, student=student, tot_checked=tot_checked, plus=plus, minus=minus, milestone=milestone
    )
    teacher_msg = await bot.send_message(chat_id=query.message.chat.id, text=text, parse_mode='HTML')
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    # Пересылаем переписку школьнику
    if RESULT_MODE == FEATURES.RESULT_IMMEDIATELY:
        asyncio.create_task(refresh_last_student_keyboard(student))  # Обновляем студенту клавиатуру со списком задач
        asyncio.create_task(forward_discussion_to_student(student, problem, set_verdict, result_id=result_id))
    asyncio.create_task(prc_teacher_select_action(None, teacher, 1 if milestone else 0))


@reg_callback(CALLBACK.SEND_ANSWER)
async def prc_send_answer_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_send_answer_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    _, student_id, problem_id = query.data.split('_')
    student = User.get_by_id(int(student_id))
    problem = Problem.get_by_id(-int(problem_id))  # убираем минус SOS
    # Помечаем решение как неверное и удаляем из очереди
    WrittenQueue.delete_from_queue(student.id, -problem.id)  # возвращаем минус SOS
    await bot.send_message(chat_id=query.message.chat.id,
                           text=msgs.t_answer_recorded,
                           parse_mode='HTML')

    # Пересылаем переписку школьнику
    student_chat_id = User.get_by_id(student.id).chat_id
    try:
        discussion = WrittenQueue.get_discussion(student.id, -problem.id)  # возвращаем минус SOS
        await bot.send_message(chat_id=student_chat_id,
                               text=msgs.t_problem_question_answer.format_map({'problem': problem}),
                               disable_notification=True)
        for row in discussion[-20:]:  # Берём последние 20 сообщений, чтобы не превысить лимит
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
                               text='⬆⬆⬆⬆\n',
                               disable_notification=True)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student_chat_id}\n{e}')
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    await bot.answer_callback_query_ig(query.id)
    asyncio.create_task(prc_teacher_select_action(None, teacher))


@reg_callback(CALLBACK.GET_QUEUE_TOP)
async def prc_get_queue_top_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_queue_top_callback')
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=None)
    top = Waitlist.top(1)
    if not top:
        # Если в очереди пусто, то шлём сообщение и выходим.
        await bot.send_message(chat_id=teacher.chat_id,
                               text=msgs.t_queue_empty_retry)
        await bot.answer_callback_query_ig(query.id)
        await prc_teacher_select_action(query.message, teacher)
        return

    student = User.get_by_id(top[0]['student_id'])
    problem = Problem.get_by_id(top[0]['problem_id'])
    State.set_by_user_id(teacher.id, STATE.TEACHER_ACCEPTED_QUEUE, oral_problem_id=problem.id,
                         last_student_id=student.id)
    Waitlist.leave(student.id)
    db.delete_url_by_user_id(student.id)
    try:
        await bot.unpin_chat_message(chat_id=student.chat_id)
    except BadRequest:
        pass

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
                               reply_markup=student_keyboards.build_student_in_conference(),
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
                           text=msgs.t_oral_plus_give_surname,
                           reply_markup=teacher_keyboards.build_cancel_keyboard())
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
    student = User.get_by_id(student_id)
    Result.add(student, problem, teacher, verdict, None, RES_TYPE.ZOOM)
    await refresh_last_student_keyboard(student)  # Обновляем студенту клавиатуру со списком задач
    asyncio.create_task(prc_teacher_select_action(None, teacher))


@reg_callback(CALLBACK.STUDENT_SELECTED)
async def prc_student_selected_callback(query: types.CallbackQuery, teacher: User, *, remove_old_buttons=True):
    logger.debug('prc_student_selected_callback')
    _, student_id = query.data.split('_')
    student_id = int(student_id)
    student = User.get_by_id(student_id)
    msg_text = msgs.t_putting_plusses.format(student=student)
    if remove_old_buttons:
        await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                       reply_markup=None, text=msg_text)
    else:  # TODO ФИЧА НЕ РАБОТАЕТ!!
        await bot.send_message(chat_id=query.message.chat.id, reply_markup=None, text=msg_text)
    mode_label = msgs.t_online_mode_school if teacher.online == ONLINE_MODE.SCHOOL else msgs.t_online_mode_online
    text = msgs.t_mark_oral_tasks_intro.format(mode_label=mode_label)
    reply_markup = teacher_keyboards.build_verdict_for_oral_problems(
        plus_ids=set(),
        minus_ids=set(),
        student=student,
        online=teacher.online,
    )
    await bot.send_message(chat_id=query.message.chat.id,
                           text=text,
                           reply_markup=reply_markup)
    State.set_by_user_id(teacher.id, STATE.TEACHER_WRITES_STUDENT_NAME, last_student_id=student.id)
    await bot.answer_callback_query_ig(query.id)


@reg_callback(CALLBACK.ADD_OR_REMOVE_ORAL_PLUS)
async def prc_add_or_remove_oral_plus_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_add_or_remove_oral_plus_callback')
    state = State.get_by_user_id(teacher.id)
    student_id = state['last_student_id']
    student = User.get_by_id(student_id)
    if not student:
        # Что-то сломалось
        await prc_teacher_cancel_callback(query, teacher)
        await bot.answer_callback_query_ig(query.id)
        return
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
    lesson_num = Problem.get_by_id(problem_id).lesson
    reply_markup = teacher_keyboards.build_verdict_for_oral_problems(
        plus_ids=plus_ids, minus_ids=minus_ids,
        student=student, online=teacher.online,
        lesson_num=lesson_num,
    )
    await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                           reply_markup=reply_markup)
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
                                                 text=msgs.t_bot_broken_result_not_saved)
        await bot.answer_callback_query_ig(query.id)
        State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
        asyncio.create_task(prc_teacher_select_action(None, teacher))
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
    # Определяем занятие и уровень по задаче, за которую ставим плюс или минус
    any_problem = pluses[0] if pluses else minuses[0] if minuses else None
    if any_problem:
        zoom_conversation_id = db.zoom_conversation.insert(student_id=student_id, teacher_id=teacher.id, lesson=any_problem.lesson, level=any_problem.level)
    else:
        zoom_conversation_id = None
    # Заливаем плюсы и минусы в базу
    for problem in pluses:
        Result.add(student, problem, teacher, VERDICT.SOLVED, None, res_type, zoom_conversation_id=zoom_conversation_id)
        # А ещё нужно удалить эту задачу из очереди на письменную проверку
        db.written_task_queue.delete(student_id, problem.id)
    for problem in minuses:
        db.result.delete_plus(student_id, problem.id, RES_TYPE.SCHOOL, VERDICT.REJECTED_ANSWER)
        db.result.delete_plus(student_id, problem.id, RES_TYPE.ZOOM, VERDICT.REJECTED_ANSWER)
        Result.add(student, problem, teacher, VERDICT.WRONG_ANSWER, None, res_type, zoom_conversation_id=zoom_conversation_id)
    await refresh_last_student_keyboard(student)  # Обновляем студенту клавиатуру со списком задач

    # Формируем сообщение с итоговым результатом проверки
    text = msgs.t_written_res_1(student=student)
    if human_readable_pluses:
        human_readable_pluses_joined = ', '.join(human_readable_pluses)
        text += msgs.t_written_res_2(human_readable_pluses_joined=human_readable_pluses_joined)
    if human_readable_minuses:
        human_readable_minuses_joined = ', '.join(human_readable_minuses)
        text += msgs.t_written_res_3(human_readable_minuses_joined=human_readable_minuses_joined)
    if any_problem:
        lesson = any_problem.lesson
    else:
        lesson = Problem.last_lesson_num(student.level)
    text += msgs.t_written_res_4(student=student, lesson=lesson)
    await bot.edit_message_text_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                   text=text,
                                   reply_markup=None)
    # Предлагаем учителю оставить отзыв о устной сдаче, если есть хотя бы одна отметка
    if any_problem:
        zoom_reaction_msg = await bot.send_message(
            chat_id=query.message.chat.id,
            text=msgs.t_rate_oral_submission,
            reply_markup=teacher_keyboards.build_teacher_reaction_oral(zoom_conversation_id)
        )
        bot.delete_messages_after(zoom_reaction_msg, 15)

    # Посылаем сообщения школьнику о проверке (если хотя бы одна задача проверена)
    try:
        if any_problem:
            pluses_list = ', '.join(human_readable_pluses)
            student_message = await bot.send_message(chat_id=student.chat_id,
                                                     text=msgs.oral_accepted_problems.format_map({'pluses_list': pluses_list}),
                                                     reply_markup=student_keyboards.build_student_reaction_oral(zoom_conversation_id),
                                                     disable_notification=True)
        # Этот кусок для не работающего пока функционала
        student_state = State.get_by_user_id(student.id)
        if student_state['state'] == STATE.STUDENT_IS_IN_CONFERENCE:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
            await process_regular_message(student_message)
    except aiogram.utils.exceptions.TelegramAPIError as e:
        logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
    # Ура, сообщение обработано!
    await bot.answer_callback_query_ig(query.id)
    # Сохраняем учителю режим внесения устных задач, сразу работает в режиме «ведите фамилию»
    await prc_ins_oral_plusses(query, teacher)
    # State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    # asyncio.create_task(prc_teacher_select_action(None, teacher))


@router.message(Command('find_student', 'fs'))
async def find_student(message: types.Message):
    logger.debug('find_student')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    search = None
    if (match := re.match(r'/\w+\s+(\S+)', message.text or '')):
        search = match.group(1)
    if not search:
        await bot.send_message(chat_id=message.chat.id, text=msgs.t_find_student_hint, )
        return
    students = sorted(
        User.all_students(),
        key=lambda user: min(
            -jaro_winkler(search.lower(), f'{user.surname} {user.name} {user.token}'.lower(), prefix_weight=1 / 32),
            -jaro_winkler(search, user.token, prefix_weight=1 / 32),
        )
    )
    if students:
        lines = [
            f'{student.surname:<20} {student.name:<15} {student.level} {student.token} {"🏫" if student.online == ONLINE_MODE.SCHOOL else "📡"}'
            for student in students[:10]]
        await bot.send_message(chat_id=message.chat.id, parse_mode="HTML", text='<pre>' + '</pre>\n<pre>'.join(lines) + '</pre>')
    else:
        await bot.send_message(chat_id=message.chat.id, text=msgs.t_no_students_found)


@router.message(Command('set_online', 'so'))
async def set_online(message: types.Message):
    logger.debug('set_online')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.split()
    try:
        cmd, token, new_online = text
    except:
        await bot.send_message(chat_id=message.chat.id, text=msgs.t_teacher_set_online_usage, )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id, text=msgs.t_stundent_name_not_found.format(token=token))
        return
    new_online = ONLINE_MODE_DECODER.get(new_online.strip(), None)
    if new_online:
        student.set_online_mode(new_online)
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.t_student_online_changed.format_map({'token': token}),
        )


@router.message(Command('set_teacher', 'st'))
async def set_teacher(message: types.Message):
    '''
    После тестирования ответов в боте учителю нужно снова вернуться в своё учительское состояние.
    '''
    logger.debug('set_teacher')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    State.set_by_user_id(teacher.id, STATE.TEACHER_SELECT_ACTION)
    asyncio.create_task(prc_teacher_select_action(None, teacher))


@reg_callback(CALLBACK.CHANGE_LEVEL)
async def prc_change_level_callback(query: types.CallbackQuery, teacher: User):
    logger.debug('prc_get_written_task_callback')
    # Пока не трогаем старую клаву
    # await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id,
    #                                        reply_markup=None)
    _, student_id, lvl = query.data.split('_')
    student = User.get_by_id(int(student_id))
    level = LEVEL(lvl)
    if student:
        student.set_level(level)
        if State.get_by_user_id(student.id)['state'] != STATE.STUDENT_IS_SLEEPING:
            State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        if student.chat_id:
            message = await bot.send_message(
                chat_id=student.chat_id,
                text=msgs.your_level_changed_to.format_map({'level': level}),
            )
            asyncio.create_task(sleep_and_send_problems_keyboard(message.chat.id, student))
        await bot.send_message(
            chat_id=query.message.chat.id,
            text=msgs.t_student_level_changed(level=level),
        )
        query.data = f'{CALLBACK.STUDENT_SELECTED}_{student_id}'
        await prc_student_selected_callback(query, teacher)
    await bot.answer_callback_query_ig(query.id)


@router.message(Command('zoom_queue', 'z', 'zall'))
async def zoom_queue(message: types.Message):
    '''
    Вывести очередь школьников
    '''
    logger.debug('zoom_queue')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    show_all = 'all' in message.text
    queue = db.zoom_queue.get_first_from_queue(show_all)
    # [{'zoom_user_name': 'name3', 'enter_ts': '2022-01-01 02:00:00', 'status': 0}]
    show_queue = []
    for row in queue:
        waits = datetime.datetime.now() - datetime.datetime.fromisoformat(row['enter_ts'])
        waits_min = (waits.total_seconds() + 30) // 60
        if row['status'] == 1:
            alert = ' (в основном зале)'
        elif row['status'] == -1:
            alert = ' (нет в конфе)'
            # Если нет в конфе, то и не показываем
            continue
        else:
            alert = ''
        show_queue.append(f'{waits_min} мин   {row["zoom_user_name"]}  {alert}')
    in_queue = db.zoom_queue.get_queue_count()
    show_queue.append(f'\nВсего в очереди: {in_queue} человек')
    await bot.send_message(
        chat_id=message.chat.id,
        text='Очередь в конференции:\n' + '\n'.join(show_queue)
    )
    teacher_state = State.get_by_user_id(teacher.id)
    if teacher_state['state'] == STATE.TEACHER_SELECT_ACTION:
        await prc_teacher_select_action(message, teacher, 1)

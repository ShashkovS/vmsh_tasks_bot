import logging

import aiogram
from aiogram import types
import asyncio
import re

from helpers.consts import *
from helpers.config import logger, config
from models import User, Problem, State
from models.spreadsheets import FromGoogleSpreadsheet
import db_methods as db
from helpers.bot import bot, dispatcher
from handlers import student_keyboards
from handlers.student_handlers import (
    check_test_problem_answer, ANS_CHECK_VERDICT, post_problem_keyboard, refresh_last_student_keyboard,
    prc_student_is_sleeping_state,
)


@dispatcher.message_handler(commands=['update_all_quaLtzPE', 'update_all'])
async def update_all_internal_data(message: types.Message):
    logger.debug('update_all_internal_data')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    errors = FromGoogleSpreadsheet.update_all()
    await bot.send_message(
        chat_id=message.chat.id,
        text="Все данные обновлены" + (('\nОшибки:\n' + '\n'.join(errors)) if errors else ''),
    )


@dispatcher.message_handler(commands=['update_teachers', 'ut'])
async def update_teachers(message: types.Message):
    logger.debug('update_teachers')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    FromGoogleSpreadsheet.update_teachers()
    await bot.send_message(
        chat_id=message.chat.id,
        text="Учителя обновлены",
    )


@dispatcher.message_handler(commands=['update_students', 'us'])
async def update_students(message: types.Message):
    logger.debug('update_students')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    FromGoogleSpreadsheet.update_students()
    await bot.send_message(
        chat_id=message.chat.id,
        text="Студенты обновлены",
    )


@dispatcher.message_handler(commands=['update_problems', 'up'])
async def update_problems(message: types.Message):
    logger.debug('update_problems')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    errors = FromGoogleSpreadsheet.update_problems()
    await bot.send_message(
        chat_id=message.chat.id,
        text="Задачи обновлены" + (('\nОшибки:\n' + '\n'.join(errors)) if errors else ''),
    )


async def run_broadcast_task(teacher_chat_id, tokens, broadcast_message, html_mode: bool = False, reply_to_message: types.Message = None, quite=False):
    logger.debug('run_broadcast_task')
    tokens = set(tokens)
    all_students = None
    if any(tok.startswith('all_') for tok in tokens):
        all_students = User.all_students()
    if 'all_students' in tokens:
        tokens |= {user.token for user in all_students}
    elif 'all_teachers' in tokens:
        tokens |= {user.token for user in User.all_teachers()}
    elif 'all_novice' in tokens:
        tokens |= {user.token for user in all_students if user.level == LEVEL.NOVICE}
    elif 'all_pro' in tokens:
        tokens |= {user.token for user in all_students if user.level == LEVEL.PRO}
    elif 'all_expert' in tokens:
        tokens |= {user.token for user in all_students if user.level == LEVEL.EXPERT}
    elif 'all_gr8' in tokens:
        tokens |= {user.token for user in all_students if user.level == LEVEL.GR8}
    elif 'all_online' in tokens:
        tokens |= {user.token for user in all_students if user.online == ONLINE_MODE.ONLINE and user.level != LEVEL.GR8}  # TODO Trash
    elif 'all_school' in tokens:
        tokens |= {user.token for user in all_students if user.online == ONLINE_MODE.SCHOOL and user.level != LEVEL.GR8}  # TODO Trash
    parse_mode = 'HTML' if html_mode else None
    bad_tokens = []
    sent = 0
    for token in tokens:
        student = User.get_by_token(token)
        if not student or not student.chat_id:
            continue
        try:
            if reply_to_message:
                broad_message = await bot.copy_message(student.chat_id, reply_to_message.chat.id, reply_to_message.message_id)
            else:
                broad_message = await bot.send_message(
                    chat_id=student.chat_id,
                    text=broadcast_message,
                    disable_web_page_preview=True,
                    parse_mode=parse_mode,
                    disable_notification=quite,
                )
            sent += 1
            db.log.insert(
                True, broad_message.message_id, student.chat_id, student.id, None,
                broadcast_message, None
            )
        except aiogram.exceptions.TelegramAPIError as e:
            logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
            bad_tokens.append(token)
        await asyncio.sleep(1 / 20)  # 20 messages per second (Limit: 30 messages per second)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все сообщения разосланы ({sent} штук). Проблемы возникли с {bad_tokens!r}",
    )


@dispatcher.message_handler(commands=['broadcast_wibkn96x', 'broadcast', 'broadcast_html', 'broadcast_quiet', 'broadcast_html_quiet'])
async def broadcast(message: types.Message):
    logger.debug('broadcast')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.splitlines()
    try:
        cmd, tokens, *broadcast_message = text
    except:
        return
    html_mode = 'html' in cmd
    quite = 'quiet' in cmd
    if message.reply_to_message:
        broadcast_message = message.reply_to_message.text or ''
    else:
        broadcast_message = '\n'.join(broadcast_message)
    tokens = re.split(r'\W+', tokens)
    asyncio.create_task(run_broadcast_task(message.chat.id, tokens, broadcast_message, html_mode, message.reply_to_message, quite))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание рассылки сообщений",
    )


@dispatcher.message_handler(commands=['forward_all'])
async def forward_all_messages(message: types.Message):
    logger.debug('forward_all_messages')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.strip().split()
    try:
        cmd, token, start, end = text
        start = int(start)
        end = int(end)
    except:
        return
    student = User.get_by_token(token)
    if not student or not student.chat_id:
        return
    await bot.send_message(
        chat_id=message.chat.id,
        text="Начинаем пересылать",
    )
    errors = []
    for id in range(start, end + 1):
        try:
            await bot.forward_message(message.chat.id, student.chat_id, id)
            await asyncio.sleep(1 / 20)
        except Exception as e:
            errors.append((id, e.__class__.__name__))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Ошибки: " + '\n'.join(str(row) for row in errors),
    )


@dispatcher.message_handler(commands=['create_survey'])
async def create_survey(message: types.Message):
    logger.debug('create_survey')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    text = message.text.strip()
    try:
        survey_type = SURVEY_TYPES(re.match(r'/create_survey\s+(\w)', text).group(1))
        choices = re.findall(r'^[-*]\s+(.*)', text, flags=re.MULTILINE)
        question = re.fullmatch(r'/create_survey\s+\w *\n([\s\S]*?)(?:^[-*]\s+(?:.*)\n?)+\s*', text, flags=re.MULTILINE).group(1).strip()
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text='/create_survey r/c\nВопрос\n- Один\n- Два')
        return
    survey_id = db.survey.add_survey(survey_type, True, question, choices)
    text = f'''Опрос с id={survey_id} создан.
    {survey_type=}
    {question=}
    {choices=}
    '''
    await bot.send_message(chat_id=message.chat.id, text=text)


@dispatcher.message_handler(commands=['disable_survey'])
async def disable_survey(message: types.Message):
    logger.debug('disable_survey')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    cmd, survey_id = message.text.strip().split()
    try:
        survey_id = int(survey_id)
    except Exception as e:
        return
    db.survey.disable_survey(survey_id)
    await bot.send_message(chat_id=message.chat.id, text=f'Опрос {survey_id} отключён')


@dispatcher.message_handler(commands=['assign_survey_to_tokens'])
async def assign_survey_to_tokens(message: types.Message):
    logger.debug('assign_survey_to_tokens')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    try:
        first, second = message.text.strip().splitlines()
        cmd, survey_id = first.split()
        survey_id = int(survey_id)
        survey = db.survey.get_survey_by_id(survey_id)
        assert survey is not None
        tokens = second.split()
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f'/assign_survey_to_tokens surv_id\ntok1 tok2 tok3')
        return
    done = 0
    users = [User.get_by_token(token) for token in tokens]
    db.survey.assign_survey(survey_id, [user.id for user in users if user])
    for user in users:
        if user and user.chat_id:
            try:
                await post_problem_keyboard(user.chat_id, user)
            except Exception as e:
                logger.exception(e)
            await asyncio.sleep(1 / 20)
            done += 1
    await bot.send_message(chat_id=message.chat.id, text=f'Назначен опрос {survey_id} {done} пользователям')


TEACHER_COMMANDS = [
    aiogram.types.BotCommand(command='online', description='Дистанционный приём'),
    aiogram.types.BotCommand(command='in_school', description='Очный приём'),
    aiogram.types.BotCommand(command='find_student', description='Найти студента'),
    aiogram.types.BotCommand(command='set_level', description='Поставить студенту уровень'),
    aiogram.types.BotCommand(command='set_online', description='Поменять студенту режим очно/дистант'),
    aiogram.types.BotCommand(command='level_novice', description='Перейти на уровень «Начинающие»'),
    aiogram.types.BotCommand(command='level_pro', description='Перейти на уровень «Продолжающие»'),
    aiogram.types.BotCommand(command='level_expert', description='Перейти на уровень «Профессионалы»'),
    aiogram.types.BotCommand(command='set_teacher', description='Снова стать учителем'),
    aiogram.types.BotCommand(command='statw', description='Посмотреть статистику'),
    aiogram.types.BotCommand(command='student_results', description='Посмотреть результаты школьника'),
]


async def update_teachers_commands_task(teacher_chat_id):
    for user in User.all_teachers():
        if not user.chat_id:
            continue
        await bot.set_my_commands(commands=TEACHER_COMMANDS, scope=aiogram.types.BotCommandScope(type='chat', chat_id=user.chat_id))
        await asyncio.sleep(1 / 20)  # 20 messages per second (Limit: 30 messages per second)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Команды учителей обновлены",
    )


@dispatcher.message_handler(commands=['update_teachers_commands'])
async def update_teachers_commands(message: types.Message):
    logger.debug('update_teachers_commands')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    asyncio.create_task(update_teachers_commands_task(message.chat.id))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание обновления статусов",
    )


async def recheck_problem_task(teacher_chat_id: int, problem: Problem):
    for_recheck = db.result.get_for_recheck_by_problem_id(problem.id)
    oks = errs = changes = 0
    students_to_update_keyboards = set()
    for row in for_recheck:
        check_verdict, _, error_text = check_test_problem_answer(problem, student=None, student_answer=row["answer"])
        if error_text:
            await bot.post_logging_message(error_text)
        row["old_verdict"] = old_verdict = row["verdict"]
        if check_verdict == ANS_CHECK_VERDICT.CORRECT:
            row["verdict"] = VERDICT.SOLVED
            oks += 1
        else:
            row["verdict"] = VERDICT.WRONG_ANSWER
            errs += 1
        if old_verdict != row["verdict"]:
            changes += 1
            students_to_update_keyboards.add(row['student_id'])
    db.result.update_verdicts(for_recheck)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Задача {problem} перепроверена. {oks} плюсов, {errs} минусов. Исправлено {changes} посылок",
    )
    # Обновляем клавиатуры школьникам
    for student_id in students_to_update_keyboards:
        student = User.get_by_id(student_id)
        await refresh_last_student_keyboard(student)


@dispatcher.message_handler(commands=['problem_recheck', 'prc'])
async def problem_recheck(message: types.Message):
    logger.debug('problem_recheck')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    problem = None
    if match := re.fullmatch(r'/\w+?\s+(\d+)([а-яА-Яa-zA-Z]\w*)\.(\d+)([а-я]?)\s*', message.text or ''):
        lst, level, prob, item = match.groups()
        problem = Problem.get_by_key(level, int(lst), int(prob), item)
    if problem is None:
        await bot.send_message(chat_id=message.chat.id, text=f"Задача не найдена")
        return
    asyncio.create_task(recheck_problem_task(message.chat.id, problem))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание по перепроверке тестовой задачи",
    )


async def run_set_get_task_info_for_all_students_task(teacher_chat_id):
    logger.debug('run_set_get_task_info_for_all_students_task')
    # Всем студентам, у которых есть chat_id ставим state STATE.GET_TASK_INFO и отправляем список задач
    for student in User.all_students():
        db.last_keyboard.delete(student.id)
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        logger.info(f'{student.id} оживлён')
        if not student.chat_id:
            continue
        try:
            await post_problem_keyboard(student.chat_id, student)
        except:
            pass
        await asyncio.sleep(1 / 20)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все школьники переведены в режим сдачи задач",
    )


async def update_all_student_keyboards(teacher_chat_id, force=False):
    logger.debug('update_all_student_keyboards')
    num_updated = 0
    errors = []
    not_updated = 0
    for student in User.all_students():
        try:
            updated = await refresh_last_student_keyboard(student, force)
            num_updated += 1
            not_updated += not updated
        except Exception as e:
            logger.exception(e)
            updated = True
            errors.append(student.token)
        if updated:
            await asyncio.sleep(1 / 20)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все плюсики обновлены: {num_updated} обновлено, {not_updated} не обновлено, {len(errors)} ошибок.",
    )
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Ошибки по: `{'`, `'.join(errors)}`",
    )


@dispatcher.message_handler(commands=['reset_keyboards', 'rk', 'reset_keyboards_force', 'rkf'])
async def reset_keyboards(message: types.Message):
    logger.debug('reset_keyboards')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    force = 'force' in message.text or 'rkf' in message.text
    asyncio.create_task(
        update_all_student_keyboards(
            message.chat.id,
            force=force
        )
    )
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"Создано задание по обновлению плюсиков запущено, {force=}",
    )


@dispatcher.message_handler(commands=['reset_state_jvcykgny', 'reset_state'])
async def set_get_task_info_for_all_students(message: types.Message):
    logger.debug('set_get_task_info_for_all_students')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    asyncio.create_task(run_set_get_task_info_for_all_students_task(message.chat.id))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание по переводу в режим сдачи задач",
    )


async def run_set_sleep_state_task(teacher_chat_id):
    logger.debug('run_set_sleep_state_task')
    # Всем студентам ставим state STATE.STUDENT_IS_SLEEPING. Прекращаем приём задач
    for student in User.all_students():
        State.set_by_user_id(student.id, STATE.STUDENT_IS_SLEEPING)
        if not student.chat_id:
            continue
        try:
            await post_problem_keyboard(student.chat_id, student, blocked=True)
        except:
            pass
        try:
            await prc_student_is_sleeping_state(None, student)
        except:
            pass
        await asyncio.sleep(1 / 20)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все школьники переведены в статус SLEEPING",
    )


@dispatcher.message_handler(commands=['set_sleep_state'])
async def set_sleep_state_for_all_students(message: types.Message):
    logger.debug('set_sleep_state_for_all_students')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    asyncio.create_task(run_set_sleep_state_task(message.chat.id))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание по переводу в статус SLEEPING",
    )


@dispatcher.message_handler(commands=['stat'])
async def calc_last_lesson_stat(message: types.Message):
    logger.debug('calc_last_lesson_stat')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    stat = db.report.calc_last_lesson_stat()
    msg = '\n'.join(map(lambda r: '  '.join(r.values()), stat))
    for i in range(0, len(msg), 4096):
        await bot.send_message(
            chat_id=message.chat.id,
            text=msg[i:i + 4096],
        )


@dispatcher.message_handler(commands=['statw'])
async def get_statw_url(message: types.Message):
    logger.debug('statw')
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        return
    url = f'https://{config.webhook_host}/stat'
    await bot.send_message(
        chat_id=message.chat.id,
        text=url,
    )
    await bot.send_message(
        chat_id=message.chat.id, parse_mode="HTML",
        text=f"Ваш пароль:\n<code>{user.token}</code>",
    )


@dispatcher.message_handler(commands=['student_results', 'sr', 'all_student_results', 'asr'])
async def student_results(message: types.Message):
    logger.debug('student_results')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    token = student = None
    if (match := re.match(r'/\w+\s+(\S+)', message.text or '')):
        token = match.group(1)
        student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id, text=f"🤖 Студент {token} не найден", )
        return

    # r.ts, p.level, p.lesson, p.prob, p.item, r.answer, r.verdict
    if 'asr' in message.text or 'all_' in message.text:
        rows = db.result.list_all_student_results(student.id)
    else:
        rows = db.result.list_student_results(student.id, Problem.last_lesson_num(student.level))
    if rows:
        lessons = {row['lesson'] for row in rows}
        for lesson in sorted(lessons):
            lines = [f'{row["ts"][5:16]} {row["lesson"]:02}{row["level"]}.{row["prob"]:02}{row["item"]:<1} {VERDICT_DECODER[row["verdict"]]} {row["answer"]}'
                     for row in rows
                     if row['lesson'] == lesson
                     ]
            await bot.send_message(chat_id=message.chat.id, parse_mode="HTML", text='<pre>' + '\n'.join(lines) + '</pre>')
    else:
        await bot.send_message(chat_id=message.chat.id, text='Нет ни одной посылки (или что-то пошло не так)')


@dispatcher.message_handler(commands=['oral2written', 'written2oral'])
async def oral2written(message: types.Message):
    logger.debug('oral2written')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    cmd, *slevels = message.text.split()
    levels = None
    if slevels:
        try:
            levels = [LEVEL(x) for x in slevels]
        except Exception as e:
            await bot.send_message(chat_id=message.chat.id, text='Кривой уровень, не парсится')
            return
    if cmd == '/oral2written':
        Problem.oral_to_written(levels)
    elif cmd == '/written2oral':
        Problem.written_to_oral(levels)
    await bot.send_message(chat_id=message.chat.id, text='Готово')


@dispatcher.message_handler(commands=['reset_checked'])
async def reset_checked(message: types.Message):
    logger.debug('reset_checked')
    db.written_task_queue.reset_beeing_checked()
    await bot.send_message(chat_id=message.chat.id, text='Готово')


@dispatcher.message_handler(commands=['set_game_command', 'sg'])
async def set_game_command(message: types.Message):
    logger.debug('set_game_command')
    teacher = User.get_by_chat_id(message.chat.id)
    if not teacher or teacher.type != USER_TYPE.TEACHER:
        return
    parts = message.text.split()
    command_id = None
    if len(parts) == 2:
        cmd, command_id = parts
        token = teacher.token
    elif len(parts) == 3:
        cmd, token, command_id = parts
    try:
        command_id = int(command_id)
    except:
        await bot.send_message(chat_id=message.chat.id, text=f"/set_game_command token number", )
        return
    student = User.get_by_token(token)
    if not student:
        await bot.send_message(chat_id=message.chat.id, text=f"Студент с токеном {token} не найден", )
        return
    db.game.set_student_command(student.id, student.level, command_id)
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"Студент с токеном {token} переведён в команду {command_id}",
    )

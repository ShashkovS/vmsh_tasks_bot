import aiogram
from aiogram import types
import asyncio
import re

from helpers.consts import *
from helpers.config import logger
from helpers.obj_classes import User, Problem, State, FromGoogleSpreadsheet, db
from helpers.bot import bot, dispatcher
from handlers import student_keyboards


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


@dispatcher.message_handler(commands=['update_teachers'])
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


@dispatcher.message_handler(commands=['update_students'])
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


@dispatcher.message_handler(commands=['update_problems'])
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


async def run_broadcast_task(teacher_chat_id, tokens, broadcast_message):
    logger.debug('run_broadcast_task')
    if tokens == ['all_students']:
        tokens = [user.token for user in User.all_students()]
    elif tokens == ['all_novice']:
        tokens = [user.token for user in User.all_students() if user.level == LEVEL.NOVICE]
    elif tokens == ['all_pro']:
        tokens = [user.token for user in User.all_students() if user.level == LEVEL.PRO]
    elif tokens == ['all_expert']:
        tokens = [user.token for user in User.all_students() if user.level == LEVEL.EXPERT]
    elif tokens == ['all_teachers']:
        tokens = [user.token for user in User.all_teachers()]
    bad_tokens = []
    for token in tokens:
        student = User.get_by_token(token)
        if not student or not student.chat_id:
            continue
        try:
            broad_message = await bot.send_message(
                chat_id=student.chat_id,
                text=broadcast_message,
                disable_web_page_preview=True,
            )
            db.add_message_to_log(True, broad_message.message_id, broad_message.chat.id, student.id, None,
                                  broadcast_message, None)
        except aiogram.utils.exceptions.TelegramAPIError as e:
            logger.info(f'Школьник удалил себя или забанил бота {student.chat_id}\n{e}')
            bad_tokens.append(token)
        await asyncio.sleep(1 / 20)  # 20 messages per second (Limit: 30 messages per second)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все сообщения разосланы. Проблемы возникли с {bad_tokens!r}",
    )


@dispatcher.message_handler(commands=['broadcast_wibkn96x', 'broadcast'])
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
    broadcast_message = '\n'.join(broadcast_message)
    tokens = re.split(r'\W+', tokens)
    asyncio.create_task(run_broadcast_task(message.chat.id, tokens, broadcast_message))
    await bot.send_message(
        chat_id=message.chat.id,
        text="Создано задание рассылки сообщений",
    )


async def run_set_get_task_info_for_all_students_task(teacher_chat_id):
    logger.debug('run_set_get_task_info_for_all_students_task')
    # Всем студентам, у которых есть chat_id ставим state STATE.GET_TASK_INFO и отправляем список задач
    for student in User.all_students():
        State.set_by_user_id(student.id, STATE.GET_TASK_INFO)
        logger.info(f'{student.id} оживлён')
        if not student.chat_id:
            continue
        try:
            slevel = f'(уровень «{student.level.slevel}»)'
            await bot.send_message(
                chat_id=student.chat_id,
                text=f"Можно сдавать задачи!\n❓ Нажимайте на задачу, чтобы сдать её {slevel}",
                reply_markup=student_keyboards.build_problems(Problem.last_lesson_num(), student),
            )
        except:
            pass
        await asyncio.sleep(1 / 20)
    await bot.send_message(
        chat_id=teacher_chat_id,
        text=f"Все школьники переведены в режим сдачи задач",
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
            await bot.send_message(
                chat_id=student.chat_id,
                text="🤖 Приём задач ботом окончен до начала следующего занятия.\n"
                     "Заходите в канал @vmsh_179_5_7_2021 кружка за новостями и решениями.",
            )
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
    stat = db.calc_last_lesson_stat()
    msg = '\n'.join(map(lambda r: '  '.join(r.values()), stat))
    await bot.send_message(
        chat_id=message.chat.id,
        text=msg,
    )

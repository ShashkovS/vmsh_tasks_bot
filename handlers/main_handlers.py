import asyncio
import traceback
from aiogram.dispatcher.webhook import types

from helpers.consts import *
from helpers.config import logger, config
from models import User, State
import db_methods as db
from helpers.bot import bot, dispatcher, reg_state, callbacks_processors, state_processors
from handlers.student_handlers import post_problem_keyboard

@dispatcher.message_handler(commands=['start'])
async def start(message: types.Message):
    logger.debug('start')
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        user = User(message.chat.id, USER_TYPE.STUDENT, LEVEL.NOVICE, message.chat.first_name or '', message.chat.last_name or '', '',
                    str(message.chat.id), ONLINE_MODE.ONLINE, 12, None)
    db.log.log_signon(user and user.id, message.chat.id, message.chat.first_name, message.chat.last_name, message.chat.username, message.text)
    row = db.sql.conn.execute('''
        select command_id, count(*) cnt from game_map_opened_cells
        group by command_id order by command_id desc
        limit 1;
    ''').fetchone()
    if not row:
        command_id = 1
    else:
        command_id = row['command_id']
        # cnt = row['cnt']
        # if cnt > 450:
        #     command_id += 1
    db.set_student_command(user.id, LEVEL.NOVICE, command_id)
    await bot.send_message(
        chat_id=message.chat.id,
        text="🤖 Привет! Это бот для сдачи задач, вот этих: https://shashkovs.ru/vmsh/2022/n/#34-n.\n"
             "Если задачи окажутся простоватыми, то можно выполнить команду /level_pro и решать вот эти задачи https://shashkovs.ru/vmsh/2022/p/#34-p, они сложнее и их больше.",
    )
    State.set_by_user_id(user.id, STATE.GET_TASK_INFO)
    await post_problem_keyboard(message.chat.id, user)


@reg_state(STATE.GET_USER_INFO)
async def prc_get_user_info_state(message: types.Message, user: User):
    logger.debug('prc_get_user_info_state')
    user = User.get_by_token(message.text)
    db.log.log_signon(user and user.id, message.chat.id, message.chat.first_name, message.chat.last_name, message.chat.username, message.text)
    if user is None:
        await start(message)
        return
    elif user.type == USER_TYPE.DELETED:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🔁 Этот пароль был заблокирован.\n"
                 "Скорее всего новый пароль был выслан по электронной почте, не забудьте проверить спам.",
        )
    else:
        User.set_chat_id(user, message.chat.id)
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"🤖 ОК, Добро пожаловать, {user.name} {user.surname}",
        )
        if user.type == USER_TYPE.STUDENT:
            State.set_by_user_id(user.id, STATE.GET_TASK_INFO)
        elif user.type == USER_TYPE.TEACHER:
            State.set_by_user_id(user.id, STATE.TEACHER_SELECT_ACTION)
        elif user.type == USER_TYPE.DEACTIVATED_STUDENT:
            State.set_by_user_id(user.id, STATE.USER_IS_NOT_ACTIVATED)
        await process_regular_message(message)


@reg_state(STATE.USER_IS_NOT_ACTIVATED)
async def prc_user_is_not_activated_state(message: types.Message, user: User):
    logger.debug('prc_user_is_not_activated_state')
    await bot.send_message(
        chat_id=message.chat.id,
        text="🔁 Привет!\n"
             "Для начала обучения нужно оставить заявку на обучение на кружке на mos,ru.\n"
             "Через несколько рабочих дней на почту придёт инструкция, а ваш аккаунт будет активирован.\n"
             "Подробно про оформление: https://shashkovs.ru/vmsh/2023/n/about.html#application",
    )


async def prc_WTF(message: types.Message, user: User):
    logger.debug('prc_WTF')
    await bot.send_message(
        chat_id=message.chat.id,
        text="☢️ Всё сломалось, бот запутался в текущей ситации :(. Начнём сначала!",
    )
    logger.error(f"prc_WTF: {user!r} {message!r}")
    State.set_by_user_id(user.id, STATE.GET_TASK_INFO)
    await asyncio.sleep(1)
    await process_regular_message(message)


@dispatcher.callback_query_handler()
async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    logger.debug('inline_kb_answer_callback_handler')
    if query.message:
        user = User.get_by_chat_id(query.message.chat.id)
        if not user:
            try:
                await bot.edit_message_reply_markup_ig(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None)
            except:
                pass  # Ошибки здесь не важны
            await start(query.message)
            return
        # Если нет данных, то игнорируем
        # (это специальные кнопки «без реакции»)
        if not query.data:
            return
        callback_type = query.data[0]  # Вот здесь существенно используется, что callback параметризуется одной буквой
        callback_processor = callbacks_processors.get(callback_type, None)
        try:
            await callback_processor(query, user)
        except Exception as e:
            error_text = traceback.format_exc()
            logger.exception(f'SUPERSHIT_CALLBACK: {e}')
            await bot.post_logging_message(error_text)


# Важно, чтобы эта регистрация была последней
# @dispatcher.message_handler(content_types=["any"])
async def process_regular_message(message: types.Message):
    logger.debug('process_regular_message')
    # Сначала проверяем, что этот тип сообщений мы вообще поддерживаем
    alarm = None
    if message.document and message.document.mime_type and message.document.mime_type.startswith('image'):
        alarm = '❗❗❗ Бот принимает только сжатые фото: отправляйте картинки по одной, ставьте галочку «Сжать/Compress»'
    elif not message.text and not message.photo:
        alarm = '❗❗❗ Бот принимает только текстовые сообщения и фотографии решений.'
    if alarm:
        try:
            await bot.send_message(chat_id=message.chat.id, text=alarm)
        except Exception as e:
            logger.exception(f'SHIT: {e}')
        return
    # Ок, теперь обрабатываем сообщение

    # Может так статься, что сообщение будет ходить кругами по функциям и будет обработано несколько раз.
    # Некоторым функциям это может быть важно
    # message.num_processed = getattr(message, 'num_processed', 0) + 1
    user = User.get_by_chat_id(message.chat.id)
    if not user:
        await start(message)
        return
    else:
        if user.type == USER_TYPE.DEACTIVATED_STUDENT:
            cur_chat_state = STATE.USER_IS_NOT_ACTIVATED
            State.set_by_user_id(user.id, STATE.USER_IS_NOT_ACTIVATED)
        else:
            cur_chat_state = State.get_by_user_id(user.id)
            if cur_chat_state:
                cur_chat_state = cur_chat_state['state']
    if not cur_chat_state:
        State.set_by_user_id(user.id, STATE.GET_USER_INFO)
        return

    if not message.document and not message.photo:
        db.log.insert(False, message.message_id, message.chat.id, user and user.id, None, message.text, None)
    state_processor = state_processors.get(cur_chat_state, prc_WTF)
    try:
        await state_processor(message, user)
    except Exception as e:
        error_text = traceback.format_exc()
        logger.exception(f'SUPERSHIT_STATE: {e}')
        await bot.post_logging_message(error_text)


@dispatcher.message_handler(commands=['online'])
async def mode_online(message: types.Message):
    logger.debug('mode_online')
    user = User.get_by_chat_id(message.chat.id)
    if user:
        await bot.send_message(chat_id=message.chat.id, text="Теперь вы работаете в режиме «Онлайн»", )
        user.set_online_mode(ONLINE_MODE.ONLINE)
    else:
        await start(message)


@dispatcher.message_handler(commands=['in_school'])
@dispatcher.message_handler(commands=['inschool'])
@dispatcher.message_handler(commands=['school'])
async def mode_school(message: types.Message):
    logger.debug('mode_school')
    user = User.get_by_chat_id(message.chat.id)
    if user:
        await bot.send_message(chat_id=message.chat.id, text="Теперь вы работаете в режиме «Очно в школе»", )
        user.set_online_mode(ONLINE_MODE.SCHOOL)
    else:
        await start(message)

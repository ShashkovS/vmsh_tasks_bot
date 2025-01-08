import asyncio
import traceback
from aiogram.dispatcher.webhook import types

from helpers.consts import *
from helpers.config import logger, config
from helpers.features import REG_MODE, FEATURES
from models import User, State
import db_methods as db
from helpers.bot import bot, dispatcher, reg_state, callbacks_processors, state_processors
from helpers.msg_texts import msgs
from handlers.student_handlers import post_problem_keyboard


def assign_default_game_command(user):
    # TODO Треш, конечно. Нужно отсюда убрать и переделать
    row = db.sql.conn.execute(
        '''
                select command_id, count(*) cnt from game_map_opened_cells
                group by command_id order by command_id desc
                limit 1;
            '''
    ).fetchone()
    if not row:
        command_id = 1
    else:
        command_id = row['command_id']
        cnt = row['cnt']
        if cnt > 450 and command_id <= 1:
            command_id += 1
    db.game.set_student_command(user.id, LEVEL.NOVICE, command_id)


@dispatcher.message_handler(commands=['start'])
async def start(message: types.Message):
    logger.debug('start')
    user = User.get_by_chat_id(message.chat.id)
    if REG_MODE == FEATURES.REG_NEEDED:
        if user:
            State.set_by_user_id(user.id, STATE.GET_USER_INFO)
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.start_if_reg_needed,
        )
    elif REG_MODE == FEATURES.REG_ANYBODY:
        if not user:
            user = User(
                message.chat.id, USER_TYPE.STUDENT, LEVEL.NOVICE,
                name=message.chat.first_name or '',
                surname=message.chat.last_name or '',
                middlename='',
                token=str(message.chat.id),
                online=ONLINE_MODE.ONLINE,
                grade=12,
                birthday=None
            )
            assign_default_game_command(user)
        db.log.log_signon(
            user and user.id, message.chat.id, message.chat.first_name, message.chat.last_name, message.chat.username,
            message.text
        )
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.start_if_reg_anybody,
        )
        await post_problem_keyboard(message.chat.id, user)
    else:
        raise ValueError(f'Wrong {REG_MODE=}')


@reg_state(STATE.GET_USER_INFO)
async def prc_get_user_info_state(message: types.Message, user: User):
    logger.debug('prc_get_user_info_state')
    user = User.get_by_token(message.text)
    db.log.log_signon(
        user and user.id, message.chat.id, message.chat.first_name, message.chat.last_name, message.chat.username,
        message.text
    )
    if user is None:
        await start(message)
        return
    elif user.type == USER_TYPE.DELETED:
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.this_password_is_blocked,
        )
    else:
        User.set_chat_id(user, message.chat.id)
        if user.type == USER_TYPE.STUDENT:
            State.set_by_user_id(user.id, STATE.GET_TASK_INFO)
        elif user.type == USER_TYPE.TEACHER:
            State.set_by_user_id(user.id, STATE.TEACHER_SELECT_ACTION)
        elif user.type == USER_TYPE.DEACTIVATED_STUDENT:
            State.set_by_user_id(user.id, STATE.USER_IS_NOT_ACTIVATED)
        await bot.send_message(
            chat_id=message.chat.id,
            text=msgs.welcome_user.format_map({'user': user}),
        )
        await asyncio.sleep(1)
        await process_regular_message(message)


@reg_state(STATE.USER_IS_NOT_ACTIVATED)
async def prc_user_is_not_activated_state(message: types.Message, user: User):
    logger.debug('prc_user_is_not_activated_state')
    await bot.send_message(
        chat_id=message.chat.id,
        text=msgs.user_is_not_activated,
    )


async def prc_WTF(message: types.Message, user: User):
    logger.debug('prc_WTF')
    await bot.send_message(
        chat_id=message.chat.id,
        text=msgs.bot_internal_error,
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
                await bot.edit_message_reply_markup_ig(
                    chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=None
                )
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
        alarm = msgs.error_only_compressed_images
    elif not message.text and not message.photo:
        alarm = msgs.error_only_images_and_texts
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
        await bot.send_message(chat_id=message.chat.id, text=msgs.you_are_in_online_mode_now, )
        user.set_online_mode(ONLINE_MODE.ONLINE)
    else:
        await start(message)


@dispatcher.message_handler(commands=['in_school', 'inschool', 'school'])
async def mode_school(message: types.Message):
    logger.debug('mode_school')
    user = User.get_by_chat_id(message.chat.id)
    if user:
        await bot.send_message(chat_id=message.chat.id, text=msgs.you_are_in_offline_mode_now, )
        user.set_online_mode(ONLINE_MODE.SCHOOL)
    else:
        await start(message)

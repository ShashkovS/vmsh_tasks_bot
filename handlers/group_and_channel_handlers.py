import asyncio
import re
from aiogram.dispatcher.webhook import types
from aiogram.dispatcher.filters import ChatTypeFilter, RegexpCommandsFilter
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToForwardNotFound

import db_methods as db
from helpers.bot import bot, dispatcher
from helpers.config import logger, config
from helpers.consts import ONLINE_MODE
from helpers.msg_texts import msgs

from models import User

URL_REGEX = re.compile(r'\s*(https?:\/\/)?([\w\.]+)\.([a-zрф]{2,6}\.?)(\/[\w\.]*)*\/?\s*')
MAT_REGEX = re.compile(
    r"""(?iu)\b(?:(?:[уyu]|[нзnz3][аa]|(?:хитро|не)?[вvwb][зz3]?[ыьъi]|[сsc][ьъ']|(?:и|[рpr][аa4])[зсzs]ъ?|(?:[оo0][тбtb6]|[пp][оo0][дd9])[ьъ']?|(?:.\B)+?[оаеиeo])?-?(?:[еёe][бb6](?!о[рй])|и[пб][ае][тц]).*?|(?:[нn][иеаaie]|(?:[дпdp]|[вv][еe3][рpr][тt])[оo0]|[рpr][аa][зсzc3]|[з3z]?[аa]|с(?:ме)?|[оo0](?:[тt]|дно)?|апч)?-?[хxh][уuy](?:[яйиеёюuie]|ли(?!ган)).*?|(?:[вvw][зы3z]|(?:три|два|четыре)жды|(?:н|[сc][уuy][кk])[аa])?-?[бb6][лl](?:[яy](?!(?:х|ш[кн]|мб)[ауеыио]).*?|[еэe][дтdt][ь']?)|(?:[рp][аa][сзc3z]|[знzn][аa]|[соsc]|[вv][ыi]?|[пp](?:[еe][рpr][еe]|[рrp][оиioеe]|[оo0][дd])|и[зс]ъ?|[аоao][тt])?[пpn][иеёieu][зz3][дd9].*?|(?:[зz3][аa])?[пp][иеieu][дd][аоеaoe]?[рrp](?:ну.*?|[оаoa][мm]|(?:[аa][сcs])?(?:[иiu](?:[лl][иiu])?[нщктлtlsn]ь?)?|(?:[оo](?:ч[еиei])?|[аa][сcs])?[кk](?:[оo]й)?|[юu][гg])[ауеыauyei]?|[мm][аa][нnh][дd](?:[ауеыayueiи](?:[лl](?:[иi][сзc3щ])?[ауеыauyei])?|[оo][йi]|[аоao][вvwb][оo](?:ш|sh)[ь']?(?:[e]?[кk][ауеayue])?|юк(?:ов|[ауи])?)|[мm][уuy][дd6](?:[яyаиоaiuo0].*?|[еe]?[нhn](?:[ьюия'uiya]|ей))|мля(?:[тд]ь)?|лять|(?:[нз]а|по)х|м[ао]л[ао]фь(?:[яию]|[её]й))\b""")
OK_URL_REGEX = re.compile(r't\.me\/vmsh')
BOT_URL = re.compile(r'(?:(?<=t\.me/)|(?<=@))\w+bot\b', flags=re.IGNORECASE)
SOME_TYPICAL_SPAM = re.compile(msgs.a_spam_regex, flags=re.IGNORECASE)


def check_sos_channel(message: types.Message):
    return message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel


@dispatcher.channel_post_handler(check_sos_channel, content_types=types.ContentType.ANY)
@dispatcher.channel_post_handler(check_sos_channel, RegexpCommandsFilter(regexp_commands=['.*']))
@dispatcher.message_handler(check_sos_channel, content_types=types.ContentType.ANY)
@dispatcher.message_handler(check_sos_channel, RegexpCommandsFilter(regexp_commands=['.*']))
async def prc_sos_reply(message: types.Message):
    logger.debug('prc_sos_reply')
    # Ботов нафиг
    if message.from_user and message.from_user.is_bot:
        return
    # Только ответы
    if not message.reply_to_message:
        return
    question_record = db.question.get_message_by_sos(message.chat.id, message.reply_to_message.message_id)
    if not question_record:
        await bot.send_message(chat_id=message.chat.id, text=msgs.a_reply_only_to_forwarded)
        return
    try:
        await bot.send_message(question_record['chat_id'], text=msgs.here_is_your_answer, reply_to_message_id=question_record['question_msg_id'])
        await bot.copy_message(question_record['chat_id'], message.chat.id, message.message_id)
        student = User.get_by_chat_id(question_record['chat_id'])
        if student:
            new_text = f'✅✅✅✅\n<code>{student.surname}</code> <code>{student.name}</code>\n<code>{student.level}</code> <code>{student.token}</code> {ONLINE_MODE(student.online).__str__()[12:]}'
            await bot.edit_message_text_ig(chat_id=question_record['sos_chat_id'], message_id=question_record['sos_header_msg_id'], text=new_text,
                                           parse_mode="HTML")
        await bot.send_message(chat_id=message.chat.id, text=msgs.a_forwarded_ok)
        db.question.mark_as_answered(message.chat.id, message.reply_to_message.message_id, message.text)
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=msgs.a_forward_failed)
        logger.exception(f'SHIT: {e}')


@dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), content_types=types.ContentType.ANY)
@dispatcher.message_handler(ChatTypeFilter(types.ChatType.GROUP), content_types=types.ContentType.ANY)
@dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), RegexpCommandsFilter(regexp_commands=['.*']))
@dispatcher.message_handler(ChatTypeFilter(types.ChatType.GROUP), RegexpCommandsFilter(regexp_commands=['.*']))
async def group_message_handler(message: types.Message):
    # Если сообщение от админа, то игнорируем его
    if message.from_user.username == 'GroupAnonymousBot':
        return
    # Сообщения про новеньких и удалившихся удаляем
    elif message.new_chat_members or message.left_chat_member:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            logger.exception(f'SHIT: {e}')
        return

    text = ''
    try:
        text = message.text or ''
    except:
        pass
    html_text = ''
    try:
        html_text = message.html_text or ''
    except:
        pass
    has_buttons = False
    try:
        has_buttons = message.reply_markup and message.reply_markup.inline_keyboard
        print(f'{has_buttons=}')
    except:
        pass

    # Кто-то пишет команду в группе, а не в боте
    if text and re.match(r'^\s*/[a-z_]{2,}', text):
        try:
            reply_msg = await bot.send_message(message.chat.id, text=msgs.this_message_is_for_bot.format_map({'username': bot.username}),
                                               reply_to_message_id=message.message_id)
            bot.delete_messages_after([message, reply_msg], timeout=10)
        except Exception as e:
            logger.error(e)
    elif text or html_text or has_buttons:
        user_sign = (message.from_user.first_name or '') + ' ' + (message.from_user.last_name or '') + ' ' + (message.from_user.username or '')
        too_short_user_sign = len(user_sign) <= 5
        text_to_check = (text or '') + ' ' + (html_text or '') + ' ' + user_sign
        # Ссылка без комментариев — это спам. Пересылаем её в exception и удаляем
        message_is_url_only = URL_REGEX.fullmatch(text or html_text) and not OK_URL_REGEX.search(text_to_check)
        mat_detected = MAT_REGEX.search(text_to_check) or SOME_TYPICAL_SPAM.search(text_to_check)
        all_urls = BOT_URL.findall(text_to_check)
        bad_urls = any(
            url.endswith('bot') and not url.startswith('vmsh')
            for url in all_urls
        )
        from_bad_bot_message = message.from_user.is_bot and ('vmsh' not in message.from_user.username and message.from_user.id != bot.id)
        if message_is_url_only or mat_detected or bad_urls or from_bad_bot_message or too_short_user_sign:
            try:
                await bot.forward_message(config.exceptions_channel, message.chat.id, message.message_id)
            except MessageToForwardNotFound:
                pass
            # Удаляем сообщение
            try:
                await bot.delete_message(message.chat.id, message.message_id)
            except MessageCantBeDeleted:
                await bot.send_message(config.exceptions_channel, msgs.a_moderate_could_not_delete)
            except Exception as e:
                logger.exception(f'SHIT: {e}')
                await bot.send_message(config.exceptions_channel, msgs.a_moderate_could_not_delete)
        if mat_detected or from_bad_bot_message:
            # Баним пользователя
            try:
                await bot.ban_chat_member(message.chat.id, message.from_user.id, revoke_messages=True)
                await bot.send_message(config.exceptions_channel, msgs.a_moderate_banned.format_map({'message': message}))
            except Exception as e:
                logger.exception(f'SHIT: {e}')
                await bot.send_message(config.exceptions_channel, msgs.a_moderate_could_not_ban)

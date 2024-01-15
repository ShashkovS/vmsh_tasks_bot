import asyncio
import re
from aiogram.dispatcher.webhook import types
from aiogram.dispatcher.filters import ChatTypeFilter, RegexpCommandsFilter
from aiogram.utils.exceptions import MessageCantBeDeleted

import db_methods as db
from helpers.bot import bot, dispatcher
from helpers.config import logger, config
from helpers.consts import ONLINE_MODE
from models import User

URL_REGEX = re.compile(r'\s*(https?:\/\/)?([\w\.]+)\.([a-zрф]{2,6}\.?)(\/[\w\.]*)*\/?\s*')
MAT_REGEX = re.compile(
    r"""(?iu)\b(?:(?:[уyu]|[нзnz3][аa]|(?:хитро|не)?[вvwb][зz3]?[ыьъi]|[сsc][ьъ']|(?:и|[рpr][аa4])[зсzs]ъ?|(?:[оo0][тбtb6]|[пp][оo0][дd9])[ьъ']?|(?:.\B)+?[оаеиeo])?-?(?:[еёe][бb6](?!о[рй])|и[пб][ае][тц]).*?|(?:[нn][иеаaie]|(?:[дпdp]|[вv][еe3][рpr][тt])[оo0]|[рpr][аa][зсzc3]|[з3z]?[аa]|с(?:ме)?|[оo0](?:[тt]|дно)?|апч)?-?[хxh][уuy](?:[яйиеёюuie]|ли(?!ган)).*?|(?:[вvw][зы3z]|(?:три|два|четыре)жды|(?:н|[сc][уuy][кk])[аa])?-?[бb6][лl](?:[яy](?!(?:х|ш[кн]|мб)[ауеыио]).*?|[еэe][дтdt][ь']?)|(?:[рp][аa][сзc3z]|[знzn][аa]|[соsc]|[вv][ыi]?|[пp](?:[еe][рpr][еe]|[рrp][оиioеe]|[оo0][дd])|и[зс]ъ?|[аоao][тt])?[пpn][иеёieu][зz3][дd9].*?|(?:[зz3][аa])?[пp][иеieu][дd][аоеaoe]?[рrp](?:ну.*?|[оаoa][мm]|(?:[аa][сcs])?(?:[иiu](?:[лl][иiu])?[нщктлtlsn]ь?)?|(?:[оo](?:ч[еиei])?|[аa][сcs])?[кk](?:[оo]й)?|[юu][гg])[ауеыauyei]?|[мm][аa][нnh][дd](?:[ауеыayueiи](?:[лl](?:[иi][сзc3щ])?[ауеыauyei])?|[оo][йi]|[аоao][вvwb][оo](?:ш|sh)[ь']?(?:[e]?[кk][ауеayue])?|юк(?:ов|[ауи])?)|[мm][уuy][дd6](?:[яyаиоaiuo0].*?|[еe]?[нhn](?:[ьюия'uiya]|ей))|мля(?:[тд]ь)?|лять|(?:[нз]а|по)х|м[ао]л[ао]фь(?:[яию]|[её]й))\b""")
OK_URL_REGEX = re.compile(r't\.me\/vmsh')



@dispatcher.channel_post_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel,
                                 content_types=types.ContentType.ANY)
@dispatcher.channel_post_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel,
                                 RegexpCommandsFilter(regexp_commands=['.*']))
@dispatcher.message_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel,
                                 content_types=types.ContentType.ANY)
@dispatcher.message_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel,
                                 RegexpCommandsFilter(regexp_commands=['.*']))
async def prc_sos_reply(message: types.Message):
    logger.debug('prc_sos_reply')
    # Ботов нафиг
    if message.from_user.is_bot:
        return
    # Только ответы
    if not message.reply_to_message:
        return
    question_record = db.question.get_message_by_sos(message.chat.id, message.reply_to_message.message_id)
    if not question_record:
        await bot.send_message(chat_id=message.chat.id, text='Отвечайте на пересланные сообщения с вопросом')
        return
    try:
        await bot.send_message(question_record['chat_id'], text='Вот ответ на этот вопрос:', reply_to_message_id=question_record['question_msg_id'])
        await bot.copy_message(question_record['chat_id'], message.chat.id, message.message_id)
        student = User.get_by_chat_id(question_record['chat_id'])
        if student:
            new_text = f'✅✅✅✅\n<code>{student.surname}</code> <code>{student.name}</code>\n<code>{student.level}</code> <code>{student.token}</code> {ONLINE_MODE(student.online).__str__()[12:]}'
            await bot.edit_message_text(chat_id=question_record['sos_chat_id'], message_id=question_record['sos_header_msg_id'], text=new_text,
                                        parse_mode="HTML")
        await bot.send_message(chat_id=message.chat.id, text='Переслал.')
        db.question.mark_as_answered(message.chat.id, message.reply_to_message.message_id, message.text)
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text='Не получилось послать ответ. Попробуйте указать токен первым словом или ответить вручную.')
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
    # Кто-то пишет команду в группе, а не в боте
    elif message.text and re.match(r'^\s*/[a-z_]{2,}', message.text):
        reply_msg = await bot.send_message(message.chat.id, text=f'Кажется, это сообщение лично для меня. Заходите: @{bot.username}',
                                           reply_to_message_id=message.message_id)
        bot.delete_messages_after([message, reply_msg], timeout=10)
    # Ссылка без комментариев — это спам. Пересылаем её в exception и удаляем
    elif message.text:
        message_is_url_only = URL_REGEX.fullmatch(message.text) and not OK_URL_REGEX.search(message.text)
        mat_detected = MAT_REGEX.search(message.text)
        if message_is_url_only or mat_detected:
            await bot.forward_message(config.exceptions_channel, message.chat.id, message.message_id)
            # Удаляем сообщение
            try:
                await bot.delete_message(message.chat.id, message.message_id)
            except MessageCantBeDeleted:
                await bot.send_message(config.exceptions_channel, 'Сообщение выше удалить не удалось :(')
            except Exception as e:
                logger.exception(f'SHIT: {e}')
                await bot.send_message(config.exceptions_channel, 'Сообщение выше удалить не удалось :(')
        if mat_detected:
            # Баним пользователя
            try:
                await bot.ban_chat_member(message.chat.id, message.from_user.id, revoke_messages=True)
                await bot.send_message(config.exceptions_channel, f'Пользователь {message.from_user!r} забанен')
            except Exception as e:
                logger.exception(f'SHIT: {e}')
                await bot.send_message(config.exceptions_channel, 'Юзера выше не удалось забанить :(')

import asyncio
import re
from aiogram.dispatcher.webhook import types
from aiogram.dispatcher.filters import ChatTypeFilter, RegexpCommandsFilter
from aiogram.utils.exceptions import MessageCantBeDeleted

from helpers.bot import bot, dispatcher
from helpers.config import logger, config
from models import User

# URL_REGEX = re.compile(r'\s*(https?:\/\/)?([\w\.]+)\.([a-zрф]{2,6}\.?)(\/[\w\.]*)*\/?\s*')
# MAT_REGEX = re.compile(r"""(?iu)\b(?:(?:[уyu]|[нзnz3][аa]|(?:хитро|не)?[вvwb][зz3]?[ыьъi]|[сsc][ьъ']|(?:и|[рpr][аa4])[зсzs]ъ?|(?:[оo0][тбtb6]|[пp][оo0][дd9])[ьъ']?|(?:.\B)+?[оаеиeo])?-?(?:[еёe][бb6](?!о[рй])|и[пб][ае][тц]).*?|(?:[нn][иеаaie]|(?:[дпdp]|[вv][еe3][рpr][тt])[оo0]|[рpr][аa][зсzc3]|[з3z]?[аa]|с(?:ме)?|[оo0](?:[тt]|дно)?|апч)?-?[хxh][уuy](?:[яйиеёюuie]|ли(?!ган)).*?|(?:[вvw][зы3z]|(?:три|два|четыре)жды|(?:н|[сc][уuy][кk])[аa])?-?[бb6][лl](?:[яy](?!(?:х|ш[кн]|мб)[ауеыио]).*?|[еэe][дтdt][ь']?)|(?:[рp][аa][сзc3z]|[знzn][аa]|[соsc]|[вv][ыi]?|[пp](?:[еe][рpr][еe]|[рrp][оиioеe]|[оo0][дd])|и[зс]ъ?|[аоao][тt])?[пpn][иеёieu][зz3][дd9].*?|(?:[зz3][аa])?[пp][иеieu][дd][аоеaoe]?[рrp](?:ну.*?|[оаoa][мm]|(?:[аa][сcs])?(?:[иiu](?:[лl][иiu])?[нщктлtlsn]ь?)?|(?:[оo](?:ч[еиei])?|[аa][сcs])?[кk](?:[оo]й)?|[юu][гg])[ауеыauyei]?|[мm][аa][нnh][дd](?:[ауеыayueiи](?:[лl](?:[иi][сзc3щ])?[ауеыauyei])?|[оo][йi]|[аоao][вvwb][оo](?:ш|sh)[ь']?(?:[e]?[кk][ауеayue])?|юк(?:ов|[ауи])?)|[мm][уuy][дd6](?:[яyаиоaiuo0].*?|[еe]?[нhn](?:[ьюия'uiya]|ей))|мля(?:[тд]ь)?|лять|(?:[нз]а|по)х|м[ао]л[ао]фь(?:[яию]|[её]й))\b""")
# OK_URL_REGEX = re.compile(r't\.me\/vmsh')
#
#
#
# @dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), content_types=types.ContentType.ANY)
# @dispatcher.message_handler(ChatTypeFilter(types.ChatType.GROUP), content_types=types.ContentType.ANY)
# @dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), RegexpCommandsFilter(regexp_commands=['.*']))
# @dispatcher.message_handler(ChatTypeFilter(types.ChatType.GROUP), RegexpCommandsFilter(regexp_commands=['.*']))
# async def group_message_handler(message: types.Message):
#     # Если сообщение от админа, то игнорируем его
#     if message.from_user.username == 'GroupAnonymousBot':
#         return
#     # Сообщения про новеньких и удалившихся удаляем
#     elif message.new_chat_members or message.left_chat_member:
#         try:
#             await bot.delete_message(message.chat.id, message.message_id)
#         except Exception as e:
#             logger.exception(f'SHIT: {e}')
#     # Кто-то пишет команду в группе, а не в боте
#     elif message.text and re.match(r'^\s*/[a-z_]{2,}', message.text):
#         reply_msg = await bot.send_message(message.chat.id, text=f'Кажется, это сообщение лично для меня. Заходите: @{bot.username}',
#                                reply_to_message_id=message.message_id)
#         bot.delete_messages_after([message, reply_msg], timeout=10)
#     # Ссылка без комментариев — это спам. Пересылаем её в exception и удаляем
#     elif message.text:
#         message_is_url_only = URL_REGEX.fullmatch(message.text) and not OK_URL_REGEX.search(message.text)
#         mat_detected = MAT_REGEX.search(message.text)
#         if message_is_url_only or mat_detected:
#             await bot.forward_message(config.exceptions_channel, message.chat.id, message.message_id)
#             # Удаляем сообщение
#             try:
#                 await bot.delete_message(message.chat.id, message.message_id)
#             except MessageCantBeDeleted:
#                 await bot.send_message(config.exceptions_channel, 'Сообщение выше удалить не удалось :(')
#             except Exception as e:
#                 logger.exception(f'SHIT: {e}')
#                 await bot.send_message(config.exceptions_channel, 'Сообщение выше удалить не удалось :(')
#         if mat_detected:
#             # Баним пользователя
#             try:
#                 await bot.ban_chat_member(message.chat.id, message.from_user.id, revoke_messages=True)
#                 await bot.send_message(config.exceptions_channel, f'Пользователь {message.from_user!r} забанен')
#             except Exception as e:
#                 logger.exception(f'SHIT: {e}')
#                 await bot.send_message(config.exceptions_channel, 'Юзера выше не удалось забанить :(')
#
#
#
# @dispatcher.channel_post_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel)
# async def prc_sos_reply(message: types.Message):
#     logger.debug('prc_sos_reply')
#     # Сначала проверим, может пароль явно указан в сообщении?
#     student = None
#     if message.text and (match := re.match(r'^[a-z0-9]{6,12}\b', message.text, flags=re.DOTALL)):
#         token = match.group()
#         student = User.get_by_token(token)
#     # Обрабатываем только ответы из sos-чата (если токен явно не указан)
#     if not student and not message.reply_to_message:
#         # Отправляем сообщение только на продакшене (чтобы боты друг с другом не спорили)
#         # if config.production_mode:
#             try:
#                 await bot.send_message(chat_id=message.chat.id, text='Выбирайте в меню «Ответить», чтобы сразу пересылать сообщение')
#             except Exception as e:
#                 logger.exception(f'SHIT: {e}')
#     else:
#         to_chat_id = (student and student.chat_id) or (message.reply_to_message.forward_from and message.reply_to_message.forward_from.id)
#         try:
#             await bot.send_message(to_chat_id, text='Ответ на вопрос: «' + (message.reply_to_message.text or '').strip() + '»')
#             await bot.copy_message(to_chat_id, message.chat.id, message.message_id)
#             await bot.send_message(chat_id=message.chat.id, text='Переслал.')
#         except Exception as e:
#             await bot.send_message(chat_id=message.chat.id, text='Не получилось послать ответ. Попробуйте указать токен первым словом или ответить вручную.')
#             logger.exception(f'SHIT: {e}')

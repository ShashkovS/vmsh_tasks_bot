import re
from aiogram.dispatcher.webhook import types
from aiogram.dispatcher.filters import ChatTypeFilter, RegexpCommandsFilter

from helpers.bot import bot, dispatcher
from helpers.config import logger, config
from helpers.obj_classes import User

URL_REGEX = re.compile(r'\s*(https?:\/\/)?([\w\.]+)\.([a-zрф]{2,6}\.?)(\/[\w\.]*)*\/?\s*')


@dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), content_types=types.ContentType.ANY)
@dispatcher.message_handler(ChatTypeFilter(types.ChatType.SUPERGROUP), RegexpCommandsFilter(regexp_commands=['.*']))
async def group_message_handler(message: types.Message):
    # Если сообщение от админа, то игнорируем его
    if message.from_user.username == 'GroupAnonymousBot':
        return
    # Кто-то пишет команду в группе, а не в боте
    if message.text and re.match(r'^\s*/[a-z_]{2,}', message.text):
        await bot.send_message(message.chat.id, text=f'Кажется, это сообщение лично для меня. Заходите: @{bot.username}',
                               reply_to_message_id=message.message_id)
    # Ссылка без комментариев — это спам. Пересылаем её в exception и удаляем
    elif message.text and URL_REGEX.fullmatch(message.text):
        await bot.forward_message(config.exceptions_channel, message.chat.id, message.message_id)
        await bot.delete_message(message.chat.id, message.message_id)


@dispatcher.channel_post_handler(lambda message: message.chat.id == config.sos_channel or '@' + str(message.chat.username) == config.sos_channel)
async def prc_sos_reply(message: types.Message):
    logger.debug('prc_sos_reply')
    # Сначала проверим, может пароль явно указан в сообщении?
    student = None
    if message.text and (match := re.match(r'^[a-z0-9]{6,12}\b', message.text, flags=re.DOTALL)):
        token = match.group()
        student = User.get_by_token(token)
    # Обрабатываем только ответы из sos-чата (если токен явно не указан)
    if not student and not message.reply_to_message:
        # Отправляем сообщение только на продакшене (чтобы боты друг с другом не спорили)
        if config.production_mode:
            try:
                await bot.send_message(chat_id=message.chat.id, text='Выбирайте в меню «Ответить», чтобы сразу пересылать сообщение')
            except Exception as e:
                logger.exception(f'SHIT: {e}')
    else:
        to_chat_id = (student and student.chat_id) or (message.reply_to_message.forward_from and message.reply_to_message.forward_from.id)
        try:
            await bot.send_message(to_chat_id, text='Ответ на вопрос: «' + (message.reply_to_message.text or '').strip() + '»')
            await bot.copy_message(to_chat_id, message.chat.id, message.message_id)
            await bot.send_message(chat_id=message.chat.id, text='Переслал.')
        except Exception as e:
            await bot.send_message(chat_id=message.chat.id, text='Не получилось послать ответ. Попробуйте указать токен первым словом или ответить вручную.')
            logger.exception(f'SHIT: {e}')

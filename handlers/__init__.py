# -*- coding: utf-8 -*-
from .group_and_channel_handlers import *
from .main_handlers import *
from .student_handlers import *
from .teacher_handlers import *
from .admin_handlers import *

from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.types import ChatType, ContentType

# Важно, что последний хендлер. Обрабатываем только private-сообщения
dispatcher.register_message_handler(process_regular_message, ChatTypeFilter(ChatType.PRIVATE), content_types=ContentType.ANY)

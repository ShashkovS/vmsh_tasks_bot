# -*- coding: utf-8 -*-
from .group_and_channel_handlers import *
from .main_handlers import *
from .student_handlers import *
from .teacher_handlers import *
from .common_handlers import *
from .admin_handlers import *

from aiogram.enums import ChatType
from aiogram.filters import ChatTypeFilter
from helpers.bot import router

# Важно, что последний хендлер. Обрабатываем только private-сообщения
router.message.register(process_regular_message, ChatTypeFilter(ChatType.PRIVATE))

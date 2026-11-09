# -*- coding: utf-8 -*-
from .group_and_channel_handlers import *
from .pwa_news_handlers import *
from .main_handlers import *
from .student_handlers import *
from .teacher_handlers import *
from .common_handlers import *
from .admin_handlers import *

from aiogram import F
from aiogram.enums import ChatType
from helpers.bot import router

# Важно, что последний хендлер. Обрабатываем только private-сообщения
router.message.register(process_regular_message, F.chat.type == ChatType.PRIVATE)

# -*- coding: utf-8 -*-
from .main_handlers import *
from .student_handlers import *
from .teacher_handlers import *
from .admin_handlers import *

# Важно, что последний
dispatcher.register_message_handler(process_regular_message, content_types=["any"])

"""
Это — заготовка для теста.
Она пока ничего не тестирует.
"""

import os
from unittest import TestCase, IsolatedAsyncioTestCase
import logging


from helpers import consts
from helpers.obj_classes import *

from .initial_test_data import test_students, test_teachers
from .dataset import *
from helpers.bot import bot
from handlers import main_handlers

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-8s: %(levelname)-8s %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
logging.getLogger('aiogram').setLevel(logging.DEBUG)


class UserMethodsTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = db
        test_db_filename = 'db/unittest.db'
        # ensure there is no trash file from previous incorrectly handled tests present
        try:
            os.unlink(test_db_filename)
        except FileNotFoundError:
            pass
        # create shiny new db instance from scratch and connect
        self.db.setup(test_db_filename)
        self.insert_dummy_users()
        # fake telegram
        # self._bot = Bot(TOKEN, parse_mode=types.ParseMode.MARKDOWN_V2)


    def insert_dummy_users(self):
        for row in test_students + test_teachers:
            real_id = self.db.add_user(row)
            row['id'] = real_id

    def tearDown(self) -> None:
        self.db.disconnect()
        os.unlink(self.db.db_file)

    async def test_something(self):
        MESSAGE = {
            "message_id": 11223,
            "from": USER,
            "chat": CHAT,
            "date": 1508709711,
            "text": "/start",
        }
        msg = types.Message(**MESSAGE)

        async with FakeTelegram(message_data=MESSAGE):
            await main_handlers.start(msg)
        # print(msg)
        # print(_message)
        # print(MESSAGE)
        # a = 1/0

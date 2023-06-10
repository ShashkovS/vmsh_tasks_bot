import os
from dataclasses import asdict
from unittest import TestCase

from helpers.consts import *
import db_methods as db
from models import *

from .initial_test_data import test_students, test_teachers


class UserMethodsTest(TestCase):
    def setUp(self) -> None:
        self.db = db
        test_db_filename = 'db/unittest.db'
        # ensure there is no trash file from previous incorrectly handled tests present
        try:
            os.unlink(test_db_filename)
        except FileNotFoundError:
            pass
        # create shiny new db instance from scratch and connect
        self.db.sql.setup(test_db_filename)
        self.insert_dummy_users()

    def insert_dummy_users(self):
        for row in test_students + test_teachers:
            real_id = self.db.user.insert(row)
            row['id'] = real_id

    def tearDown(self) -> None:
        self.db.sql.disconnect()
        os.unlink(self.db.sql.db_file)

    def test_all_getters(self):
        """ Test this methods:
        def all(cls) -> Generator[User, None, None]:
        def all_students(cls) -> Generator[User, None, None]:
        def all_teachers(cls) -> Generator[User, None, None]:
        """
        students = list(User.all_students())
        teachers = list(User.all_teachers())
        all_users = list(User.all())
        self.assertEqual(len(students), len(test_students))
        self.assertEqual(len(teachers), len(test_teachers))
        self.assertEqual(len(all_users), len(students) + len(teachers))
        self.assertListEqual([asdict(user) for user in students], test_students)
        self.assertListEqual([asdict(user) for user in teachers], test_teachers)
        self.assertListEqual([asdict(user) for user in all_users], test_students + test_teachers)

    def test_by_getters(self):
        """ Test this methods:
        def get_by_chat_id(cls, chat_id: int) -> Optional[User]:
        def get_by_token(cls, token: str) -> Optional[User]:
        def get_by_id(cls, id: int) -> Optional[User]:
        """
        for dict_user in test_students + test_teachers:
            dict_user['level'] = LEVEL(dict_user['level'] or 'н')
            dict_user['online'] = ONLINE_MODE(dict_user['online'])
            dict_user['type'] = USER_TYPE(dict_user['type'])
            self.assertDictEqual(dict_user, asdict(User.get_by_id(dict_user['id'])))
            self.assertDictEqual(dict_user, asdict(User.get_by_token(dict_user['token'])))
            if dict_user['chat_id']:
                self.assertDictEqual(dict_user, asdict(User.get_by_chat_id(dict_user['chat_id'])))

    def test_set_level(self):
        for dict_user in test_students + test_teachers:
            user = User.get_by_id(dict_user['id'])
            new_level = LEVEL.NOVICE
            user.set_level(new_level)
            user = User.get_by_id(dict_user['id'])
            self.assertEqual(user.level, new_level)

    def test_set_chat_id(self):
        prev_user_id = None
        for dict_user in test_students + test_teachers:
            user = User.get_by_id(dict_user['id'])
            new_chat_id = 99999
            user.set_chat_id(new_chat_id)
            user = User.get_by_id(dict_user['id'])
            self.assertEqual(user.chat_id, new_chat_id)
            if prev_user_id:
                self.assertIsNone(User.get_by_id(prev_user_id).chat_id)
            prev_user_id = dict_user['id']

    def test_webtokens(self):
        student1 = User.get_by_token(test_students[-1]['token'])
        student2 = User.get_by_token(test_students[0]['token'])
        self.assertIsNone(Webtoken.user_by_webtoken('trash'))
        webtoken1 = Webtoken.webtoken_by_user(student1)
        self.assertIsNone(Webtoken.user_by_webtoken('trash'))
        self.assertEqual(Webtoken.user_by_webtoken(webtoken1), student1)
        self.assertEqual(Webtoken.webtoken_by_user(student1), webtoken1)
        webtoken2 = Webtoken.webtoken_by_user(student2)
        self.assertIsNone(Webtoken.user_by_webtoken('trash'))
        self.assertEqual(Webtoken.user_by_webtoken(webtoken2), student2)
        self.assertEqual(Webtoken.webtoken_by_user(student2), webtoken2)
        self.assertIsNone(Webtoken.user_by_webtoken(None))
        self.assertIsNone(Webtoken.webtoken_by_user(None))

    def test_problem_lock(self):
        pass

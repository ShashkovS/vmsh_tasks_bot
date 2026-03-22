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
        expected_students = self._with_enums(test_students)
        expected_teachers = self._with_enums(test_teachers)
        self.assertEqual(len(students), len(test_students))
        self.assertEqual(len(teachers), len(test_teachers))
        self.assertEqual(len(all_users), len(students) + len(teachers))
        self.assertListEqual([self._public_user_dict(user) for user in students], expected_students)
        self.assertListEqual([self._public_user_dict(user) for user in teachers], expected_teachers)
        self.assertListEqual([self._public_user_dict(user) for user in all_users], expected_students + expected_teachers)

    def test_by_getters(self):
        """ Test this methods:
        def get_by_chat_id(cls, chat_id: int) -> Optional[User]:
        def get_by_token(cls, token: str) -> Optional[User]:
        def get_by_id(cls, id: int) -> Optional[User]:
        """
        for dict_user in test_students + test_teachers:
            expected = dict(dict_user)
            expected['online'] = ONLINE_MODE(expected['online'])
            expected['type'] = USER_TYPE(expected['type'])
            self.assertDictEqual(expected, self._public_user_dict(User.get_by_id(expected['id'])))
            self.assertDictEqual(expected, self._public_user_dict(User.get_by_token(expected['token'])))
            if expected['chat_id']:
                self.assertDictEqual(expected, self._public_user_dict(User.get_by_chat_id(expected['chat_id'])))

    @staticmethod
    def _with_enums(rows):
        normalized = []
        for row in rows:
            item = dict(row)
            item['type'] = USER_TYPE(item['type'])
            item['online'] = ONLINE_MODE(item['online'])
            normalized.append(item)
        return normalized

    @staticmethod
    def _public_user_dict(user):
        item = asdict(user)
        item.pop('allowed_groups_set', None)
        item.pop('_cached_group', None)
        return item

    def test_set_group_id(self):
        for dict_user in test_students + test_teachers:
            user = User.get_by_id(dict_user['id'])
            new_group_id = 'н'
            user.set_group_id(new_group_id)
            user = User.get_by_id(dict_user['id'])
            self.assertEqual(user.group_id, new_group_id)

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

    def test_group_model_and_accessors(self):
        group = Group.get_by_id('н')
        self.assertIsNotNone(group)
        self.assertEqual(group.group_id, 'н')
        short_code_groups = Group.get_by_short_code('н')
        self.assertTrue(any(item.group_id == 'н' for item in short_code_groups))
        student = User.get_by_id(test_students[0]['id'])
        self.assertEqual(student.group_id, 'н')
        self.assertEqual(student.group.group_id, 'н')
        self.assertEqual(student.allowed_groups_set, set())
        self.assertTrue(student.can_access_group('н'))
        self.assertFalse(student.can_access_group('п'))
        student.set_allowed_groups(';н;п;')
        self.assertEqual(student.allowed_groups_set, {'н', 'п'})
        self.assertTrue(student.can_access_group('п'))
        allowed_student = User.get_by_id(test_students[1]['id'])
        self.assertEqual(allowed_student.allowed_groups_set, {'п', 'э'})
        self.assertTrue(allowed_student.can_access_group('п'))
        self.assertTrue(allowed_student.can_access_group('э'))
        self.assertFalse(allowed_student.can_access_group('н'))

    def test_problem_ref_resolution(self):
        Problem(
            group_id='н',
            lesson=4,
            prob=4,
            item='',
            title='Base key problem',
            prob_text='',
            prob_type=PROB_TYPE.TEST,
            ans_type=ANS_TYPE.NATURAL,
            ans_validation='',
            validation_error='',
            cor_ans='1',
            cor_ans_checker='',
            wrong_ans='',
            congrat='',
        )

        # explicit group_id reference
        problem, err = Problem.resolve_problem_ref('н:4.4', allowed_group_ids={'н'})
        self.assertIsNone(err)
        self.assertIsNotNone(problem)
        self.assertEqual(problem.group_id, 'н')

        # duplicate short_code -> ambiguity
        db.group.insert({
            'group_id': 'н_dup',
            'short_code': 'н',
            'broadcast_code': 'all_n_dup',
            'tg_command': '/switch_n_dup',
            'public_name': 'Novice duplicate',
            'conditions_url': None,
            'tasks_header_template': None,
            'switch_message': None,
            'sort_order': 500,
            'is_active': 1,
            'is_default': 0,
            'allow_self_switch': 1,
            'is_system': 0,
            'score_weight': 1.0,
        })
        Problem(
            group_id='н_dup',
            lesson=4,
            prob=4,
            item='',
            title='Duplicate key problem',
            prob_text='',
            prob_type=PROB_TYPE.TEST,
            ans_type=ANS_TYPE.NATURAL,
            ans_validation='',
            validation_error='',
            cor_ans='1',
            cor_ans_checker='',
            wrong_ans='',
            congrat='',
        )
        _, err = Problem.resolve_problem_ref('4н.4', allowed_group_ids={'н', 'н_dup'})
        self.assertEqual(err, 'ambiguous')

        # explicit reference always resolves this ambiguity
        problem, err = Problem.resolve_problem_ref('н_dup:4.4', allowed_group_ids={'н', 'н_dup'})
        self.assertIsNone(err)
        self.assertEqual(problem.group_id, 'н_dup')

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

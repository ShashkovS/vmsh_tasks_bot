# Для работы по виндой нужны PYTHONUTF8=1
import os
from unittest import TestCase
from datetime import datetime
from random import randint

from helpers.consts import *
from db_methods import db
from .initial_test_data import test_students, test_teachers, test_problems


class DatabaseMethodsTest(TestCase):
    def setUp(self, counter=[0]) -> None:
        self.db = db
        test_db_filename = f'db/unittest_{counter[0]:03}.db'
        counter[0] += 1
        # ensure there is no trash file from previous incorrectly handled tests present
        for file in [test_db_filename, test_db_filename + '-shm', test_db_filename + '-wal']:
            try:
                os.unlink(file)
            except FileNotFoundError:
                pass
        # create shiny new db instance from scratch and connect
        self.db.setup(test_db_filename)
        # Making it blazing fast
        self.db.conn.execute('''      PRAGMA journal_mode = OFF;       ''')
        self.db.conn.execute('''      PRAGMA synchronous = 0;       ''')
        self.db.conn.execute('''      PRAGMA cache_size = 1000000;       ''')
        self.db.conn.execute('''      PRAGMA locking_mode = EXCLUSIVE;       ''')
        self.db.conn.execute('''      PRAGMA temp_store = MEMORY;       ''')
        self.insert_dummy_users()
        self.insert_dummy_problems()

    def insert_dummy_users(self):
        for row in test_students + test_teachers:
            real_id = self.db.add_user(row)
            row['id'] = real_id

    def insert_dummy_problems(self):
        for row in test_problems:
            real_id = self.db.add_problem(row)
            row['id'] = real_id

    def tearDown(self) -> None:
        self.db.disconnect()
        self.db.conn.close()
        try:
            os.unlink(self.db.db_file)
        except PermissionError:
            pass

    def test_users_add_and_fetch_all(self):
        students = self.db.fetch_all_users_by_type(USER_TYPE.STUDENT)
        teachers = self.db.fetch_all_users_by_type(USER_TYPE.TEACHER)
        all_users = self.db.fetch_all_users_by_type()
        self.assertEqual(len(students), len(test_students))
        self.assertEqual(len(teachers), len(test_teachers))
        self.assertEqual(len(all_users), len(students) + len(teachers))
        self.assertListEqual(students, test_students)
        self.assertListEqual(teachers, test_teachers)
        self.assertListEqual(all_users, test_students + test_teachers)

    def test_users_get_by(self):
        student = test_students[-1]
        teacher = test_teachers[-1]
        self.assertDictEqual(self.db.get_user_by_id(student['id']), student)
        self.assertDictEqual(self.db.get_user_by_token(student['token']), student)
        self.assertDictEqual(self.db.get_user_by_chat_id(student['chat_id']), student)
        self.assertDictEqual(self.db.get_user_by_id(teacher['id']), teacher)
        self.assertDictEqual(self.db.get_user_by_token(teacher['token']), teacher)
        self.assertDictEqual(self.db.get_user_by_chat_id(teacher['chat_id']), teacher)
        self.assertIsNone(self.db.get_user_by_id(-1))
        self.assertIsNone(self.db.get_user_by_token('-1'))
        self.assertIsNone(self.db.get_user_by_chat_id(-1))

    def test_user_set_chat_id(self):
        student1 = test_students[-1]
        student2 = test_students[0]
        teacher = test_teachers[-1]
        self.assertDictEqual(student1, self.db.get_user_by_id(student1['id']))
        self.assertDictEqual(student2, self.db.get_user_by_id(student2['id']))
        new_chat_id = 12345
        self.db.set_user_chat_id(student1['id'], new_chat_id)
        self.assertEqual(12345, self.db.get_user_by_id(student1['id'])['chat_id'])
        self.assertEqual(student2['chat_id'], self.db.get_user_by_id(student2['id'])['chat_id'])
        # Тот же юзер заходит под другим паролем
        self.db.set_user_chat_id(student2['id'], new_chat_id)
        self.assertIsNone(self.db.get_user_by_id(student1['id'])['chat_id'])
        self.assertEqual(new_chat_id, self.db.get_user_by_id(student2['id'])['chat_id'])
        # Тот же юзер заходит под другим паролем
        self.db.set_user_chat_id(teacher['id'], new_chat_id)
        self.assertEqual(new_chat_id, self.db.get_user_by_id(teacher['id'])['chat_id'])

    def test_user_set_level(self):
        student1 = test_students[-1]
        student2 = test_students[0]
        new_level1 = 'level1'
        self.db.set_user_level(student1['id'], new_level1)
        self.assertEqual(self.db.get_user_by_id(student1['id'])['level'], new_level1)
        self.assertEqual(self.db.get_user_by_id(student2['id'])['level'], student2['level'])
        new_level2 = 'level2'
        self.db.set_user_level(student2['id'], new_level2)
        self.assertEqual(self.db.get_user_by_id(student1['id'])['level'], new_level1)
        self.assertEqual(self.db.get_user_by_id(student2['id'])['level'], new_level2)

    def test_webtokens(self):
        student1 = self.db.get_user_by_token(test_students[-1]['token'])
        student2 = self.db.get_user_by_token(test_students[0]['token'])
        token1 = 'token1'
        token2 = 'token2'
        self.assertIsNone(self.db.get_webtoken_by_user_id(student1['id']))
        self.assertIsNone(self.db.get_webtoken_by_user_id(student2['id']))
        self.assertIsNone(self.db.get_user_id_by_webtoken(token1))
        self.assertIsNone(self.db.get_user_id_by_webtoken(token2))
        self.db.add_webtoken(student1['id'], token1)
        self.assertEqual(self.db.get_webtoken_by_user_id(student1['id']), token1)
        self.assertIsNone(self.db.get_webtoken_by_user_id(student2['id']))
        self.assertEqual(self.db.get_user_id_by_webtoken(token1), student1['id'])
        self.assertIsNone(self.db.get_user_id_by_webtoken(token2))
        self.db.add_webtoken(student2['id'], token2)
        self.assertEqual(self.db.get_webtoken_by_user_id(student1['id']), token1)
        self.assertEqual(self.db.get_webtoken_by_user_id(student2['id']), token2)
        self.assertEqual(self.db.get_user_id_by_webtoken(token1), student1['id'])
        self.assertEqual(self.db.get_user_id_by_webtoken(token2), student2['id'])
        token2new = 'token2new'
        self.db.add_webtoken(student2['id'], token2new)
        self.assertEqual(self.db.get_webtoken_by_user_id(student1['id']), token1)
        self.assertEqual(self.db.get_webtoken_by_user_id(student2['id']), token2new)
        self.assertEqual(self.db.get_user_id_by_webtoken(token1), student1['id'])
        self.assertEqual(self.db.get_user_id_by_webtoken(token2new), student2['id'])

    def test_results(self):
        student1 = test_students[-1]
        student2 = test_students[0]
        answer1 = '17'
        answer2 = '18'
        verdict1 = 1
        verdict2 = -1
        for problem in test_problems:
            for student in test_students:
                self.db.add_result(student["id"], problem["id"], problem["level"], problem["lesson"], None, verdict1, answer1)
                self.db.add_result(student["id"], problem["id"], problem["level"], problem["lesson"], None, verdict2, answer2)
        problem = test_problems[2]
        for_recheck = self.db.get_results_for_recheck_by_problem_id(problem["id"])
        new_verdict = 99
        for row in for_recheck:
            row["verdict"] = new_verdict
        self.db.update_verdicts(for_recheck)
        results = self.db.list_student_results(student2["id"], problem["lesson"])
        for res in results:
            if res["problem_id"] == problem["id"]:
                self.assertEqual(res["verdict"], new_verdict)
            else:
                self.assertIn(res["verdict"], [verdict1, verdict2])

    def test_key_value_storage(self):
        kv = self.db.kv
        self.assertEqual(len(kv), 0)
        kv['foo1'] = 'baz1'
        kv['foo2'] = 'baz2'
        kv['foo3'] = 'baz3'
        self.assertEqual(len(kv), 3)
        self.assertEqual(kv['foo1'], 'baz1')
        kv['foo1'] = 'baz11'
        self.assertEqual(kv['foo1'], 'baz11')
        self.assertEqual(kv['foo2'], 'baz2')
        del kv['foo1']
        self.assertRaises(KeyError, lambda: kv['foo1'])
        self.assertIsNone(kv.get('foo1', None))
        self.assertIsNone(kv.pop('foo1', None))
        self.assertTrue('foo2' in kv)
        self.assertFalse('foo1' in kv)
        self.assertListEqual(kv.keys(), ['foo2', 'foo3'])
        self.assertListEqual(kv.values(), ['baz2', 'baz3'])
        self.assertEqual(kv.pop('foo2', None), 'baz2')
        self.assertIsNone(kv.get('foo2', None))

        db = self.db

        def get_problem_lock(teacher_id: int):
            key = f'{teacher_id}_pl'
            value = db.kv.get(key, None)
            return int(value) if value else None

        def del_problem_lock(teacher_id: int):
            key = f'{teacher_id}_pl'
            db.kv.pop(key, None)

        def set_problem_lock(teacher_id: int, problem_id: int):
            key = f'{teacher_id}_pl'
            value = f'{problem_id}'
            db.kv[key] = value

        self.assertIsNone(get_problem_lock(123))
        del_problem_lock(123)
        self.assertIsNone(get_problem_lock(123))
        set_problem_lock(123, 23)
        set_problem_lock(124, 24)
        set_problem_lock(125, 25)
        self.assertEqual(get_problem_lock(123), 23)
        self.assertEqual(get_problem_lock(124), 24)
        self.assertEqual(get_problem_lock(125), 25)
        set_problem_lock(123, 123)
        self.assertEqual(get_problem_lock(123), 123)
        self.assertEqual(get_problem_lock(124), 24)
        self.assertEqual(get_problem_lock(125), 25)
        del_problem_lock(123)
        self.assertIsNone(get_problem_lock(123))

    def test_zoom_queue(self):
        db = self.db
        ts1 = datetime(2022, 1, 1, 1)
        ts2 = datetime(2022, 1, 1, 2)
        ts3 = datetime(2022, 1, 1, 3)
        db.add_to_queue('name1', ts1)
        db.add_to_queue('name2', ts3)
        db.add_to_queue('name3', ts2)
        db.mark_joined('name2')
        queue = db.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0},
            {'zoom_user_name': 'name2', 'enter_ts': '2022-01-01T03:00:00', 'status': 1},
        ])
        db.add_to_queue('name2', ts1)
        db.add_to_queue('name3', datetime.now())
        queue = db.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name2', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])
        db.remove_from_queue('name2')
        queue = db.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])
        db.remove_from_queue('name1')
        queue = db.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])

    def test_problem_tags(self):
        db = self.db
        ts1 = datetime(2022, 1, 1, 1)
        ts2 = datetime(2022, 1, 1, 2)
        ts3 = datetime(2022, 1, 1, 3)
        problems = db.get_all_tags()
        self.assertEqual(len(problems), len(test_problems))
        self.assertIsNone(problems[0]['tags'])
        db.add_tags(7, 'tags1', 17)
        self.assertEqual(db.get_tags_by_problem_id(7),'tags1')
        db.add_tags(7, 'tags2', 18)
        self.assertEqual(db.get_tags_by_problem_id(7), 'tags2')
        self.assertIsNone(db.get_tags_by_problem_id(8))
        problems = db.get_all_tags()
        prob_7 = [prob for prob in problems if prob['id'] == 7][0]
        self.assertEqual(prob_7['tags'], 'tags2')

    def test_media_groups(self):
        db = self.db
        media_group_id = 123
        media_group_id_2 = 1234
        media_group_id_3 = 1235
        problem_id = 12

        saved_problem_id = db.media_group_check(media_group_id)
        self.assertIsNone(saved_problem_id)

        db.media_group_add(media_group_id, problem_id)
        saved_problem_id = db.media_group_check(media_group_id)
        self.assertEqual(problem_id, saved_problem_id)

        saved_problem_id = db.media_group_check(media_group_id_2)
        self.assertIsNone(saved_problem_id)
        saved_problem_id = db.media_group_check(media_group_id_3)
        self.assertIsNone(saved_problem_id)

        db.media_group_add(media_group_id_2, problem_id)
        db.media_group_add(media_group_id_3, problem_id)

        saved_problem_id = db.media_group_check(media_group_id_2)
        self.assertEqual(problem_id, saved_problem_id)
        saved_problem_id = db.media_group_check(media_group_id_3)
        self.assertEqual(problem_id, saved_problem_id)

    def test_game_methods(self):
        self.db.set_student_command(3, 'н', 179)
        self.db.set_student_command(3, 'н', 178)
        self.assertEqual(self.db.get_student_command(3)['command_id'], 178)

        self.db.set_student_command(1, 'н', 179)
        self.db.set_student_command(2, 'н', 179)
        self.db.set_student_command(3, 'н', 178)
        self.assertEqual(self.db.get_student_command(1)['command_id'], 179)

        self.assertTrue(self.db.add_payment(3, 178, 15, 10, 1))
        self.db.add_payment(2, 179, 15, 10, 1)
        self.assertFalse(self.db.add_payment(3, 178, 15, 10, 1))
        self.assertEqual(self.db.get_student_payments(3)[0]['amount'], 1)
        self.assertEqual(self.db.get_opened_cells(178), [{'x': 15, 'y': 10}])
        self.db.set_student_flag(2, 179, 12, 13)
        self.db.set_student_flag(2, 179, 11, 13)
        self.db.set_student_flag(1, 179, 20, 10)
        self.assertEqual(db.get_flags_by_command(179), [{'x': 11, 'y': 13}, {'x': 20, 'y': 10}])
        self.db.set_student_flag(1, 179, 11, 13)
        self.assertEqual(self.db.get_flags_by_command(179), [{'x': 11, 'y': 13}, {'x': 11, 'y': 13}])

        self.assertListEqual(self.db.get_student_chests(3, 333), [])
        self.db.add_student_chest(3, 333, 1, 1, 5)
        self.db.add_student_chest(4, 333, 1, 1, 6)
        self.db.add_student_chest(3, 3333, 1, 1, 7)
        self.db.add_student_chest(3, 333, 1, 2, 55)
        chests = self.db.get_student_chests(3, 333)
        self.assertEqual(len(chests), 2)
        self.assertEqual(chests[0]['bonus'], 5)
        self.assertEqual(chests[1]['bonus'], 55)
        self.db.add_student_chest(3, 333, 1, 2, 555)
        chests = self.db.get_student_chests(3, 333)
        self.assertEqual(len(chests), 2)
        self.assertEqual(chests[0]['bonus'], 5)
        self.assertEqual(chests[1]['bonus'], 555)


    # def add_problem(self, data: dict)
    # def fetch_all_problems(self)
    # def fetch_all_lessons(self)
    # def get_last_lesson_num(self)
    # def fetch_all_problems_by_lesson(self, level: str, lesson: int)
    # def get_problem_by_id(self, id: int)
    # def get_problem_by_text_number(self, level: str, lesson: int, prob: int, item: '')

    # def fetch_all_states(self)
    # def get_state_by_user_id(self, user_id: int)
    # def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0, last_teacher_id: int = 0, oral_problem_id: int = None)
    # def update_oral_problem(self, user_id: int, oral_problem_id: int = None)

    # def add_result(self, student_id: int, problem_id: int, level: str, lesson: int, teacher_id: int, verdict: int, answer: str, res_type: int = None)
    # def check_num_answers(self, student_id: int, problem_id: int)
    # def delete_plus(self, student_id: int, problem_id: int, verdict: int)
    # def check_student_solved(self, student_id: int, level: str, lesson: int)
    # def check_student_sent_written(self, student_id: int, lesson: int)

    # def insert_into_written_task_queue(self, student_id: int, problem_id: int, cur_status: int, ts: datetime = None)
    # def get_written_tasks_to_check(self, teacher_id)
    # def get_written_tasks_count(self)
    # def upd_written_task_status(self, student_id: int, problem_id: int, new_status: int, teacher_id: int = None)
    # def delete_from_written_task_queue(self, student_id: int, problem_id: int)

    # def add_user_to_waitlist(self, student_id: int, problem_id: int)
    # def remove_user_from_waitlist(self, student_id: int)
    # def get_waitlist_top(self, top_n: int)

    # def insert_into_written_task_discussion(self, student_id: int, problem_id: int, teacher_id: int, text: str, attach_path: str, chat_id: int, tg_msg_id: int)
    # def fetch_written_task_discussion(self, student_id: int, problem_id: int)

    # def add_message_to_log(self, from_bot: bool, tg_msg_id: int, chat_id: int, student_id: int, teacher_id: int, msg_text: str, attach_path: str)

    # def calc_last_lesson_stat(self)

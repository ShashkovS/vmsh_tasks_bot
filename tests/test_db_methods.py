import os
from unittest import TestCase

from helpers.consts import *
from db_methods import db
from .initial_test_data import test_students, test_teachers


class DatabaseMethodsTest(TestCase):
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

    def insert_dummy_users(self):
        for row in test_students + test_teachers:
            real_id = self.db.add_user(row)
            row['id'] = real_id

    def tearDown(self) -> None:
        self.db.disconnect()
        os.unlink(self.db.db_file)

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

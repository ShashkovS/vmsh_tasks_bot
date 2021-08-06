import os
from dataclasses import asdict
from unittest import TestCase
from unittest.mock import patch
from db_methods import DB
from consts import *

initial_test_students = [
  {"chat_id": None, "type": 1, "level": "н", "name": "Григорий", "surname": "Ющенко", "middlename": "", "token": "token1"},
  {"chat_id": 1230, "type": 1, "level": "п", "name": "София", "surname": "Полякова", "middlename": "", "token": "token2"},
  {"chat_id": 1231, "type": 1, "level": "п", "name": "Антон", "surname": "Михеенко", "middlename": "", "token": "token3"},
  {"chat_id": None, "type": 1, "level": "н", "name": "Михаил", "surname": "Наумов", "middlename": "", "token": "token4"},
  {"chat_id": 1232, "type": 1, "level": "н", "name": "Амир М.", "surname": "Файзуллин", "middlename": "", "token": "token5"},
  {"chat_id": 1233, "type": 1, "level": "н", "name": "Марк", "surname": "Шерман", "middlename": "", "token": "token6"},
]
initial_test_teachers = [
  {"chat_id": None, "type": 2, "level": None, "name": "Анна", "surname": "Гришина", "middlename": "10A", "token": "token101"},
  {"chat_id": 2120, "type": 2, "level": None, "name": "Надежда", "surname": "Ибрагимова", "middlename": "10Б", "token": "token102"},
]



class DatabaseMethodsTest(TestCase):
    def setUp(self) -> None:
        # to create db instance and access db_file field is the only way to extract file path
        self.db = DB('test.db')
        self.db.disconnect()

        # ensure there is no trash file from previous incorrectly handled tests present
        os.unlink(self.db.db_file)

        # create shiny new db instance from scratch
        self.db = DB('test.db')

    def insert_dummy_users(self):
        for row in initial_test_students + initial_test_teachers:
            real_id = self.db.add_user(row)
            row['id'] = real_id

    def tearDown(self) -> None:
        self.db.disconnect()
        os.unlink(self.db.db_file)

    def test_users_add_and_fetch_all(self):
        with patch('db_methods.db', self.db):
            self.insert_dummy_users()
            students = self.db.fetch_all_users_by_type(USER_TYPE_STUDENT)
            teachers = self.db.fetch_all_users_by_type(USER_TYPE_TEACHER)
            all_users = self.db.fetch_all_users_by_type()
            self.assertEqual(len(students), len(initial_test_students))
            self.assertEqual(len(teachers), len(initial_test_teachers))
            self.assertEqual(len(all_users), len(students) + len(teachers))
            self.assertListEqual(students, initial_test_students)
            self.assertListEqual(teachers, initial_test_teachers)
            self.assertListEqual(all_users, initial_test_students + initial_test_teachers)

    def test_users_get_by(self):
        with patch('db_methods.db', self.db):
            self.insert_dummy_users()
            student = initial_test_students[-1]
            teacher = initial_test_teachers[-1]
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
        self.insert_dummy_users()
        student1 = initial_test_students[-1]
        student2 = initial_test_students[0]
        teacher = initial_test_teachers[-1]
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
        self.insert_dummy_users()
        student1 = initial_test_students[-1]
        student2 = initial_test_students[0]
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

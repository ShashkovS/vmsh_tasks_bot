# Для работы по виндой нужны PYTHONUTF8=1
import os
from unittest import TestCase
from datetime import datetime

from helpers.consts import *
import db_methods as db
from .initial_test_data import test_students, test_teachers, test_problems


class DatabaseMethodsTest(TestCase):
    def setUp(self) -> None:
        print(f'setup, id={id(self)}, {self!r}')
        self.db = db
        test_db_filename = f'db/unittest.db'
        # ensure there is no trash file from previous incorrectly handled tests present
        for file in [test_db_filename, test_db_filename + '-shm', test_db_filename + '-wal']:
            try:
                os.unlink(file)
            except FileNotFoundError:
                pass
        # create shiny new db instance from scratch and connect
        self.db.sql.setup(test_db_filename)
        # Making it blazing fast
        self.db.sql.conn.execute('''      PRAGMA journal_mode = OFF;       ''')
        self.db.sql.conn.execute('''      PRAGMA synchronous = 0;       ''')
        self.db.sql.conn.execute('''      PRAGMA cache_size = 1000000;       ''')
        self.db.sql.conn.execute('''      PRAGMA locking_mode = EXCLUSIVE;       ''')
        self.db.sql.conn.execute('''      PRAGMA temp_store = MEMORY;       ''')
        self.insert_dummy_users()
        self.insert_dummy_problems()

    def tearDown(self) -> None:
        print(f'tearDown, id={id(self)}')
        self.db.sql.disconnect()
        try:
            os.unlink(self.db.sql.db_file)
        except PermissionError:
            pass

    def insert_dummy_users(self):
        for row in test_students + test_teachers:
            real_id = self.db.user.insert(row)
            row['id'] = real_id

    def insert_dummy_problems(self):
        for row in test_problems:
            real_id = self.db.problem.insert(row)
            row['id'] = real_id

    def test_users_add_and_fetch_all(self):
        students = self.db.user.get_all_by_type(USER_TYPE.STUDENT)
        teachers = self.db.user.get_all_by_type(USER_TYPE.TEACHER)
        all_users = self.db.user.get_all_by_type()
        self.assertEqual(len(students), len(test_students))
        self.assertEqual(len(teachers), len(test_teachers))
        self.assertEqual(len(all_users), len(students) + len(teachers))
        self.assertListEqual(students, test_students)
        self.assertListEqual(teachers, test_teachers)
        self.assertListEqual(all_users, test_students + test_teachers)

    def test_users_get_by(self):
        student = test_students[-1]
        teacher = test_teachers[-1]
        self.assertDictEqual(self.db.user.get_by_id(student['id']), student)
        self.assertDictEqual(self.db.user.get_by_token(student['token']), student)
        self.assertDictEqual(self.db.user.get_by_chat_id(student['chat_id']), student)
        self.assertDictEqual(self.db.user.get_by_id(teacher['id']), teacher)
        self.assertDictEqual(self.db.user.get_by_token(teacher['token']), teacher)
        self.assertDictEqual(self.db.user.get_by_chat_id(teacher['chat_id']), teacher)
        self.assertIsNone(self.db.user.get_by_id(-1))
        self.assertIsNone(self.db.user.get_by_token('-1'))
        self.assertIsNone(self.db.user.get_by_chat_id(-1))

    def test_user_set_chat_id(self):
        student1 = test_students[-1]
        student2 = test_students[0]
        teacher = test_teachers[-1]
        self.assertDictEqual(student1, self.db.user.get_by_id(student1['id']))
        self.assertDictEqual(student2, self.db.user.get_by_id(student2['id']))
        new_chat_id = 12345
        self.db.user.set_chat_id(student1['id'], new_chat_id)
        self.assertEqual(12345, self.db.user.get_by_id(student1['id'])['chat_id'])
        self.assertEqual(student2['chat_id'], self.db.user.get_by_id(student2['id'])['chat_id'])
        # Тот же юзер заходит под другим паролем
        self.db.user.set_chat_id(student2['id'], new_chat_id)
        self.assertIsNone(self.db.user.get_by_id(student1['id'])['chat_id'])
        self.assertEqual(new_chat_id, self.db.user.get_by_id(student2['id'])['chat_id'])
        # Тот же юзер заходит под другим паролем
        self.db.user.set_chat_id(teacher['id'], new_chat_id)
        self.assertEqual(new_chat_id, self.db.user.get_by_id(teacher['id'])['chat_id'])

    def test_user_set_group_and_allowed_groups(self):
        student = test_students[-1]
        self.db.user.set_group_id(student['id'], 'pro')
        self.assertEqual(self.db.user.get_by_id(student['id'])['group_id'], 'pro')
        allowed_groups = ';novice;pro;'
        self.db.user.set_allowed_groups(student['id'], allowed_groups)
        self.assertEqual(self.db.user.get_allowed_groups(student['id']), allowed_groups)

    def test_groups_crud_and_queries(self):
        new_group = {
            'group_id': 'custom',
            'short_code': 'c',
            'broadcast_code': 'all_custom',
            'tg_command': '/level_custom',
            'public_name': 'Custom Group',
            'conditions_url': 'https://example.com/custom',
            'tasks_header_template': 'Header',
            'switch_message': 'Switched',
            'sort_order': 99,
            'is_active': 1,
            'is_default': 0,
            'allow_self_switch': 1,
            'is_system': 0,
            'score_weight': 1.0,
        }
        self.db.group.insert(new_group)
        row = self.db.group.get_by_id('custom')
        self.assertEqual(row['group_id'], 'custom')
        self.assertEqual(self.db.group.get_by_command('/level_custom')['group_id'], 'custom')
        self.assertEqual(self.db.group.get_by_broadcast_code('all_custom')['group_id'], 'custom')
        short_code_rows = self.db.group.get_by_short_code('c')
        self.assertTrue(any(item['group_id'] == 'custom' for item in short_code_rows))

    def test_schema_has_no_legacy_level_columns(self):
        legacy_column = 'le' 'vel'
        tables = [
            'users',
            'problems',
            'lessons',
            'results',
            'zoom_conversation',
            'game_students_commands',
        ]
        for table in tables:
            columns = [row['name'] for row in self.db.sql.conn.execute(f"pragma table_info({table})").fetchall()]
            self.assertNotIn(legacy_column, columns, msg=f'legacy column still exists in {table}')

    def test_webtokens(self):
        student1 = self.db.user.get_by_token(test_students[-1]['token'])
        student2 = self.db.user.get_by_token(test_students[0]['token'])
        token1 = 'token1'
        token2 = 'token2'
        self.assertIsNone(self.db.web_token.get_by_user_id(student1['id']))
        self.assertIsNone(self.db.web_token.get_by_user_id(student2['id']))
        self.assertIsNone(self.db.web_token.get_user_id(token1))
        self.assertIsNone(self.db.web_token.get_user_id(token2))
        self.db.web_token.insert(student1['id'], token1)
        self.assertEqual(self.db.web_token.get_by_user_id(student1['id']), token1)
        self.assertIsNone(self.db.web_token.get_by_user_id(student2['id']))
        self.assertEqual(self.db.web_token.get_user_id(token1), student1['id'])
        self.assertIsNone(self.db.web_token.get_user_id(token2))
        self.db.web_token.insert(student2['id'], token2)
        self.assertEqual(self.db.web_token.get_by_user_id(student1['id']), token1)
        self.assertEqual(self.db.web_token.get_by_user_id(student2['id']), token2)
        self.assertEqual(self.db.web_token.get_user_id(token1), student1['id'])
        self.assertEqual(self.db.web_token.get_user_id(token2), student2['id'])
        token2new = 'token2new'
        self.db.web_token.insert(student2['id'], token2new)
        self.assertEqual(self.db.web_token.get_by_user_id(student1['id']), token1)
        self.assertEqual(self.db.web_token.get_by_user_id(student2['id']), token2new)
        self.assertEqual(self.db.web_token.get_user_id(token1), student1['id'])
        self.assertEqual(self.db.web_token.get_user_id(token2new), student2['id'])

    def test_results(self):
        student1 = test_students[-1]
        student2 = test_students[0]
        answer1 = '17'
        answer2 = '18'
        verdict1 = 1
        verdict2 = -1
        for problem in test_problems:
            for student in test_students:
                self.db.result.insert(student["id"], problem["id"], problem["lesson"], None, verdict1, answer1)
                self.db.result.insert(student["id"], problem["id"], problem["lesson"], None, verdict2, answer2)
        problem = test_problems[2]
        for_recheck = self.db.result.get_for_recheck_by_problem_id(problem["id"])
        new_verdict = 99
        for row in for_recheck:
            row["verdict"] = new_verdict
        self.db.result.update_verdicts(for_recheck)
        results = self.db.result.list_student_results(student2["id"], problem["lesson"])
        for res in results:
            if res["problem_id"] == problem["id"]:
                self.assertEqual(res["verdict"], new_verdict)
            else:
                self.assertIn(res["verdict"], [verdict1, verdict2])
        group_id = problem["group_id"]
        group_results = self.db.result.list_student_results(
            student2["id"], problem["lesson"], group_id=group_id
        )
        group_problem_ids = {item["id"] for item in test_problems if item["group_id"] == group_id}
        self.assertTrue(group_results)
        self.assertTrue(all(row['problem_id'] in group_problem_ids for row in group_results))

    def test_group_filters_on_problems_and_lessons(self):
        group_id = 'novice'
        lesson_num = 4
        problems = self.db.problem.get_all_by_lesson(group_id, lesson_num)
        self.assertTrue(problems)
        self.assertTrue(all(row['group_id'] == group_id for row in problems))
        self.db.lesson.update()
        lessons = self.db.lesson.get_all(group_id=group_id)
        self.assertTrue(lessons)
        self.assertTrue(all(row['group_id'] == group_id for row in lessons))

    def test_key_value_storage(self):
        kv = self.db.sql.kv
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
        self.assertEqual(len(list(kv.iteritems())), 2)
        self.assertEqual(kv.pop('foo2', None), 'baz2')
        self.assertIsNone(kv.get('foo2', None))
        self.assertEqual(len(list(kv.items())), 1)

        db = self.db

        def get_problem_lock(teacher_id: int):
            key = f'{teacher_id}_pl'
            value = db.sql.kv.get(key, None)
            return int(value) if value else None

        def del_problem_lock(teacher_id: int):
            key = f'{teacher_id}_pl'
            db.sql.kv.pop(key, None)

        def set_problem_lock(teacher_id: int, problem_id: int):
            key = f'{teacher_id}_pl'
            value = f'{problem_id}'
            db.sql.kv[key] = value

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
        db.zoom_queue.insert('name1', ts1)
        db.zoom_queue.insert('name2', ts3)
        db.zoom_queue.insert('name3', ts2)
        db.zoom_queue.mark_joined('name2')
        queue = db.zoom_queue.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0},
            {'zoom_user_name': 'name2', 'enter_ts': '2022-01-01T03:00:00', 'status': 1},
        ])
        db.zoom_queue.insert('name2', ts1)
        db.zoom_queue.insert('name3', datetime.now())
        queue = db.zoom_queue.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name2', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])
        db.zoom_queue.delete('name2')
        queue = db.zoom_queue.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name1', 'enter_ts': '2022-01-01T01:00:00', 'status': 0},
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])
        db.zoom_queue.delete('name1')
        queue = db.zoom_queue.get_first_from_queue()
        self.assertListEqual(queue, [
            {'zoom_user_name': 'name3', 'enter_ts': '2022-01-01T02:00:00', 'status': 0}
        ])

    def test_media_groups(self):
        db = self.db
        media_group_id = 123
        media_group_id_2 = 1234
        media_group_id_3 = 1235
        problem_id = 12

        saved_problem_id = db.media_group.check(media_group_id)
        self.assertIsNone(saved_problem_id)

        db.media_group.insert(media_group_id, problem_id)
        saved_problem_id = db.media_group.check(media_group_id)
        self.assertEqual(problem_id, saved_problem_id)

        saved_problem_id = db.media_group.check(media_group_id_2)
        self.assertIsNone(saved_problem_id)
        saved_problem_id = db.media_group.check(media_group_id_3)
        self.assertIsNone(saved_problem_id)

        db.media_group.insert(media_group_id_2, problem_id)
        db.media_group.insert(media_group_id_3, problem_id)

        saved_problem_id = db.media_group.check(media_group_id_2)
        self.assertEqual(problem_id, saved_problem_id)
        saved_problem_id = db.media_group.check(media_group_id_3)
        self.assertEqual(problem_id, saved_problem_id)

    def test_game_methods(self):
        self.db.game.set_student_command(3, 179, group_id='novice')
        self.db.game.set_student_command(3, 178, group_id='novice')
        self.assertEqual(self.db.game.get_student_command(3)['command_id'], 178)

        self.db.game.set_student_command(1, 179, group_id='novice')
        self.db.game.set_student_command(2, 179, group_id='novice')
        self.db.game.set_student_command(3, 178, group_id='novice')
        self.assertEqual(self.db.game.get_student_command(1)['command_id'], 179)

        self.assertTrue(self.db.game.add_payment(3, 178, 15, 10, 1))
        self.db.game.add_payment(2, 179, 15, 10, 1)
        self.assertFalse(self.db.game.add_payment(3, 178, 15, 10, 1))
        self.assertEqual(self.db.game.get_student_payments(3, 178)[0]['amount'], 1)
        self.assertEqual(self.db.game.get_opened_cells(178), [{'x': 15, 'y': 10}])
        self.db.game.set_student_flag(2, 179, 12, 13)
        self.db.game.set_student_flag(2, 179, 11, 13)
        self.db.game.set_student_flag(1, 179, 20, 10)
        self.assertEqual(db.game.get_flags_by_command(179), [{'x': 11, 'y': 13}, {'x': 20, 'y': 10}])
        self.db.game.set_student_flag(1, 179, 11, 13)
        self.assertEqual(self.db.game.get_flags_by_command(179), [{'x': 11, 'y': 13}, {'x': 11, 'y': 13}])

        self.assertListEqual(self.db.game.get_student_chests(3, 333), [])
        self.db.game.add_student_chest(3, 333, 1, 1, 5)
        self.db.game.add_student_chest(4, 333, 1, 1, 6)
        self.db.game.add_student_chest(3, 3333, 1, 1, 7)
        self.db.game.add_student_chest(3, 333, 1, 2, 55)
        chests = self.db.game.get_student_chests(3, 333)
        self.assertEqual(len(chests), 2)
        self.assertEqual(chests[0]['bonus'], 5)
        self.assertEqual(chests[1]['bonus'], 55)
        self.db.game.add_student_chest(3, 333, 1, 2, 555)
        chests = self.db.game.get_student_chests(3, 333)
        self.assertEqual(len(chests), 2)
        self.assertEqual(chests[0]['bonus'], 5)
        self.assertEqual(chests[1]['bonus'], 555)
        print(self.db.game.get_opened_cells_timeline(179))

    def test_survey(self):
        surv_1_id = self.db.survey.add_survey(SURVEY_TYPES.RADIO, True, 'WHAT??', ['One', 'Two'])
        surv_2_id = self.db.survey.add_survey(SURVEY_TYPES.CHECKBOX, True, 'Check', ['Either', 'Neither'])
        surv_3_id = self.db.survey.add_survey(SURVEY_TYPES.CHECKBOX, True, 'Check3', ['Either3', 'Neither3'])
        surv_2 = self.db.survey.get_survey_by_id(surv_2_id)
        self.assertEqual(surv_2['question'], 'Check')
        all_student_ids = [s['id'] for s in test_students]
        self.assertIsNone(self.db.survey.get_active_survey(test_students[0]['id']))
        self.assertListEqual([], self.db.survey.get_survey_assigns(surv_1_id))
        self.db.survey.assign_survey(surv_1_id, all_student_ids)
        self.assertListEqual(all_student_ids, self.db.survey.get_survey_assigns(surv_1_id))
        self.assertIsNotNone(self.db.survey.get_active_survey(test_students[0]['id']))
        stud_surv = self.db.survey.get_active_survey(test_students[0]['id'])
        self.assertEqual('WHAT??', stud_surv['question'])
        self.assertIsNone(self.db.survey.get_active_survey(test_teachers[0]['id']))
        self.db.survey.update_survey_result(13, surv_1_id, [123, 125])
        self.db.survey.update_survey_result(13, surv_1_id, [123, 188])
        self.assertEqual([123, 188], self.db.survey.get_survey_result(13, surv_1_id))
        self.db.survey.disable_survey(surv_1_id)
        survey = self.db.survey.get_active_survey(USER_TYPE.STUDENT)
        self.assertIsNone(survey)
        self.assertListEqual([], self.db.survey.get_survey_assigns(surv_2_id))
        self.assertListEqual([], self.db.survey.get_survey_assigns(surv_3_id))
        self.db.survey.assign_survey(surv_3_id, all_student_ids)
        half_students_id = all_student_ids[::2]
        left_students_id = list(set(all_student_ids) - set(half_students_id))
        self.db.survey.assign_survey(surv_2_id, half_students_id)
        self.assertListEqual([], self.db.survey.get_survey_assigns(surv_1_id))
        self.assertListEqual(half_students_id, self.db.survey.get_survey_assigns(surv_2_id))
        self.assertListEqual(left_students_id, self.db.survey.get_survey_assigns(surv_3_id))
        # print(f'{self.db.survey.get_survey_assigns(surv_1_id)=} {[]=}')
        # print(f'{self.db.survey.get_survey_assigns(surv_2_id)=} {half_students_id=}')
        # print(f'{self.db.survey.get_survey_assigns(surv_3_id)=} {left_students_id=}')
        stud_surv_2 = self.db.survey.get_active_survey(half_students_id[0])
        stud_surv_3 = self.db.survey.get_active_survey(left_students_id[0])
        # print(f'{stud_surv_2=}')
        # print(f'{stud_surv_3=}')
        self.assertEqual('Neither', stud_surv_2['choices'][1]['text'])
        self.assertEqual('Either3', stud_surv_3['choices'][0]['text'])


    # def add_problem(self, data: dict)
    # def fetch_all_problems(self)
    # def fetch_all_lessons(self)
    # def get_last_lesson_num(self)
    # def fetch_all_problems_by_lesson(self, group_id: str, lesson: int)
    # def get_problem_by_id(self, id: int)
    # def get_problem_by_text_number(self, group_id: str, lesson: int, prob: int, item: '')

    # def fetch_all_states(self)
    # def get_state_by_user_id(self, user_id: int)
    # def update_state(self, user_id: int, state: int, problem_id: int = 0, last_student_id: int = 0, last_teacher_id: int = 0, oral_problem_id: int = None)
    # def update_oral_problem(self, user_id: int, oral_problem_id: int = None)

    # def add_result(self, student_id: int, problem_id: int, lesson: int, teacher_id: int, verdict: int, answer: str, res_type: int = None)
    # def check_num_answers(self, student_id: int, problem_id: int)
    # def delete_plus(self, student_id: int, problem_id: int, verdict: int)
    # def check_student_solved(self, student_id: int, group_id: str, lesson: int)
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

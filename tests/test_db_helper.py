import os
from dataclasses import asdict
from unittest import TestCase
from unittest.mock import patch

from db_helper import DB, User, Users, Problem, Problems


class ObjectRelationsMappingTest(TestCase):
    def setUp(self) -> None:
        # to create db instance and access db_file field is the only way to extract file path
        self.db = DB('test.db')
        self.db.disconnect()

        # ensure there is no trash file from previous incorrectly handled tests present
        os.unlink(self.db.db_file)

        # create shiny new db instance from scratch
        self.db = DB('test.db')

    def tearDown(self) -> None:
        self.db.disconnect()
        os.unlink(self.db.db_file)

    def test_users_model(self):
        with patch('db_helper.db', self.db):
            u1 = User(None, 1, 'name', 'surname', 'middle', 'tok1')
            u2 = User(124, 1, 'name2', 'surname2', 'middle', 'tok2')
            u3 = User(125, 1, 'name3', 'surname3', 'middle', 'tok3')
            u1upd = User(12312, 1, 'name1', 'surname1', 'middle', 'tok1')

            u1_data = {'chat_id': 12312, 'type': 1, 'name': 'name1', 'surname': 'surname1', 'middlename': 'middle',
                       'token': 'tok1', 'id': 1}
            u2_data = {'chat_id': 124, 'type': 1, 'name': 'name2', 'surname': 'surname2', 'middlename': 'middle',
                       'token': 'tok2', 'id': 2}
            u3_data = {'chat_id': 125, 'type': 1, 'name': 'name3', 'surname': 'surname3', 'middlename': 'middle',
                       'token': 'tok3', 'id': 3}

            users = Users()

            assert [asdict(u) for u in users] == [u1_data, u2_data, u3_data]
            assert asdict(users.by_token['tok2']) == u2_data
            assert asdict(users.by_id[1]) == u1_data
            assert asdict(users.by_chat_id[12312]) == u1_data
            assert users.get_by_id(123) is None
            assert asdict(users.get_by_id(1)) == u1_data
            assert len(users) == 3

    def test_problems_model(self):
        with patch('db_helper.db', self.db):
            p1 = Problem(1, 1, 'а', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
            p2 = Problem(1, 1, 'б', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
            p3 = Problem(1, 2, '', 'Гы', 'текст', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')
            p2upd = Problem(1, 1, 'б', 'Гы', 'текст_upd', 0, 0, r'\d+', 'ЧИСЛО!', 123, 'check_int', 'ЛОЖЬ!', 'Крутяк')

            p1_data = {'list': 1, 'prob': 1, 'item': 'а', 'title': 'Гы', 'prob_text': 'текст', 'prob_type': 0,
                       'ans_type': 0, 'ans_validation': '\\d+', 'validation_error': 'ЧИСЛО!', 'cor_ans': '123',
                       'cor_ans_checker': 'check_int', 'wrong_ans': 'ЛОЖЬ!', 'congrat': 'Крутяк', 'id': 1}
            p2_data = {'list': 1, 'prob': 1, 'item': 'б', 'title': 'Гы', 'prob_text': 'текст_upd', 'prob_type': 0,
                       'ans_type': 0, 'ans_validation': '\\d+', 'validation_error': 'ЧИСЛО!', 'cor_ans': '123',
                       'cor_ans_checker': 'check_int', 'wrong_ans': 'ЛОЖЬ!', 'congrat': 'Крутяк', 'id': 2}
            p3_data = {'list': 1, 'prob': 2, 'item': '', 'title': 'Гы', 'prob_text': 'текст', 'prob_type': 0,
                       'ans_type': 0, 'ans_validation': '\\d+', 'validation_error': 'ЧИСЛО!', 'cor_ans': '123',
                       'cor_ans_checker': 'check_int', 'wrong_ans': 'ЛОЖЬ!', 'congrat': 'Крутяк', 'id': 3}

            problems = Problems()

            assert [asdict(p) for p in problems] == [p1_data, p2_data, p3_data]
            assert asdict(problems.by_id[1]) == p1_data
            assert asdict(problems.by_key[(1, 1, 'б')]) == p2_data
            assert problems.get_by_key(1, 1, 'б') is None
            assert problems.get_by_key(1, 1, 'бs') is None
            assert len(problems) == 3

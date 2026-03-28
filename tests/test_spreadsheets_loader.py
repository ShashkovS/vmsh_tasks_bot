# Для работы по виндой нужны PYTHONUTF8=1
from unittest import TestCase

from models.spreadsheets import FromGoogleSpreadsheet


class SpreadsheetGroupsTest(TestCase):
    def test_normalize_groups_ok(self):
        groups = [
            {
                'group_id': 'н',
                'short_code': 'н',
                'broadcast_code': 'all_n',
                'tg_command': '/switch_n',
                'public_name': 'Начинающие',
                'conditions_url': '',
                'tasks_header_template': '<a href=""{group.conditions_url}"">tasks</a>',
                'switch_message': 'Now in ""Math""',
                'sort_order': '10',
                'is_active': '1',
                'is_default': '0',
                'allow_self_switch': '1',
                'is_system': '0',
                'score_weight': '1.5',
            }
        ]
        normalized, errors = FromGoogleSpreadsheet.normalize_groups(groups)
        self.assertFalse(errors)
        self.assertEqual(len(normalized), 1)
        row = normalized[0]
        self.assertEqual(row['group_id'], 'н')
        self.assertEqual(row['sort_order'], 10)
        self.assertEqual(row['is_active'], 1)
        self.assertEqual(row['allow_self_switch'], 1)
        self.assertEqual(row['score_weight'], 1.5)
        self.assertEqual(row['tasks_header_template'], '<a href="{group.conditions_url}">tasks</a>')
        self.assertEqual(row['switch_message'], 'Now in "Math"')

    def test_group_id_forbids_semicolon(self):
        groups = [
            {
                'group_id': 'bad;id',
                'short_code': 'b',
                'public_name': 'Bad',
            }
        ]
        normalized, errors = FromGoogleSpreadsheet.normalize_groups(groups)
        self.assertEqual(normalized, [])
        self.assertGreater(len(errors), 0)

    def test_duplicate_command_is_error(self):
        groups = [
            {
                'group_id': 'g1',
                'short_code': 'g',
                'public_name': 'G1',
                'tg_command': '/level_g',
            },
            {
                'group_id': 'g2',
                'short_code': 'h',
                'public_name': 'G2',
                'tg_command': '/level_g',
            }
        ]
        normalized, errors = FromGoogleSpreadsheet.normalize_groups(groups)
        self.assertEqual(len(normalized), 1)
        self.assertGreater(len(errors), 0)

    def test_pick_user_group_id_prefers_first_allowed_group(self):
        self.assertEqual(
            FromGoogleSpreadsheet._pick_user_group_id('', ';i28m;i28p;i28c;'),
            'i28m',
        )
        self.assertEqual(
            FromGoogleSpreadsheet._pick_user_group_id('i27m', ';i28m;i28p;i28c;'),
            'i28m',
        )
        self.assertEqual(
            FromGoogleSpreadsheet._pick_user_group_id('i28p', ';i28m;i28p;i28c;'),
            'i28p',
        )

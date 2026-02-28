# Для работы по виндой нужны PYTHONUTF8=1
from unittest import TestCase

from models.spreadsheets import FromGoogleSpreadsheet


class SpreadsheetGroupsTest(TestCase):
    def test_normalize_groups_ok(self):
        groups = [
            {
                'group_id': 'novice',
                'short_code': 'n',
                'broadcast_code': 'all_novice',
                'tg_command': '/level_novice',
                'public_name': 'Novice',
                'conditions_url': '',
                'tasks_header_template': '',
                'switch_message': '',
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
        self.assertEqual(row['group_id'], 'novice')
        self.assertEqual(row['sort_order'], 10)
        self.assertEqual(row['is_active'], 1)
        self.assertEqual(row['allow_self_switch'], 1)
        self.assertEqual(row['score_weight'], 1.5)

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

# -*- coding: utf-8 -*-
from helpers.config import logger

_IGNORE_FIRST_HEADER_ROWS_NUM = 2
_PROBLEMS_HEADERS = [
    'group_id', 'lesson', 'prob', 'item',
    'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error',
    'cor_ans', 'cor_ans_checker', 'wrong_ans', 'congrat',
]
_STUDENTS_HEADERS = ['surname', 'name', 'token', 'group_id', 'online', 'grade', 'birthday', 'allowed_groups']
_TEACHERS_HEADERS = ['surname', 'name', 'middlename', 'token', 'online', 'group_id', 'allowed_groups']
_UI_MESSAGES_HEADERS = ['key', 'value']
_BOT_SETTINGS_HEADERS = ['key', 'value']
_GROUPS_HEADERS = [
    'group_id',
    'short_code',
    'broadcast_code',
    'tg_command',
    'public_name',
    'conditions_url',
    'tasks_header_template',
    'switch_message',
    'sort_order',
    'is_active',
    'is_default',
    'allow_self_switch',
    'is_system',
    'score_weight',
]


def _dict_factory(rows, column_names):
    res_rows = []
    for row in rows:
        d = {}
        for idx, col in enumerate(column_names):
            val = row[idx] if idx < len(row) else ''
            d[col] = val
        res_rows.append(d)
    return res_rows


class SpreadsheetLoader:
    def __init__(self, sheets_key: str = None, google_cred_json: str = None):
        self.sheets_key = sheets_key
        self.google_cred_json = google_cred_json
        self.client = None

    def setup(self, sheets_key: str, google_cred_json: str):
        self.sheets_key = sheets_key
        self.google_cred_json = google_cred_json

    def _connect_to_google_sheets(self):
        logger.info('Setting reload: using google')
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.google_cred_json, scopes)
        self.client = client = gspread.authorize(creds)
        sheet = client.open_by_key(self.sheets_key)
        return sheet

    def _load_problems(self, sheet):
        worksheet_problems = sheet.worksheet("Задачи")
        logger.info('Setting reload: fetching problems')
        problems = _dict_factory(
            worksheet_problems.get_all_values(),
            _PROBLEMS_HEADERS,
        )
        return problems[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def _load_students(self, sheet):
        logger.info('Setting reload: fetching students')
        worksheet_students = sheet.worksheet("Школьники")
        students = _dict_factory(
            worksheet_students.get_all_values(),
            _STUDENTS_HEADERS,
        )
        return students[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def _load_teachers(self, sheet):
        logger.info('Setting reload: fetching teachers')
        worksheet_students = sheet.worksheet("Учителя")
        teachers = _dict_factory(
            worksheet_students.get_all_values(),
            _TEACHERS_HEADERS,
        )
        return teachers[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def _load_ui_messages(self, sheet):
        logger.info('Setting reload: fetching ui_messages')
        worksheet_students = sheet.worksheet("_BotUIMsgs")
        ui_messages = _dict_factory(
            worksheet_students.get_all_values(),
            _UI_MESSAGES_HEADERS,
        )
        return ui_messages[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def _load_bot_settings(self, sheet):
        logger.info('Setting reload: fetching bot settings')
        worksheet_bot_settings = sheet.worksheet("_BotSettings")
        bot_settings = _dict_factory(
            worksheet_bot_settings.get_all_values(),
            _BOT_SETTINGS_HEADERS,
        )
        return bot_settings[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def _load_groups(self, sheet):
        logger.info('Setting reload: fetching groups')
        worksheet_groups = sheet.worksheet("Группы")
        groups = _dict_factory(
            worksheet_groups.get_all_values(),
            _GROUPS_HEADERS,
        )
        return groups[_IGNORE_FIRST_HEADER_ROWS_NUM:]

    def get_all_from_spreadsheet(self):
        logger.info('All reload')
        sheet = self._connect_to_google_sheets()
        groups = self._load_groups(sheet)
        problems = self._load_problems(sheet)
        students = self._load_students(sheet)
        teachers = self._load_teachers(sheet)
        ui_messages = self._load_ui_messages(sheet)
        bot_settings = self._load_bot_settings(sheet)
        return groups, problems, students, teachers, ui_messages, bot_settings

    def get_problems(self):
        logger.info('Problems reload')
        sheet = self._connect_to_google_sheets()
        problems = self._load_problems(sheet)
        return problems

    def get_students(self):
        logger.info('Students reload')
        sheet = self._connect_to_google_sheets()
        students = self._load_students(sheet)
        return students

    def get_teachers(self):
        logger.info('Problems reload')
        sheet = self._connect_to_google_sheets()
        teachers = self._load_teachers(sheet)
        return teachers

    def get_ui_messages(self):
        logger.info('Problems reload')
        sheet = self._connect_to_google_sheets()
        ui_messages = self._load_ui_messages(sheet)
        return ui_messages

    def get_bot_settings(self):
        logger.info('Problems reload')
        sheet = self._connect_to_google_sheets()
        bot_settings = self._load_bot_settings(sheet)
        return bot_settings

    def get_groups(self):
        logger.info('Groups reload')
        sheet = self._connect_to_google_sheets()
        groups = self._load_groups(sheet)
        return groups

    def close(self):
        if not self.client:
            return
        sessions = [
            getattr(self.client, "session", None),
            getattr(getattr(self.client, "http", None), "session", None),
            getattr(getattr(self.client, "request", None), "session", None),
        ]
        seen = set()
        for session in sessions:
            if not session or id(session) in seen:
                continue
            seen.add(id(session))
            try:
                session.close()
            except Exception:
                logger.warning('Failed to close Google Sheets session', exc_info=True)
        self.client = None


google_spreadsheet_loader = SpreadsheetLoader()

if __name__ == '__main__':
    logger.info('Обновляем дамп с данными из гугль-таблицы')
    from config import config

    google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
    groups, problems, students, teachers, ui_messages, bot_settings = google_spreadsheet_loader.get_all_from_spreadsheet()
    print(len(groups), len(problems), len(students), len(teachers))

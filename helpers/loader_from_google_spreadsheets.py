# -*- coding: utf-8 -*-
from helpers.config import logger

_IGNORE_FIRST_HEADER_ROWS_NUM = 2
_PROBLEMS_HEADERS = [
    'level', 'lesson', 'prob', 'item',
    'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error',
    'cor_ans', 'cor_ans_checker', 'wrong_ans', 'congrat',
]
_STUDENTS_HEADERS = ['surname', 'name', 'token', 'level', 'online']
_TEACHERS_HEADERS = ['surname', 'name', 'middlename', 'token', 'online']


def _dict_factory(rows, column_names):
    res_rows = []
    for row in rows:
        d = {}
        for col, val in zip(column_names, row):
            d[col] = val
        res_rows.append(d)
    return res_rows


class SpreadsheetLoader:
    def __init__(self, sheets_key: str = None, google_cred_json: str = None):
        self.sheets_key = sheets_key
        self.google_cred_json = google_cred_json

    def setup(self, sheets_key: str, google_cred_json: str):
        self.sheets_key = sheets_key
        self.google_cred_json = google_cred_json

    def _connect_to_google_sheets(self):
        logger.info('Setting reload: using google')
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.google_cred_json, scopes)
        client = gspread.authorize(creds)
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

    def get_all(self):
        logger.info('All reload')
        sheet = self._connect_to_google_sheets()
        problems = self._load_problems(sheet)
        students = self._load_students(sheet)
        teachers = self._load_teachers(sheet)
        return problems, students, teachers

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


google_spreadsheet_loader = SpreadsheetLoader()

if __name__ == '__main__':
    logger.info('Обновляем дамп с данными из гугль-таблицы')
    from config import config

    google_spreadsheet_loader.setup(config.google_sheets_key, config.google_cred_json)
    problems, students, teachers = google_spreadsheet_loader.get_all()
    print(len(problems), len(students), len(teachers))

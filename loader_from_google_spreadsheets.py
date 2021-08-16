# -*- coding: utf-8 -*-
import pickle
from config import logger

_IGNORE_FIRST_HEADER_ROWS_NUM = 2
_PROBLEMS_HEADERS = [
    'level', 'lesson', 'prob', 'item',
    'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error',
    'cor_ans', 'cor_ans_checker', 'wrong_ans', 'congrat',
]
_STUDENTS_HEADERS = ['surname', 'name', 'token', 'level']
_TEACHERS_HEADERS = ['surname', 'name', 'middlename', 'token']


def _dict_factory(rows, column_names):
    res_rows = []
    for row in rows:
        d = {}
        for col, val in zip(column_names, row):
            d[col] = val
        res_rows.append(d)
    return res_rows


class SpreadsheetLoader:
    def __init__(self, dump_filename: str = None, sheets_key: str = None, google_cred_json: str = None):
        self.dump_filename = dump_filename
        self.sheets_key = sheets_key
        self.google_cred_json = google_cred_json

    def setup(self, dump_filename: str, sheets_key: str, google_cred_json: str):
        self.dump_filename = dump_filename
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

    def _load_from_pickle(self):
        try:
            with open(self.dump_filename, 'rb') as f:
                pickled = pickle.load(f)
            logger.info('Setting reload: pickle used')
            return pickled
        except FileNotFoundError:
            return None

    def _dump_to_pickle(self, pickled):
        logger.info('Setting reload: DONE')
        with open(self.dump_filename, 'wb') as f:
            pickle.dump(pickled, f)

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

    def get_all(self, *, use_pickle=True):
        if use_pickle:
            logger.info('Setting reload: check pickle')
            pickled = self._load_from_pickle()
            if pickled:
                problems, students, teachers = pickled
                return problems, students, teachers
        sheet = self._connect_to_google_sheets()
        problems = self._load_problems(sheet)
        students = self._load_students(sheet)
        teachers = self._load_teachers(sheet)
        pickled = problems, students, teachers
        self._dump_to_pickle(pickled)
        return problems, students, teachers

    def get_problems(self):
        logger.info('Problems reload: check pickle')
        sheet = self._connect_to_google_sheets()
        problems_new = self._load_problems(sheet)
        problems, students, teachers = self._load_from_pickle()
        pickled = problems_new, students, teachers
        self._dump_to_pickle(pickled)
        return problems

    def get_students(self):
        logger.info('Students reload: check pickle')
        sheet = self._connect_to_google_sheets()
        students_new = self._load_students(sheet)
        problems, students, teachers = self._load_from_pickle()
        pickled = problems, students_new, teachers
        self._dump_to_pickle(pickled)
        return students

    def get_teachers(self):
        logger.info('Problems reload: check pickle')
        sheet = self._connect_to_google_sheets()
        teachers_new = self._load_teachers(sheet)
        problems, students, teachers = self._load_from_pickle()
        pickled = problems, students, teachers_new
        self._dump_to_pickle(pickled)
        return teachers


google_spreadsheet_loader = SpreadsheetLoader()

if __name__ == '__main__':
    logger.info('Обновляем дамп с данными из гугль-таблицы')
    from config import config

    google_spreadsheet_loader.setup(config.dump_filename, config.google_sheets_key, config.google_cred_json)
    problems, students, teachers = google_spreadsheet_loader.get_all(use_pickle=False)
    print(len(problems), len(students), len(teachers))

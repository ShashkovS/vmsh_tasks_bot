# -*- coding: utf-8 -*-
import pickle
import logging
import os

if os.environ.get('PROD', None) == 'true':
    DUMP_FILENAME = 'students_and_probles_v2_prod.pickle'
    sheets_key = open('creds_prod/settings_sheet_key_prod').read()
    google_cred_json = 'creds_prod/vmsh_bot_sheets_creds_prod.json'
elif os.environ.get('EXAM', None) == 'true':
    DUMP_FILENAME = 'students_and_probles_v2_exam.pickle'
    sheets_key = open('creds_exam_prod/settings_sheet_key_prod').read()
    google_cred_json = 'creds_exam_prod/vmsh_bot_sheets_creds_prod.json'
else:
    DUMP_FILENAME = 'students_and_probles_v2.pickle'
    try:
        sheets_key = open('creds/settings_sheet_key').read()
    except:
        print('Запишите API-ключ гугловой таблицы в creds/settings_sheet_key')
    google_cred_json = 'creds/vmsh_bot_sheets_creds.json'


def _dict_factory(rows, column_names):
    res_rows = []
    for row in rows:
        d = {}
        for col, val in zip(column_names, row):
            d[col] = val
        res_rows.append(d)
    return res_rows


def load(*, use_pickle=True):
    if use_pickle:
        logging.info('Setting reload: check pickle')
        try:
            with open(DUMP_FILENAME, 'rb') as f:
                problems, students, teachers = pickle.load(f)
            logging.info('Setting reload: pickle used')
            return problems, students, teachers
        except FileNotFoundError:
            pass

    logging.info('Setting reload: using google')
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(google_cred_json, scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheets_key)

    worksheet_problems = sheet.worksheet("Задачи")
    logging.info('Setting reload: fetching problems')
    problems = _dict_factory(
        worksheet_problems.get_all_values(),
        ['level', 'lesson', 'prob', 'item', 'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error', 'cor_ans', 'cor_ans_checker',
         'wrong_ans', 'congrat', ],
    )

    logging.info('Setting reload: fetching students')
    worksheet_students = sheet.worksheet("Школьники")
    students = _dict_factory(
        worksheet_students.get_all_values(),
        ['surname', 'name', 'token', 'level'],
    )

    logging.info('Setting reload: fetching teachers')
    worksheet_students = sheet.worksheet("Учителя")
    teachers = _dict_factory(
        worksheet_students.get_all_values(),
        ['surname', 'name', 'middlename', 'token'],
    )

    logging.info('Setting reload: DONE')
    result = problems[2:], students[2:], teachers[2:]
    with open(DUMP_FILENAME, 'wb') as f:
        pickle.dump(result, f)
    return result


def load_teachers():
    logging.info('Setting reload: using google')
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(google_cred_json, scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheets_key)
    logging.info('Setting reload: fetching teachers')
    worksheet_students = sheet.worksheet("Учителя")
    teachers = _dict_factory(
        worksheet_students.get_all_values(),
        ['surname', 'name', 'middlename', 'token'],
    )
    logging.info('Setting reload: DONE')
    return teachers[2:]


def load_problems():
    logging.info('Setting reload: using google')
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(google_cred_json, scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheets_key)
    logging.info('Setting reload: fetching teachers')
    worksheet_problems = sheet.worksheet("Задачи")
    logging.info('Setting reload: fetching problems')
    problems = _dict_factory(
        worksheet_problems.get_all_values(),
        ['level', 'lesson', 'prob', 'item', 'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error', 'cor_ans', 'cor_ans_checker',
         'wrong_ans', 'congrat', ],
    )
    logging.info('Setting reload: DONE')
    return problems[2:]


if __name__ == '__main__':
    # problems, students, teachers = load()
    # print(problems)
    # print(students)
    # print(teachers)

    # teachers = load_teachers()
    # print(teachers)

    problems = load_problems()
    print(problems)

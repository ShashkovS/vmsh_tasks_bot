# -*- coding: utf-8 -*-

def _dict_factory(rows, column_names):
    res_rows = []
    for row in rows:
        d = {}
        for col, val in zip(column_names, row):
            d[col] = val
        res_rows.append(d)
    return res_rows


def load():
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('creds/vmsh_bot_sheets_creds.json', scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('1mw9yuCYABGiIF5WXcTE6jAi0l1UtcnTA2jlO7SDHN6Y')

    worksheet_problems = sheet.worksheet("Задачи")
    problems = _dict_factory(
        worksheet_problems.get_all_values(),
        ['list', 'prob', 'item', 'title', 'prob_text', 'prob_type', 'ans_type', 'ans_validation', 'validation_error', 'cor_ans', 'cor_ans_checker',
         'wrong_ans', 'congrat', ],
    )

    worksheet_students = sheet.worksheet("Школьники")
    students = _dict_factory(
        worksheet_students.get_all_values(),
        ['surname', 'name', 'token'],
    )

    worksheet_students = sheet.worksheet("Учителя")
    teachers = _dict_factory(
        worksheet_students.get_all_values(),
        ['surname', 'name', 'middlename', 'token'],
    )

    return problems[2:], students[2:], teachers[2:]


if __name__ == '__main__':
    problems, students, teachers = load()
    print(problems)
    print(students)
    print(teachers)

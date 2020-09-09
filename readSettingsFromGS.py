import gspread
from oauth2client.service_account import ServiceAccountCredentials

scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('creds/vmsh_bot_sheets_creds.json', scopes)

problems = []
students = []


def load():
    global problems, students
    client = gspread.authorize(creds)
    sheet = client.open_by_key('1mw9yuCYABGiIF5WXcTE6jAi0l1UtcnTA2jlO7SDHN6Y')

    worksheet_problems = sheet.worksheet("Задачи")
    problems = worksheet_problems.get('A:E')

    worksheet_students = sheet.worksheet("Школьники")
    students = worksheet_students.get('A:D')


if __name__ == '__main__':
    load()
    print(problems)
    print(students)
from urllib.parse import urlencode

parms = {
    'studentId': 123,
    'problemId': 15,
    'teacherId': 74,
    'displayName': 'Иван Сергеевич Петров',
}
print(f"https://www.shashkovs.ru/jitboard.html?{urlencode(parms)}")

parms['displayName'] = 'Коля Звякин'
print(f"https://www.shashkovs.ru/jitboard.html?{urlencode(parms)}")


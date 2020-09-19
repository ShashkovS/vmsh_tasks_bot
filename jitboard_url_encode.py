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


for i in range(10):
    parms = {
        'studentId': i,
        'problemId': 15,
        'teacherId': 1000+i,
        'displayName': f'Препод {i}',
    }
    print(f"Препод {i}: https://www.shashkovs.ru/jitboard.html?{urlencode(parms)}")
    parms['displayName'] = f'Школьник {i}',
    print(f"Школьник {i}: https://www.shashkovs.ru/jitboard.html?{urlencode(parms)}")


import sqlite3
import re
import pyperclip

NLIST = 3

conn = sqlite3.connect(r'db\88b1047644e68c3cceb7ff21e1190a90.db')
cur = conn.cursor()

cur.execute('''
    select distinct
    u.token || '	' || u.surname || '	' || u.name as user,
    p.list || '.' || p.prob  || p.item as prob
    from users u 
    join results r on r.student_id = u.id 
    join problems p on r.problem_id = p.id
    where r.verdict > 0 and (u.type = 1 and token not like 'pass%')
    and p.list = 3
''')
rows = set(cur.fetchall())

cur.execute('''
    select u.token || '	' || u.surname || '	' || u.name as user
    from users u 
    where u.type = 1 and token not like 'pass%'
    order by u.surname, u.name, u.token
''')
pupils = [x[0] for x in cur.fetchall()]

cur.execute('''
    select p.list || '.' || p.prob  || p.item as prob
    from problems p
    where p.list = :NLIST
''', globals())
problems = set({x[0] for x in cur.fetchall()})

formated_problems = []
for problem in problems:
    m = re.fullmatch('(\d+)\.(\d+)([а-я]?)', problem)
    lst, prb, itm = m.groups()
    formated_problems.append((f'{int(lst):02}.{int(prb):02}{itm}', problem))
formated_problems.sort()
table = [[''] * (len(problems) + 1) for __ in range(len(pupils) + 1)]
table[0][0] = 'token\tФамилия\tИмя'
for c, (formatted, problem) in enumerate(formated_problems, start=1):
    table[0][c] = formatted
for r, pupil in enumerate(pupils, start=1):
    table[r][0] = pupil

for r, pupil in enumerate(pupils, start=1):
    for c, (formatted, problem) in enumerate(formated_problems, start=1):
        table[r][c] = '1' if (pupil, problem) in rows else ''

stable = '\n'.join('\t'.join(row) for row in table)
pyperclip.copy(stable)
print(stable)

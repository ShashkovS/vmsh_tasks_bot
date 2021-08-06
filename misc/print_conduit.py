import sqlite3
import re
import pyperclip

NLIST = 7
NLEVEL = ''
FOR_MAILS = 1  # 1/0

conn = sqlite3.connect(r'db\88b1047644e68c3cceb7ff21e1190a90.db')
cur = conn.cursor()

cur.execute('''
    select distinct
    u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
    p.lesson || p.level || '.' || p.prob  || p.item as prob,
    max(r.verdict)
    from users u 
    join results r on r.student_id = u.id 
    join problems p on r.problem_id = p.id
    where (u.type = 1 and token not like 'pass%') and p.lesson = :NLIST and 
    (p.level = :NLEVEL or ''=:NLEVEL) 
    group by 1, 2
''', globals())
results = {(r[0], r[1]): str(max(r[2], 0)) for r in cur.fetchall()}
print(len(results))

cur.execute('''
    select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
    from users u 
    where u.type = 1 and token not like 'pass%'
    order by u.surname, u.name, u.token
''')
pupils = [x[0] for x in cur.fetchall()]




cur.execute('''
    select p.lesson || p.level || '.' || p.prob  || p.item as prob
    from problems p
    where p.lesson = :NLIST and (p.level = :NLEVEL or ''=:NLEVEL)
''', globals())
Problem = set({x[0] for x in cur.fetchall()})

formated_problems = []
for problem in Problem:
    m = re.fullmatch('(\d+)([а-я])\.(\d+)([а-я]?)', problem)
    lst, lvl, prb, itm = m.groups()
    formated_problems.append((f'{int(lst):02}{lvl}.{int(prb):02}{itm}', problem))
formated_problems.sort()
table = [[''] * (len(Problem) + 2) for __ in range(len(pupils) + 1)]
table[0][0] = 'token\tФамилия\tИмя\tнач/прод'
table[0][1] = f'{NLIST:02}{NLEVEL}.Н'
for c, (formatted, problem) in enumerate(formated_problems, start=2):
    if FOR_MAILS:
        formatted = formatted.strip('cс').lstrip('0')
        formatted = formatted if '.' not in formatted else formatted[formatted.find('.')+1:].strip('cс').lstrip('0')
        formatted = 'c' + formatted
    table[0][c] = formatted
for r, pupil in enumerate(pupils, start=1):
    table[r][0] = pupil


for r, pupil in enumerate(pupils, start=1):
    for c, (formatted, problem) in enumerate(formated_problems, start=2):
        table[r][c] = results.get((pupil, problem), '')
    table[r][1] = '1' if any(table[r][2:]) else ''

startFrom = 0 if FOR_MAILS else 1
stable = '\n'.join('\t'.join(row[startFrom:]) for row in table if not FOR_MAILS or any(row[1:]))
pyperclip.copy(stable)
print(stable)

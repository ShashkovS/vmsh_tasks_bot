import sqlite3
import re

conn = sqlite3.connect(r'db\88b1047644e68c3cceb7ff21e1190a90.db')
cur = conn.cursor()

# cur.execute('''
#     select distinct
#     u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
#     p.lesson || p.level || '.' || p.prob  || p.item as prob,
#     max(r.verdict)
#     from users u
#     join results r on r.student_id = u.id
#     join problems p on r.problem_id = p.id
#     where (u.type = 1 and token not like 'pass%')
#     group by 1, 2
# ''', globals())
# results = {(r[0], r[1]): str(max(r[2], 0)) for r in cur.fetchall()}
#
# cur.execute('''
#     select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
#     from users u
#     where u.type = 1 and token not like 'pass%'
#     order by u.surname, u.name, u.token
# ''')
# pupils = [x[0] for x in cur.fetchall()]

def fmt_probname(prob):
    m = re.fullmatch('(\d+)([а-я])\.(\d+)([а-я]?)', prob)
    lst, lvl, prb, itm = m.groups()
    return f'{int(lst):02}{lvl}.{int(prb):02}{itm}'


cur.execute('''
    select p.id, p.lesson || p.level || '.' || p.prob  || p.item as prob
    from problems p
''', globals())
Problem = {fmt_probname(x[1]): x[0] for x in cur.fetchall()}
print(Problem)
exit()

formated_problems = []
for problem in Problem:
    m = re.fullmatch('(\d+)([а-я])\.(\d+)([а-я]?)', problem)
    lst, lvl, prb, itm = m.groups()
    formated_problems.append((f'{int(lst):02}{lvl}.{int(prb):02}{itm}', problem))
formated_problems.sort()
table = [[''] * (len(Problem) + 1) for __ in range(len(pupils) + 1)]
table[0][0] = 'token\tФамилия\tИмя\tнач/прод'
for c, (formatted, problem) in enumerate(formated_problems, start=1):
    table[0][c] = formatted
for r, pupil in enumerate(pupils, start=1):
    table[r][0] = pupil

token_to_pupil = {}
for pupil in pupils:
    token, *__ = pupil.split('\t')
    token_to_pupil[token] = pupil
print(pupils)

from db_methods import db

def get_lessons_and_levels(cur):
    cur.execute('''
        select lesson, r.level, count(*) cnt
        from results r
        join users u on r.student_id = u.id
        where u.type = 1
          and u.level = r.level
          and u.surname not like 'ЯЯ%' and u.name not like 'ЯЯ%'
        group by 1, 2
        order by 1 desc, 2;
    ''')
    return cur.fetchall()


def get_results(cur, lesson, level, show_answers=False):
    if show_answers:
        verd = "GROUP_CONCAT(r.answer, '  |  ')"
    else:
        verd = 'max(r.verdict)'
    cur.execute(f'''
        select
        u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob,
        {verd} as max_verdict
        from users u 
        join results r on r.student_id = u.id
        join problems p on r.problem_id = p.id
        where u.type = 1 and u.level = :level and r.level = :level and r.lesson = :lesson
              and u.surname not like 'ЯЯ%' and u.name not like 'ЯЯ%' 
        group by 1, 2
    ''', locals())
    if show_answers:
        results = {(r['user'], r['full_prob']): r['max_verdict'] for r in cur.fetchall()}
    else:
        results = {(r['user'], r['full_prob']): str(max(r['max_verdict'], 0)) for r in cur.fetchall()}
    return results


def get_pupils(cur, level):
    cur.execute('''
        select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
        from users u 
        where u.type = 1 -- and token not like 'pass%'
        and u.level = :level
        and u.surname not like 'ЯЯ%'
        and u.name not like 'ЯЯ%'
        order by u.level, u.surname, u.name, u.token
    ''', locals())
    pupils = [x['user'] for x in cur.fetchall()]
    return pupils


def get_problems(cur, lesson, level):
    cur.execute('''
        select p.lesson, p.level, p.prob, p.item,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob
        from problems p
        where p.lesson = :lesson and p.level = :level
        order by p.lesson, p.level, p.prob, p.item
    ''', locals())
    problems = cur.fetchall()
    return problems


def create_conduit_table(problems, pupils, results):
    t_rows = 1 + len(pupils)
    t_cols = 3 + len(problems)
    table = [[''] * t_cols for __ in range(t_rows)]
    # Заполняем заголовочную строчку
    table[0][:3] = ['token', 'Фамилия', 'Имя']
    # Заполняем заголовочные столбцы
    for r, pupil in enumerate(pupils, start=1):
        table[r][0:3] = pupil.split('\t')[:3]
    # Заполняем заголовочную строку
    for col, problem in enumerate(problems, start=3):
        table[0][col] = problem['full_prob']
    # Теперь заполняем всю таблицу целиком
    for r, pupil in enumerate(pupils, start=1):
        for col, problem in enumerate(problems, start=3):
            table[r][col] = results.get((pupil, problem["full_prob"]), '')
    return table


def table_to_html(tables):
    styles = '''
<style>
.res {
  font-family: Arial, Helvetica, sans-serif;
  border-collapse: collapse;
  white-space:nowrap;
}
.res td, .res th {
  border: 1px solid #ddd;
  padding: 0px;
}
.res tr:nth-child(even){background-color: #f2f2f2;}
.res tr:hover {background-color: #ddd;}
.res th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: left;
  background-color: #04AA6D;
  color: white;
}
</style>
'''
    html = ['<!DOCTYPE html>', '<meta charset="utf-8">', '<head>', styles, '</head>', '<body>']
    for table in tables:
        html.append('<table class="res">')
        html.append('<tr><th>' + '</th><th>'.join(table[0]) + '</th></tr>')
        for i in range(1, len(table)):
            row = table[i]
            html.append('<tr><td>' + '</td><td>'.join(map(str, row)) + '</th></tr>')
        html.append('</table>')
        html.append('<hr style="margin:2rem;">')
    html.extend(['</table>', '</body>', '</html>'])
    html = '\n'.join(html)
    return html


def get_html():
    cur = db.conn.cursor()
    lessons_and_levels = get_lessons_and_levels(cur)
    tables = []
    for row in lessons_and_levels:
        lesson, level = row['lesson'], row['level']
        pupils = get_pupils(cur, level)
        problems = get_problems(cur, lesson, level)
        results = get_results(cur, lesson, level, show_answers=False)
        table = create_conduit_table(problems, pupils, results)
        tables.append(table)
        results = get_results(cur, lesson, level, show_answers=True)
        table = create_conduit_table(problems, pupils, results)
        tables.append(table)
    html = table_to_html(tables)
    return html

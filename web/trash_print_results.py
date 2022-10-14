from db_methods import db


def get_results(cur):
    cur.execute('''
        select distinct
        u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob,
        max(r.verdict) as max_verdict
        from users u 
        join (select level, max(lesson) as lesson from lessons group by level) as last  
        join results r on r.student_id = u.id and u.level = last.level and r.lesson = last.lesson
        join problems p on r.problem_id = p.id
        where (u.type = 1 and token not like 'pass%' and token not like 'qwerty%') 
        -- and p.lesson = :NLIST
        group by 1, 2
    ''', globals())
    results = {(r['user'], r['full_prob']): str(max(r['max_verdict'], 0)) for r in cur.fetchall()}
    return results


def get_pupils(cur):
    cur.execute('''
        select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
        from users u 
        where u.type = 1 and token not like 'pass%'
        order by u.level, u.surname, u.name, u.token
    ''')
    pupils = [x['user'] for x in cur.fetchall()]
    return pupils


def get_problems(cur):
    cur.execute('''
        select p.lesson, p.level, p.prob, p.item,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob
        from problems p
        join (select level, max(lesson) as lesson from lessons group by level) as last on p.level = last.level and p.lesson = last.lesson  
        -- where p.lesson = :NLIST
        order by p.lesson, p.level, p.prob, p.item
    ''', globals())
    problems = cur.fetchall()
    return problems


def create_conduit_table(problems, pupils, results):
    t_rows = len(pupils) + 1

    n_level = [problem for problem in problems if problem['level'] == 'н']
    p_level = [problem for problem in problems if problem['level'] == 'п']
    x_level = [problem for problem in problems if problem['level'] == 'э']

    t_cols = 1 + len(n_level) + len(p_level) + len(x_level) + 5

    table = [[''] * t_cols for __ in range(t_rows)]

    # Заполняем заголовочную строчку
    table[0][:3] = ['Фамилия', 'Имя', 'уровень']
    # Заполняем заголовочный столбец (он для отладки)
    for r, pupil in enumerate(pupils, start=1):
        table[r][0:3] = pupil.split('\t')[1:]

    nH_col = 3
    pH_col = 3 + len(n_level)
    xH_col = 3 + len(n_level) + len(p_level)

    table[0][nH_col] = f'н.Н'
    for i in range(1, len(n_level) + 1):
        table[0][nH_col + i] = n_level[i - 1]['full_prob']
    table[0][pH_col] = f'п.Н'
    for i in range(1, len(p_level) + 1):
        table[0][pH_col + i] = p_level[i - 1]['full_prob']
    table[0][xH_col] = f'э.Н'
    for i in range(1, len(x_level) + 1):
        table[0][xH_col + i] = x_level[i - 1]['full_prob']
    for c, problem in enumerate(n_level, start=1):
        table[0][nH_col + c] = f'{problem["lesson"]:02}{problem["level"]}.{problem["prob"]:02}{problem["item"]}'
    for c, problem in enumerate(p_level, start=1):
        table[0][pH_col + c] = f'{problem["lesson"]:02}{problem["level"]}.{problem["prob"]:02}{problem["item"]}'
    for c, problem in enumerate(x_level, start=1):
        table[0][xH_col + c] = f'{problem["lesson"]:02}{problem["level"]}.{problem["prob"]:02}{problem["item"]}'
    # Теперь заполняем всю таблицу целиком
    for r, pupil in enumerate(pupils, start=1):
        for c, problem in enumerate(n_level, start=1):
            table[r][nH_col + c] = results.get((pupil, problem["full_prob"]), '')
        for c, problem in enumerate(p_level, start=1):
            table[r][pH_col + c] = results.get((pupil, problem["full_prob"]), '')
        for c, problem in enumerate(x_level, start=1):
            table[r][xH_col + c] = results.get((pupil, problem["full_prob"]), '')
        nH = ''.join(table[r][nH_col + 1:nH_col + 1 + len(n_level)]).strip('')
        pH = ''.join(table[r][pH_col + 1:pH_col + 1 + len(p_level)]).strip('')
        xH = ''.join(table[r][xH_col + 1:xH_col + 1 + len(x_level)]).strip('')
        table[r][nH_col] = '1' if nH != '' and nH != '0' else ''
        table[r][pH_col] = '1' if pH != '' and pH != '0' else ''
        table[r][xH_col] = '1' if xH != '' and xH != '0' else ''
    return table


def table_to_html(table):
    styles = '''
<style>
#res {
  font-family: Arial, Helvetica, sans-serif;
  border-collapse: collapse;
  white-space:nowrap;
}
#res td, #res th {
  border: 1px solid #ddd;
  padding: 0px;
}
#res tr:nth-child(even){background-color: #f2f2f2;}
#res tr:hover {background-color: #ddd;}
#res th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: left;
  background-color: #04AA6D;
  color: white;
}
</style>
'''
    html = ['<!DOCTYPE html>', '<meta charset="utf-8">', '<head>', styles, '</head>', '<body>', '<table id="res">']
    html.append('<tr><th>' + '</th><th>'.join(table[0]) + '</th></tr>')
    for i in range(1, len(table)):
        row = table[i]
        html.append('<tr><td>' + '</td><td>'.join(row) + '</th></tr>')
    html.extend(['</table>', '</body>', '</html>'])
    html = '\n'.join(html)
    return html


def get_html():
    cur = db.conn.cursor()
    results = get_results(cur)
    pupils = get_pupils(cur)
    problems = get_problems(cur)
    table = create_conduit_table(problems, pupils, results)
    html = table_to_html(table)
    return html

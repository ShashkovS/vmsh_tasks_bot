import db_methods as db
from helpers.consts import VERDICT_VAL_DECODER
import html


def get_lessons_and_levels(cur):
    cur.execute('''
                select lesson, r.level, count(*) cnt
                from results r
                         join users u on r.student_id = u.id
                where u.type = 1
                  and u.level = r.level
                  and u.surname not like 'surname%'
                  and u.name not like 'surname%'
                group by 1, 2
                order by 1 desc, 2;
                ''')
    return cur.fetchall()


def get_results(cur, lesson, level, show_answers=False):
    if show_answers:
        verd = "GROUP_CONCAT(r.answer, '  |  ')"
    else:
        verd = 'max(v.val)'
    cur.execute(f'''
        select
        u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob,
        {verd} as max_verdict
        from users u 
        join results r on r.student_id = u.id
        join verdicts v on r.verdict = v.id
        join problems p on r.problem_id = p.id
        where u.type = 1 and u.level = :level and r.level = :level and r.lesson = :lesson
              and u.surname not like 'surname%' and u.name not like 'surname%' 
        group by 1, 2
    ''', locals())
    if show_answers:
        results = {(r['user'], r['full_prob']): r['max_verdict'] for r in cur.fetchall()}
    else:
        results = {(r['user'], r['full_prob']): VERDICT_VAL_DECODER.get(r['max_verdict'], str(r['max_verdict'])) for r
                   in cur.fetchall()}
    return results


def get_pupils(cur, level):
    cur.execute('''
                select u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user
                from users u
                where u.type = 1 -- and token not like 'pass%'
                  and u.level = :level
                  and u.surname not like 'surname%'
                  and u.name not like 'surname%'
                order by u.level, u.surname, u.name, u.token
                ''', locals())
    pupils = [x['user'] for x in cur.fetchall()]
    return pupils


def get_problems(cur, lesson, level):
    cur.execute('''
                select p.lesson,
                       p.level,
                       p.prob,
                       p.item,
                       p.lesson || p.level || '.' || p.prob || p.item as full_prob
                from problems p
                where p.lesson = :lesson
                  and p.level = :level
                order by p.lesson, p.level, p.prob, p.item
                ''', locals())
    problems = cur.fetchall()
    return problems


def create_conduit_table(problems, pupils, results):
    t_rows = 1 + len(pupils)
    t_cols = 3 + len(problems)
    table = [[''] * t_cols for __ in range(t_rows)]
    # Заполняем заголовочную строчку
    table[0][:3] = ['Фамилия', 'Имя', 'уровень']
    # Заполняем заголовочные столбцы
    for r, pupil in enumerate(pupils, start=1):
        table[r][0:3] = pupil.split('\t')[1:]
    # Заполняем заголовочную строку
    for col, problem in enumerate(problems, start=3):
        table[0][col] = problem['full_prob']
    # Теперь заполняем всю таблицу целиком
    for r, pupil in enumerate(pupils, start=1):
        for col, problem in enumerate(problems, start=3):
            val = results.get((pupil, problem["full_prob"]), '')
            if val is None:  # Replace None with 'img'
                val = 'img'
            table[r][col] = val
    return table


def table_to_html(tables, show_answers_flags):
    styles = '''
<style>
.res {
  font-family: Arial, Helvetica, sans-serif;
  border-collapse: collapse;
}
.res td, .res th {
  border: 1px solid #ddd;
  padding: 0 4px; /* Added horizontal padding, removed vertical */
}
.res th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: left;
  background-color: #04AA6D;
  color: white;
}
.res tr:nth-child(even){background-color: #f2f2f2;}
.res tr:hover {background-color: #ddd;}
/* Styles for tables showing verdicts */
.verdict-table td {
  text-align: center; /* Center align content in verdict tables */
  white-space: nowrap; /* Prevent wrapping in verdict tables */
}
.verdict-table .plus {
  background-color: #D4EDDA; /* Light green for '+' */
}
.verdict-table .minus {
  background-color: #F8D7DA; /* Light red for '-' */
}
/* Styles for tables showing answers */
.answer-table td {
  white-space: normal; /* Allow text wrap in answer tables */
  word-wrap: break-word; /* Break long words */
  max-width: 40%; /* Optional: set a max-width for answer columns */
}
.answer-table td.break-on-pipe {
    white-space: normal;
    word-break: break-all; /* Allow breaking anywhere */
}
/* Align name and surname to the left */
.res td:nth-child(1), .res td:nth-child(2) {
  text-align: left;
}
</style>
'''
    html_output = ['<!DOCTYPE html>', '<meta charset="utf-8">', '<head>', styles, '</head>', '<body>']
    for i, table in enumerate(tables):
        is_answer_table = show_answers_flags[i]
        table_class = "res " + ("answer-table" if is_answer_table else "verdict-table")

        html_output.append(f'<table class="{table_class}">')
        html_output.append('<thead><tr><th>' + '</th><th>'.join(map(html.escape, table[0])) + '</th></tr></thead>')
        html_output.append('<tbody>')
        for r in range(1, len(table)):
            row = table[r]
            row_html_cells = []
            for col_idx, cell_value in enumerate(row):
                escaped_value = html.escape(str(cell_value))  # HTML escape all values

                cell_class = ""
                if not is_answer_table and col_idx >= 3:  # Apply conditional styling only for verdict tables and problem columns
                    if cell_value == '+':
                        cell_class = "plus"
                    elif cell_value in ('-', '−'):
                        cell_class = "minus"

                # Handle wrapping for answers with '|'
                if is_answer_table and '|' in escaped_value:
                    escaped_value = escaped_value.replace('  |  ', '<br>').replace('|', '<br>')
                    cell_class += " break-on-pipe" if cell_class else "break-on-pipe"

                row_html_cells.append(f'<td class="{cell_class.strip()}">{escaped_value}</td>')
            html_output.append('<tr>' + ''.join(row_html_cells) + '</tr>')
        html_output.append('</tbody>')
        html_output.append('</table>')
        html_output.append('<hr style="margin:2rem;">')
    html_output.extend(['</body>', '</html>'])
    html_output = '\n'.join(html_output)
    return html_output


def get_html():
    cur = db.sql.conn.cursor()
    lessons_and_levels = get_lessons_and_levels(cur)
    tables = []
    show_answers_flags = []
    for row in lessons_and_levels:
        lesson, level = row['lesson'], row['level']
        pupils = get_pupils(cur, level)
        problems = get_problems(cur, lesson, level)

        # Table for verdicts (plusses and minuses)
        results_verdicts = get_results(cur, lesson, level, show_answers=False)
        table_verdicts = create_conduit_table(problems, pupils, results_verdicts)
        tables.append(table_verdicts)
        show_answers_flags.append(False)  # Flag for verdict table

        # Table for answers
        results_answers = get_results(cur, lesson, level, show_answers=True)
        table_answers = create_conduit_table(problems, pupils, results_answers)
        tables.append(table_answers)
        show_answers_flags.append(True)  # Flag for answer table

    html_output = table_to_html(tables, show_answers_flags)
    return html_output
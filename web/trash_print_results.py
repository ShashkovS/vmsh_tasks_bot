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


def get_results(cur, lesson, level):
    cur.execute(f'''
        select
        u.token || '	' || u.surname || '	' || u.name || '	' || u.level as user,
        p.lesson || p.level || '.' || p.prob  || p.item as full_prob,
        max(v.val) as max_verdict,
        GROUP_CONCAT(r.answer, '  |  ') as all_answers
        from users u 
        join results r on r.student_id = u.id
        join verdicts v on r.verdict = v.id
        join problems p on r.problem_id = p.id
        where u.type = 1 and u.level = :level and r.level = :level and r.lesson = :lesson
              and u.surname not like 'surname%' and u.name not like 'surname%' 
        group by 1, 2
    ''', locals())
    results = {(r['user'], r['full_prob']): (r['max_verdict'], r['all_answers']) for r in cur.fetchall()}
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


def create_conduit_table_verdicts(problems, pupils, results):
    t_rows = 1 + len(pupils)
    t_cols = 3 + len(problems)
    table = [[''] * t_cols for __ in range(t_rows)]
    table[0][:3] = ['Фамилия', 'Имя', 'уровень']
    for r, pupil in enumerate(pupils, start=1):
        table[r][0:3] = pupil.split('\t')[1:]
    for col, problem in enumerate(problems, start=3):
        table[0][col] = problem['full_prob']
    for r, pupil in enumerate(pupils, start=1):
        for col, problem in enumerate(problems, start=3):
            val = results.get((pupil, problem["full_prob"]))
            if val is not None:
                verdict_val = val[0]
                table[r][col] = VERDICT_VAL_DECODER.get(verdict_val, str(verdict_val))
    return table


def create_conduit_table_answers(problems, pupils, results):
    t_rows = 1 + len(pupils)
    t_cols = 3 + len(problems)
    table_data = [[''] * t_cols for __ in range(t_rows)]
    table_classes = [[''] * t_cols for __ in range(t_rows)]

    table_data[0][:3] = ['Фамилия', 'Имя', 'уровень']
    for r, pupil in enumerate(pupils, start=1):
        table_data[r][0:3] = pupil.split('\t')[1:]
    for col, problem in enumerate(problems, start=3):
        table_data[0][col] = problem['full_prob']

    for r, pupil in enumerate(pupils, start=1):
        for col, problem in enumerate(problems, start=3):
            val = results.get((pupil, problem["full_prob"]))
            if val is None:
                table_data[r][col] = ''
                table_classes[r][col] = ''
            else:
                verdict_val, all_answers = val
                if all_answers is None:
                    table_data[r][col] = 'img'  # Assuming None means an image was sent
                else:
                    table_data[r][col] = all_answers

                # Apply highlight classes based on verdict
                if verdict_val == 1.0:
                    table_classes[r][col] = "plus"
                elif verdict_val == 0.0:
                    table_classes[r][col] = "minus"
                elif verdict_val > 0.0:  # Any partial credit
                    table_classes[r][col] = "partial-credit"
    return table_data, table_classes


def table_to_html(tables_and_classes):
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
.answer-table .plus {
    background-color: #D4EDDA; /* Light green for '+' */
}
.answer-table .minus {
    background-color: #F8D7DA; /* Light red for '-' */
}
.answer-table .partial-credit {
    background-color: #FFF3CD; /* Light yellow for partial credit */
}
/* Align name and surname to the left */
.res td:nth-child(1), .res td:nth-child(2) {
  text-align: left;
}
</style>
'''
    html_output = ['<!DOCTYPE html>', '<meta charset="utf-8">', '<head>', styles, '</head>', '<body>']

    for i, (table_data, table_classes, is_answer_table) in enumerate(tables_and_classes):
        table_class = "res " + ("answer-table" if is_answer_table else "verdict-table")

        html_output.append(f'<table class="{table_class}">')
        html_output.append('<thead><tr><th>' + '</th><th>'.join(map(html.escape, table_data[0])) + '</th></tr></thead>')
        html_output.append('<tbody>')
        for r in range(1, len(table_data)):
            row_data = table_data[r]
            row_class = table_classes[r] if is_answer_table else [''] * len(
                row_data)  # Use row_class for answer table, or empty for verdict table
            row_html_cells = []
            for col_idx, cell_value in enumerate(row_data):
                escaped_value = html.escape(str(cell_value))  # HTML escape all values

                cell_class = row_class[
                    col_idx] if is_answer_table and col_idx >= 3 else ""  # Start with the answer highlight class if it's an answer table

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
    tables_and_classes = []

    for row in lessons_and_levels:
        lesson, level = row['lesson'], row['level']
        pupils = get_pupils(cur, level)
        problems = get_problems(cur, lesson, level)

        results = get_results(cur, lesson, level)

        # Table for verdicts (plusses and minuses)
        table_verdicts = create_conduit_table_verdicts(problems, pupils, results)
        tables_and_classes.append((table_verdicts, None, False))  # No specific classes for verdict table cells

        # Table for answers, with highlighting
        table_answers_data, table_answers_classes = create_conduit_table_answers(problems, pupils, results)
        tables_and_classes.append((table_answers_data, table_answers_classes, True))

    html_output = table_to_html(tables_and_classes)
    return html_output
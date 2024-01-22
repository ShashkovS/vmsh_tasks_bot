# -*- coding: utf-8 -*-.
import db_methods as db


def calc_violin_plot_data(cursor):
    # cursor.execute('''
    #     -- Число задач студентов по занятиям
    #     select lesson, s.student_id, s.level, sum(score) sol
    #     from temp_real_problem_scores s
    #     group by 1, 2, 3
    #     order by lesson, level;
    # ''')
    cursor.execute('''
        -- Число задач студентов по занятиям
        select r.lesson, r.student_id, r.level, count(distinct problem_id) sol from results r
        join verdicts v on r.verdict = v.id
        where v.val > 0
        group by 1, 2, 3
        order by lesson, level;
    ''')
    per_lesson = {}
    for row in cursor.fetchall():
        lesson = row['lesson']
        if lesson not in per_lesson:
            per_lesson[lesson] = []
        per_lesson[lesson].append(row)
    per_lesson_v2 = {
        lesson: {
            'levels': [row['level'] for row in rows],
            'counts': [row['sol'] for row in rows],
        }
        for lesson, rows in per_lesson.items()
    }
    return per_lesson_v2


def calc_stat_table_data(cursor):
    # cursor.execute('''
    #     -- Статистика по задачам
    #     select p.lesson, p.level, p.lesson || p.level ||'.' || p.prob || p.item p, p.title,
    #     round(sum(score)) sol,
    #     (select count(distinct student_id) from results r where r.problem_id = p.id) tried,
    #     count(*) cnt
    #     from temp_real_problem_scores s
    #     join problems p on s.problem_id = p.id
    #     group by 1, 2, 3, 4
    #     order by p.lesson desc, s.level, p.prob, p.item
    #     ;
    # ''')
    cursor.execute('''
        -- Статистика по задачам
        with
        tot as (
            select r1.lesson, r1.level, count(distinct student_id) cnt
            from results r1
            group by 1, 2
        ),
        sol as (
            select r2.lesson, r2.level, r2.problem_id, count(distinct student_id) cnt
            from results r2
            join verdicts v2 on r2.verdict = v2.id
            where v2.val >= 0.9
            group by 1, 2, 3
        ),
        try as (
            select r3.lesson, r3.level, r3.problem_id, count(distinct student_id) cnt
            from results r3
            group by 1, 2, 3
        )
        select p.lesson, p.level, p.lesson || p.level ||'.' || p.prob || p.item p, p.title,
             ifnull(sol.cnt, 0) as sol,
             ifnull(try.cnt, 0) as tried,
             ifnull(tot.cnt, 0) as cnt
        from problems p
        left join tot on tot.lesson = p.lesson and tot.level = p.level
        left join sol on sol.lesson = p.lesson and sol.level = p.level and sol.problem_id = p.id
        left join try on try.lesson = p.lesson and try.level = p.level and try.problem_id = p.id
        order by p.lesson desc, p.level, p.prob, p.item
        ;
    ''')
    all_rows = cursor.fetchall()
    all_levels = set()
    levels = {row['level'] for row in all_rows}
    per_lesson_level = {}
    for row in all_rows:
        lesson = row['lesson']
        level = row['level']
        all_levels.add(level)
        if lesson not in per_lesson_level:
            per_lesson_level[lesson] = {level: [] for level in levels}
        per_lesson_level[lesson][level].append(row)
    all_levels = sorted(all_levels)
    return per_lesson_level, all_levels


html = '''
<!DOCTYPE html>
<meta charset="utf-8">
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.14.0/plotly.min.js"
            integrity="sha512-XDnqTWsAcVl16AYJoBHumISzIYThowGjR67jeL53NSp6tajsq2qf5UeAWvk1n6Hp3M2iMsV/ewhPScBiLCDs9Q==" crossorigin="anonymous"
            referrerpolicy="no-referrer"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.6.1/d3.min.js"
            integrity="sha512-MefNfAGJ/pEy89xLOFs3V6pYPs6AmUhXJrRlydI/9wZuGrqxmrdQ80zKHUcyadAcpH67teDZcBeS6oMJLPtTqw==" crossorigin="anonymous"
            referrerpolicy="no-referrer"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chroma-js/2.4.2/chroma.min.js"
            integrity="sha512-zInFF17qBFVvvvFpIfeBzo7Tj7+rQxLeTJDmbxjBz5/zIr89YVbTNelNhdTT+/DCrxoVzBeUPVFJsczKbB7sew==" crossorigin="anonymous"
            referrerpolicy="no-referrer"></script>
    <style>
        .n {
            background-color: rgb(183, 225, 205)
        }

        .p {
            background-color: rgb(252, 232, 178)
        }

        .x {
            background-color: rgb(244, 199, 195)
        }

        .y {
            background-color: rgb(180, 167, 214)
        }

        h3 {
            text-align: center;
            margin-bottom: 0;
        }

        td {
            padding: 0 3px
        }
    </style>
</head>
<body>
</body>
<script>
    // beginData
DATA
    // endData
    const levelDescr = {
        'н': 'Начинающие',
        'п': 'Продолжающие',
        'э': 'Эксперты',
    }
    const levelStyle = {
        'н': 'n',
        'п': 'p',
        'э': 'x',
    }

    function unpack(rows, key) {
        return rows.map(function (row) {
            return row[key];
        });
    }


    for (let lesson of lessons) {
        const div1 = document.createElement('div');
        div1.id = `violin${lesson}`;
        div1.style.maxWidth = '50rem';
        div1.style.margin = '0 auto';
        document.body.appendChild(div1);

        const data1 = [{
            type: 'violin',
            x: perLes[lesson].levels,
            y: perLes[lesson].counts,
            points: false,
            box: {
                visible: true,
                width: 0.3,
                line: {
                    width: 1,
                }
            },
            boxpoints: false,
            scalemode: 'width',
            line: {
                color: 'green',
            },
            meanline: {
                visible: true
            },
            opacity: 1.0,
            bandwidth: 0.5,
            hoveron: 'points',
            transforms: [{
                type: 'groupby',
                groups: perLes[lesson].levels,
                styles: [
                    {target: 'н', value: {line: {color: 'green'}}},
                    {target: 'п', value: {line: {color: 'orange'}}},
                    {target: 'э', value: {line: {color: 'red'}}},
                    {target: 'В', value: {line: {color: 'violet'}}}
                ]
            }]
        }]

        const layout = {
            hovermode: "closest",
            title: `Распределение по числу решённых задач, занятие ${lesson}`,
            yaxis: {
                zeroline: false,
                dtick: 1,
            },
        }
        Plotly.newPlot(div1.id, data1, layout);

        const colorer = chroma.scale(['#F8696B', '#FFEB84', '#63BE7B']).domain([0, 50, 100]).mode('lch');
        for (const level of all_levels) {
            const data2 = perProb[lesson][level];
            // Данные

            // Создаем таблицу
            const table = document.createElement('table');
            table.setAttribute('border', '1');
            table.style.borderCollapse = 'collapse';
            table.style.margin = '0.5em auto';
            table.style.padding = '0 2px';
            // Создаем заголовок таблицы
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            const headers = ['Задача', 'Название', 'Реш', 'Проб', 'Всего', 'Доля'];
            headers.forEach(headerText => {
                const th = document.createElement('th');
                th.innerText = headerText;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            const tbody = document.createElement('tbody');
            data2.forEach(rowData => {
                const row = document.createElement('tr');
                row.className = levelStyle[level];

                const taskCell = document.createElement('td');
                taskCell.innerText = rowData['p'];
                row.appendChild(taskCell);

                const titleCell = document.createElement('td');
                titleCell.innerText = rowData['title'];
                row.appendChild(titleCell);

                const ratio = (rowData['sol'] / rowData['cnt']) * 100;
                const tdColor = colorer(ratio).hex();

                const solCell = document.createElement('td');
                solCell.innerText = rowData['sol'];
                solCell.style.backgroundColor = tdColor;
                row.appendChild(solCell);

                const triedCell = document.createElement('td');
                triedCell.innerText = rowData['tried'];
                triedCell.style.backgroundColor = tdColor;
                row.appendChild(triedCell);

                const cntCell = document.createElement('td');
                cntCell.innerText = rowData['cnt'];
                cntCell.style.backgroundColor = tdColor;
                row.appendChild(cntCell);

                const shareCell = document.createElement('td');
                shareCell.innerText = `${ratio.toFixed(2)}%`;
                shareCell.style.backgroundColor = tdColor;
                row.appendChild(shareCell);
                tbody.appendChild(row);
            });
            table.appendChild(tbody);

            const div2 = document.createElement('div');
            div2.id = `tbl${lesson}`;
            div2.style.width = '100%';
            const header = document.createElement('h3');
            header.innerText = `${levelDescr[level]}, занятие ${lesson}`;
            div2.appendChild(header);
            div2.appendChild(table);
            document.body.appendChild(div2);
        }
    }
</script>
'''


def get_html():
    cursor = db.sql.conn.cursor()
    violin_plots_data = calc_violin_plot_data(cursor)
    table_data, all_levels = calc_stat_table_data(cursor)
    cursor.close()
    lessons = sorted(violin_plots_data.keys(), reverse=True)
    script = f'''
    const perProb = {table_data!r};
    const perLes = {violin_plots_data!r};
    const lessons = {lessons!r};
    const all_levels = {all_levels!r};
    '''
    return html.replace('DATA', script)

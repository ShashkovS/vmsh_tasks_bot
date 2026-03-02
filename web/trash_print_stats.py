# -*- coding: utf-8 -*-.
import json

import db_methods as db

STYLE_PALETTE = [
    '#e2f0d9',
    '#fff2cc',
    '#fce4d6',
    '#d9e1f2',
    '#f4cccc',
    '#d0e0e3',
    '#ead1dc',
    '#ddebf7',
    '#fde9d9',
    '#e6e6e6',
]
LINE_PALETTE = [
    '#2e7d32',
    '#ef6c00',
    '#c62828',
    '#283593',
    '#6a1b9a',
    '#00838f',
    '#ad1457',
    '#5d4037',
    '#455a64',
    '#1b5e20',
]


def calc_violin_plot_data(cursor):
    # cursor.execute('''
    #     -- Число задач студентов по занятиям
    #     select lesson, s.student_id, s.group_id, sum(score) sol
    #     from temp_real_problem_scores s
    #     group by 1, 2, 3
    #     order by lesson, group_id;
    # ''')
    cursor.execute('''
        -- Число задач студентов по занятиям
        select r.lesson, r.student_id, r.group_id, count(distinct problem_id) sol
        from results r
        join verdicts v on r.verdict = v.id
        join groups g on g.group_id = r.group_id
        where v.val > 0
          and r.group_id is not null
        group by 1, 2, 3, g.sort_order
        order by lesson, g.sort_order;
    ''')
    per_lesson = {}
    for row in cursor.fetchall():
        lesson = row['lesson']
        if lesson not in per_lesson:
            per_lesson[lesson] = []
        per_lesson[lesson].append(row)
    per_lesson_v2 = {
        lesson: {
            'group_ids': [row['group_id'] for row in rows],
            'counts': [row['sol'] for row in rows],
        }
        for lesson, rows in per_lesson.items()
    }
    return per_lesson_v2


def calc_stat_table_data(cursor):
    # cursor.execute('''
    #     -- Статистика по задачам
    #     select p.lesson, p.group_id, p.lesson || p.group_id ||'.' || p.prob || p.item p, p.title,
    #     round(sum(score)) sol,
    #     (select count(distinct student_id) from results r where r.problem_id = p.id) tried,
    #     count(*) cnt
    #     from temp_real_problem_scores s
    #     join problems p on s.problem_id = p.id
    #     group by 1, 2, 3, 4
    #     order by p.lesson desc, s.group_id, p.prob, p.item
    #     ;
    # ''')
    cursor.execute('''
        -- Статистика по задачам
        with
        sol as (
            select r2.lesson, r2.group_id, r2.problem_id, count(distinct student_id) cnt
            from results r2
            join verdicts v2 on r2.verdict = v2.id
            where v2.val >= 0.4
              and r2.group_id is not null
            group by 1, 2, 3
        ),
        try as (
            select r3.lesson, r3.group_id, r3.problem_id, count(distinct student_id) cnt
            from results r3
            where r3.group_id is not null
            group by 1, 2, 3
        ),
        tot as (
            select r1.lesson, r1.group_id, count(distinct student_id) cnt
            from results r1
            where r1.group_id is not null
            group by 1, 2
        )
        select p.lesson,
               p.group_id,
               p.lesson || coalesce(g.short_code, p.group_id) || '.' || p.prob || p.item p,
               p.title,
               ifnull(sol.cnt, 0) as sol,
               ifnull(try.cnt, 0) as tried,
               ifnull(tot.cnt, 0) as cnt
        from problems p
        left join groups g on g.group_id = p.group_id
        left join sol on sol.lesson = p.lesson and sol.group_id = p.group_id and sol.problem_id = p.id
        left join try on try.lesson = p.lesson and try.group_id = p.group_id and try.problem_id = p.id
        left join tot on tot.lesson = p.lesson and tot.group_id = p.group_id
        where p.group_id is not null
        order by p.lesson desc, g.sort_order,  p.group_id, p.prob, p.item;
    ''')
    all_rows = cursor.fetchall()
    all_group_ids = set()
    group_ids = {row['group_id'] for row in all_rows if row['group_id']}
    per_lesson_group = {}
    for row in all_rows:
        lesson = row['lesson']
        group_id = row['group_id']
        if group_id:
            all_group_ids.add(group_id)
        if lesson not in per_lesson_group:
            per_lesson_group[lesson] = {group_id: [] for group_id in group_ids}
        per_lesson_group[lesson][group_id].append(row)
    all_group_ids = sorted(all_group_ids)
    return per_lesson_group, all_group_ids


def collect_group_meta(group_ids):
    group_ids = {group_id for group_id in group_ids if group_id}
    if not group_ids:
        return []
    groups = [row for row in db.group.get_all() if row['group_id'] in group_ids]
    known_ids = {row['group_id'] for row in groups}
    for group_id in sorted(group_ids - known_ids):
        groups.append({
            'group_id': group_id,
            'short_code': group_id,
            'public_name': group_id,
        })
    return groups


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
        GROUP_STYLES

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
    const groupMeta = GROUP_META;
    const groupStyles = GROUP_STYLES_MAP;
    const groupPlotColors = GROUP_PLOT_COLORS;

    function formatGroupLabel(groupId) {
        const meta = groupMeta[groupId];
        if (!meta) {
            return groupId;
        }
        const shortCode = meta.short_code || '';
        const publicName = meta.public_name || '';
        if (shortCode && publicName && shortCode !== publicName) {
            return `${shortCode} - ${publicName}`;
        }
        return publicName || shortCode || groupId;
    }

    function unpack(rows, key) {
        return rows.map(function (row) {
            return row[key];
        });
    }

    const groupPlotStyles = all_groups.map(groupId => ({
        target: groupId,
        value: {line: {color: groupPlotColors[groupId] || '#2e7d32'}}
    }));

    for (let lesson of lessons) {
        const div1 = document.createElement('div');
        div1.id = `violin${lesson}`;
        div1.style.maxWidth = '50rem';
        div1.style.margin = '0 auto';
        document.body.appendChild(div1);

        const data1 = [{
            type: 'violin',
            x: perLes[lesson].group_ids,
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
                groups: perLes[lesson].group_ids,
                styles: groupPlotStyles
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
        for (const groupId of all_groups) {
            const data2 = perProb[lesson][groupId] || [];
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
                row.className = groupStyles[groupId] || '';

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
            header.innerText = `${formatGroupLabel(groupId)}, занятие ${lesson}`;
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
    table_data, all_group_ids = calc_stat_table_data(cursor)
    cursor.close()
    lessons = sorted(violin_plots_data.keys(), reverse=True)
    group_ids = set(all_group_ids)
    for lesson_data in violin_plots_data.values():
        group_ids.update(lesson_data['group_ids'])
    groups = collect_group_meta(group_ids)
    all_groups = [group['group_id'] for group in groups]
    group_meta = {}
    group_styles_map = {}
    group_plot_colors = {}
    for idx, group in enumerate(groups):
        group_id = group['group_id']
        short_code = group.get('short_code') or group_id
        public_name = group.get('public_name') or group_id
        group_meta[group_id] = {
            'short_code': short_code,
            'public_name': public_name,
        }
        group_styles_map[group_id] = f'grp-{idx}'
        group_plot_colors[group_id] = LINE_PALETTE[idx % len(LINE_PALETTE)]
    group_style_css = '\n'.join(
        f'.grp-{idx} {{ background-color: {STYLE_PALETTE[idx % len(STYLE_PALETTE)]}; }}'
        for idx in range(len(groups))
    )
    script = f'''
    const perProb = {json.dumps(table_data)};
    const perLes = {json.dumps(violin_plots_data)};
    const lessons = {json.dumps(lessons)};
    const all_groups = {json.dumps(all_groups)};
    '''
    return (
        html.replace('DATA', script)
        .replace('GROUP_META', json.dumps(group_meta))
        .replace('GROUP_STYLES_MAP', json.dumps(group_styles_map))
        .replace('GROUP_PLOT_COLORS', json.dumps(group_plot_colors))
        .replace('GROUP_STYLES', group_style_css)
    )

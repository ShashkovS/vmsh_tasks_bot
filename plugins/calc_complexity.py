import sqlite3
import numpy as np

from helpers.config import config


COMPL_CALC_WEIGHT = 2
COMPL_ONE_WEIGHT = 1
SIMPLE_CALC_WEIGHT = 9999
SIMPLE_ONE_WEIGHT = 1


def get_conn() -> sqlite3.Connection:
    def dict_factory(cursor, row):
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    conn = sqlite3.connect(config.db_filename)
    conn.row_factory = dict_factory
    return conn


def drop_temp_tables(cur: sqlite3.Cursor):
    for table in ['temp_problem_scores', 'temp_student_visits', 'temp_real_problem_scores_t', 'temp_result_rolling_window_scores',
                  'temp_real_problem_scores', 'temp_real_students', 'temp_real_problems',
                  'temp_lesson_scores', 'temp_student_per_lesson_level_score', 'temp_student_per_lesson_level_strength',
                  'temp_final_student_level_visits', 'temp_prob_сompl_2', 'temp_pup_strength_2', 'temp_7_window']:
        cur.execute(f'drop table if exists {table}')


def create_results_with_scores_for_test_problems_and_synonim_duplicates(cur: sqlite3.Cursor):
    print('create_results_with_scores_for_test_problems_and_synonim_duplicates...')
    scores_with_synonim_problems_scripts = '''
    -- Ставим баллы за тестовые задачи. Каждая попытка отнимает 3/32=0.046875≈0.05 балла
    drop table if exists temp_problem_scores;
    create table temp_problem_scores as
        with
        tries as (
            select r.student_id, p.synonyms, v.val, row_number() over (partition by r.student_id, p.synonyms order by r.ts ) rn
            from results r 
            join problems p on r.problem_id = p.id
            join verdicts v on r.verdict = v.id
        ),
        max_val as (
            select student_id, synonyms, max(val) val from tries
            group by 1, 2
        ),
        first_success as (
            select t.student_id, t.synonyms, t.val, min(t.rn) try from tries t
            join max_val m on m.student_id = t.student_id and m.synonyms = t.synonyms and m.val = t.val 
            group by 1, 2
        )
        select distinct student_id, first_success.synonyms,
               case
                   when p.prob_type = 1 then max(33.0/64.0, 1 - (try-1.0)*3.0/64.0)*val -- Только точно представимые числа
                   else val
               end score from first_success
        join problems p on first_success.synonyms = p.synonyms
        where p.lesson >= 0 and p.prob > 0;
    '''.split(';')

    for script in scores_with_synonim_problems_scripts:
        # print('*' * 50)
        # print(script.strip(), end='...')
        cur.executescript(script)
        # print('DONE')


def create_dummy_problem_complexity_table_and_pupil_strength(cur: sqlite3.Cursor):
    print('create_dummy_problem_complexity_table_and_pupil_strength...')
    scripts = '''
    -- Создаём «первичную» таблицу стоимостей задач
    create table if not exists problem_complexity (
        synonyms TEXT NOT NULL primary key,
        for_weak DOUBLE NOT NULL,
        for_strong DOUBLE NOT NULL
    );
    -- Создаём «первичную» таблицу сил школьников
    create table if not exists student_strength
    (
        student_id integer not null primary key,
        simple_prob DOUBLE NOT NULL,
        compl_prob DOUBLE NOT NULL
    );
    -- Если таблицы уже существовали, то актуализируем
    delete from problem_complexity 
    where synonyms not in (select synonyms from problems);
    -- Если таблицы уже существовали, то актуализируем
    delete from student_strength 
    where student_id not in (select id from users);
    -- Подливаем недостающее с весами 0.5
    insert into problem_complexity
    select distinct synonyms, 0.5 for_weak, 0.5 for_strong from problems
    where lesson >= 0 and prob > 0 
    and synonyms not in (select synonyms from problem_complexity);
    -- Подливаем недостающее с весами 0.5
    insert into student_strength
    select id as student_id, 0.5 simple_prob, 0.5 compl_prob from users
    where type=1
    and id not in (select student_id from student_strength);
    '''
    for script in scripts.split(';'):
        # print('*' * 50)
        # print(script.strip(), end='...')
        cur.executescript(script)
        # print('DONE')


def create_student_visits_table(cur: sqlite3.Cursor):
    print('create_student_visits_table...')
    scripts = f'''
    -- Суммарная статистика по каждому занятию
    drop table if exists temp_lesson_scores;
    create table temp_lesson_scores as
    select p.lesson, p.level, sum(for_weak) sum_for_weak, sum(for_strong) sum_for_strong, count(*) cnt from problems p
    join problem_complexity c on p.synonyms=c.synonyms
    group by 1, 2
    ;

    -- Суммарные баллы по каждому занятию-уровню
    drop table if exists temp_student_per_lesson_level_score;
    create table temp_student_per_lesson_level_score as
    select student_id, p.lesson, p.level, sum(s.score) total, sum(s.score*c.for_weak) total_weak, sum(s.score*c.for_strong) total_strong
    from temp_problem_scores s
    join problems p on s.synonyms = p.synonyms
    join problem_complexity c on s.synonyms = c.synonyms
    group by 1, 2, 3;

    -- Итоговые силы по каждому занятию-уровню
    drop table if exists temp_student_per_lesson_level_strength;
    -- Идея с COMPL_ONE_WEIGHT в том, что если все задачи халявные, то большой рейтинг в решении сложных задач получить нельзя
    create table temp_student_per_lesson_level_strength as
    select
        ss.student_id, ss.lesson, ss.level,
        (ss.total - ss.total_weak) * {SIMPLE_CALC_WEIGHT+SIMPLE_ONE_WEIGHT:0.2f} / ({SIMPLE_CALC_WEIGHT:0.2f} * (ls.cnt - ls.sum_for_weak) + {SIMPLE_ONE_WEIGHT:0.2f} * cnt) as simple_prob_strength,
        ss.total_strong * {COMPL_CALC_WEIGHT+COMPL_ONE_WEIGHT:0.2f} / ({COMPL_CALC_WEIGHT:0.2f} * ls.sum_for_strong + {COMPL_ONE_WEIGHT:0.2f} * cnt) as compl_prob_strength
    from temp_student_per_lesson_level_score ss
    join temp_lesson_scores ls on ss.lesson=ls.lesson and ss.level=ls.level
    join student_strength ps on ss.student_id = ps.student_id
    ;
    -- Теперь шаманство. Удаляем те уровни, в которых не сдано ни одной реальной задачи
    delete from temp_student_per_lesson_level_strength
    where (student_id, lesson, level) not in 
        (select distinct student_id, lesson, level from results
        where verdict > 0)
    ;

    -- Итоговый вердикт по тому, какое «занятие» школьник посещал
    drop table if exists temp_student_visits;
    create table temp_student_visits as
    with pre as (
        select student_id, lesson, level, simple_prob_strength, compl_prob_strength,
               row_number() over (partition by student_id, lesson order by (compl_prob_strength*3 + simple_prob_strength*2) desc) rn_mid
               from temp_student_per_lesson_level_strength
    )
    select student_id, lesson, level
    from pre
    where rn_mid = 1
    order by student_id, lesson
    ;
    drop table if exists temp_student_per_lesson_level_score;
    drop table if exists temp_student_per_lesson_level_strength;
    '''
    for script in scripts.split(';'):
        # print('*' * 50)
        # print(script.strip(), end='...')
        cur.executescript(script)
        # print('DONE')


def create_real_problem_scores(cur: sqlite3.Cursor):
    '''
    -- Таблица точных результатов:
    -- null, если школьника не было на занятии-уровне,
    -- 0, если был на занятии-уровне, но не решил задачу
    -- score, если был на занятии-уровне, и решил задачу
    '''
    scripts = '''
    drop table if exists temp_real_problem_scores_t;
    -- Добавляем ненулевые результаты
    create table temp_real_problem_scores_t as
    select v.student_id, v.lesson, v.level, p.id as problem_id, p.synonyms, s.score from temp_student_visits v
    join problems p on v.lesson = p.lesson and v.level=p.level
    join temp_problem_scores s on v.student_id=s.student_id and p.synonyms=s.synonyms
    where p.prob > 0;
    -- Подливаем нули
    insert into temp_real_problem_scores_t
    select v.student_id, v.lesson, v.level, p.id as problem_id, p.synonyms, 0.0 score from temp_student_visits v
    join problems p on v.level = p.level and v.lesson = p.lesson
    where p.prob > 0;

    -- Итоговые реальные результаты
    drop table if exists temp_real_problem_scores;
    create table temp_real_problem_scores as
    select student_id, lesson, level, problem_id, synonyms, max(score) score
    from temp_real_problem_scores_t
    group by 1, 2, 3, 4
    order by 1, 2, 3, 4
    ;
    drop table if exists temp_real_problem_scores_t;
    '''
    for script in scripts.split(';'):
        # print('*' * 50)
        # print(script.strip(), end='...')
        cur.executescript(script)
        # print('DONE')


def create_result_rolling_window_scores(cur: sqlite3.Cursor):
    scripts = f'''
    -- Таблица окон для вычислений
    drop table if exists temp_7_window;
    create table temp_7_window (lesson, st, en);
     --insert into temp_7_window values (1, 1, 4), (2, 1, 5), (3, 1, 6), (4, 1, 7), (5, 2, 8), (6, 3, 9), (7, 4, 10), (8, 5, 11), (9, 6, 12), (10, 7, 13), (11, 8, 14), (12, 9, 15), (13, 10, 16), (14, 11, 17), (15, 12, 18), (16, 13, 19), (17, 14, 20), (18, 15, 21), (19, 16, 22), (20, 17, 23), (21, 18, 24), (22, 19, 25), (23, 20, 26), (24, 21, 27), (25, 22, 28), (26, 23, 29), (27, 24, 30), (28, 25, 31), (29, 26, 32), (30, 27, 33), (31, 28, 34), (32, 29, 35), (33, 30, 36), (34, 31, 36), (35, 32, 36), (36, 33, 36);    
     insert into temp_7_window values (1,1,1), (2,2,2), (3,3,3), (4,4,4), (5,5,5), (6,6,6), (7,7,7), (8,8,8), (9,9,9), (10,10,10), (11,11,11), (12,12,12), (13,13,13), (14,14,14), (15,15,15), (16,16,16), (17,17,17), (18,18,18), (19,19,19), (20,20,20), (21,21,21), (22,22,22), (23,23,23), (24,24,24), (25,25,25), (26,26,26), (27,27,27), (28,28,28), (29,29,29), (30,30,30), (31,31,31), (32,32,32), (33,33,33), (34,34,34), (35,35,35), (36,36,36);    

    -- Таблица с плывущим оконным рейтингом 
    drop table if exists temp_result_rolling_window_scores;
    create table temp_result_rolling_window_scores as
    with best_level as (
        select distinct s.student_id, s.lesson, s.level from temp_real_problem_scores s
    )
    select
        s.student_id,
        w.lesson,
        b.level,
        10.0 * ((sum(s.score) - sum(s.score * c.for_weak)) * {SIMPLE_CALC_WEIGHT + SIMPLE_ONE_WEIGHT:0.2f} / ({SIMPLE_CALC_WEIGHT:0.2f} * (sum(c.for_weak > 0) - sum(c.for_weak)) + {SIMPLE_ONE_WEIGHT:0.2f} * sum(c.for_weak > 0))) as simple_prob_strength,
        10.0 * (sum(s.score * c.for_strong) * {COMPL_CALC_WEIGHT + COMPL_ONE_WEIGHT:0.2f}  / ({COMPL_CALC_WEIGHT:0.2f}  * sum(c.for_strong) + {COMPL_ONE_WEIGHT:0.2f}  * sum(c.for_strong > 0))) as compl_prob_strength,
        10.0 * (sum(1 * c.for_strong) * {COMPL_CALC_WEIGHT + COMPL_ONE_WEIGHT:0.2f}  / ({COMPL_CALC_WEIGHT:0.2f}  * sum(c.for_strong) + {COMPL_ONE_WEIGHT:0.2f}  * sum(c.for_strong > 0))) as max_compl_prob_strength,
-- Тупо суммы    
--        sum(s.score * c.for_weak)/count(distinct s.lesson) as simple_prob_strength,
--        sum(s.score * c.for_strong)/count(distinct s.lesson) as compl_prob_strength,
        sum(s.score > 0) solved,
        sum(c.for_strong > 0) tot_problems
    from temp_7_window w
    cross join temp_real_problem_scores s on s.lesson between w.st and w.en
    join problem_complexity c on c.synonyms = s.synonyms
    left join best_level b on b.student_id = s.student_id and b.lesson = w.lesson
    where b.level is not null
    group by 1, 2
    order by 1, 2
    ;
    '''
    for script in scripts.split(';'):
        # print('*' * 50)
        # print(script.strip(), end='...')
        cur.executescript(script)
        # print('DONE')


def get_all_real_problem_and_student_ids(cur: sqlite3.Cursor) -> tuple[list, list]:
    pupils_ids = [row['student_id'] for row in cur.execute('select distinct student_id from temp_real_problem_scores').fetchall()]
    problems_ids = [row['synonyms'] for row in cur.execute('select distinct synonyms from temp_real_problem_scores').fetchall()]
    return pupils_ids, problems_ids


def get_complexities_and_strengths(cur: sqlite3.Cursor) -> tuple[list, list]:
    complexities = cur.execute('select * from problem_complexity').fetchall()
    strengths = cur.execute('select * from student_strength').fetchall()
    return complexities, strengths


def create_data_table(pup_to_row: dict, prob_to_col: dict, cur: sqlite3.Cursor):
    num_pupils = len(pup_to_row)
    num_problems = len(prob_to_col)
    data = np.empty((num_pupils, num_problems), dtype=float)
    data[:, :] = np.nan
    for row in cur.execute('select student_id, synonyms, score from temp_real_problem_scores').fetchall():
        r = pup_to_row[row['student_id']]
        c = prob_to_col[row['synonyms']]
        data[r, c] = row['score']
    return data


def create_complexity_and_strength_array(pup_to_row: dict, prob_to_col: dict, complexities: list, strengths: list):
    num_pupils = len(pup_to_row)
    num_problems = len(prob_to_col)
    prob_compl_for_strong = np.ones(num_problems) / 2
    prob_compl_for_weak = np.ones(num_problems) / 2
    pup_compl_prob_strength = np.ones(num_pupils) / 2
    pup_simple_prob_strength = np.ones(num_pupils) / 2
    complexities = {row['synonyms']: (row['for_weak'], row['for_strong']) for row in complexities}
    for id, col in prob_to_col.items():
        prob_compl_for_weak[col], prob_compl_for_strong[col] = complexities[id]
    strengths = {row['student_id']: (row['compl_prob'], row['simple_prob']) for row in strengths}
    for id, col in pup_to_row.items():
        pup_compl_prob_strength[col], pup_simple_prob_strength[col] = strengths[id]
    return prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength,


def calc(data, prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength):
    num_pupils, num_problems = data.shape
    SOLVED_THRESHOLD = 1 / 2

    for i in range(20):
        # print(716, prob_compl_for_strong[716], prob_compl_for_weak[716])
        prob_compl_for_strong_old = prob_compl_for_strong.copy()
        prob_compl_for_weak_old = prob_compl_for_weak.copy()
        pup_compl_prob_strength_old = pup_compl_prob_strength.copy()
        pup_simple_prob_strength_old = pup_simple_prob_strength.copy()
        print(i, '...')
        # Переоцениваем силу школьника
        for curr_pup in range(num_pupils):
            solved_vec = data[curr_pup, :] >= SOLVED_THRESHOLD  # Вектор задач, которые школьник решИл
            tried_vec = data[curr_pup, :] >= 0  # Вектор задач, которые школьник решАл
            # Сила школьника в простых задачах --- доля (единица минус сложностей) задач, которые он решил
            # Если школьник не решил простую задачу, то он потерял почти единицу в числителе
            pup_simple_prob_strength[curr_pup] = \
                np.dot(data[curr_pup, solved_vec], 1 - prob_compl_for_weak[solved_vec]) * (SIMPLE_CALC_WEIGHT+SIMPLE_ONE_WEIGHT) \
                 / (SIMPLE_CALC_WEIGHT * sum(1 - prob_compl_for_weak[tried_vec]) + SIMPLE_ONE_WEIGHT * sum(prob_compl_for_weak[tried_vec] > 0))
            # Сила школьника в сложных задачах --- доля сложности, которую он порвал
            # Ясно, что нерешённая сложная задача сильно уменьшает эту долю
            pup_compl_prob_strength[curr_pup] = \
                np.dot(data[curr_pup, solved_vec], prob_compl_for_strong[solved_vec]) * (COMPL_CALC_WEIGHT+COMPL_ONE_WEIGHT) \
                / (COMPL_CALC_WEIGHT * sum(prob_compl_for_strong[tried_vec]) + COMPL_ONE_WEIGHT * sum(prob_compl_for_strong[tried_vec] > 0))
        # Переоцениваем сложность задач
        for curr_prob in range(num_problems):
            solved_vec = data[:, curr_prob] >= SOLVED_THRESHOLD  # Вектор школьников, решИвших задачу
            tried_vec = data[:, curr_prob] >= 0  # Вектор школьников, решАвших задачу
            # Сложность задачи для сильных --- доля силы школьников в простых задачах, НЕ решивших задачу
            # Если школьник с большим умением решать простые задачи задачу не решил, то это знак
            prob_compl_for_strong[curr_prob] = 1 - \
                                               np.dot(data[:, curr_prob][solved_vec], pup_compl_prob_strength[solved_vec]) * \
                                               20 / (19 * sum(pup_compl_prob_strength[tried_vec]) + 1 * sum(pup_compl_prob_strength[tried_vec] > 0))
            # Сложность задачи для слабых --- доля (единица минус сила в сложных задачах) школьников, НЕ решивших задачу
            # Если школьник, нефига не умеющий решать сложные задачи, решил задачу, то это знак
            prob_compl_for_weak[curr_prob] = 1 - \
                                             np.dot(data[:, curr_prob][solved_vec], 1 - pup_simple_prob_strength[solved_vec]) * \
                                             20 / (19 * sum(1 - pup_simple_prob_strength[tried_vec]) + 1 * sum(pup_simple_prob_strength[tried_vec] > 0))
        # Если всё стабилизировалось, то останавливаемся
        prob_compl_for_strong_diff = np.max(np.abs(prob_compl_for_strong_old - prob_compl_for_strong))
        prob_compl_for_weak_diff = np.max(np.abs(prob_compl_for_weak_old - prob_compl_for_weak))
        pup_compl_prob_strength_diff = np.max(np.abs(pup_compl_prob_strength_old - pup_compl_prob_strength))
        pup_simple_prob_strength_diff = np.max(np.abs(pup_simple_prob_strength_old - pup_simple_prob_strength))
        cur_max_diff = max(prob_compl_for_strong_diff, prob_compl_for_weak_diff, pup_compl_prob_strength_diff, pup_simple_prob_strength_diff)
        print(f'{cur_max_diff=}')
        if cur_max_diff < 1e-5:
            break
    return prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength,


def update_compl(col_to_prob_id: dict, prob_compl_for_weak, prob_compl_for_strong, cur, conn):
    cur.execute('drop table if exists temp_prob_сompl_2;')
    cur.execute('create table temp_prob_сompl_2 as select * from problem_complexity;')
    cur.execute('delete from problem_complexity;')
    complexities = []
    assert len(col_to_prob_id) == len(prob_compl_for_weak) == len(prob_compl_for_strong)
    for col in col_to_prob_id:
        id, weak, strong = col_to_prob_id[col], prob_compl_for_weak[col], prob_compl_for_strong[col]
        complexities.append((id, weak, strong))
    cur.executemany('insert into problem_complexity (synonyms, for_weak, for_strong) values (?,?,?)', complexities)
    conn.commit()
    for row in cur.execute('''
            select v1.synonyms, round(v1.for_weak,4) for_weak, round(v2.for_weak,4) as weak_v2, round(v1.for_strong,4) for_strong, round(v2.for_strong,4) as strong_v2, round(abs(v1.for_strong-v2.for_strong),4) df,
                    count(*) cnt, sum(score>0) sol
            from problem_complexity as v1
            join temp_prob_сompl_2 as v2 using (synonyms)
            left join temp_real_problem_scores s on v1.synonyms=s.synonyms
            group by 1, 2, 3, 4, 5, 6
            order by 6 desc
            limit 3;
        ''').fetchall():
        print(row)
    cur.execute('drop table if exists temp_prob_сompl_2;')
    return row['df']


def update_strength(row_to_pup_id, pup_simple_prob_strength, pup_compl_prob_strength, cur, conn):
    cur.execute('drop table if exists temp_pup_strength_2;')
    cur.execute('create table temp_pup_strength_2 as select * from student_strength;')
    # Теперь заливаем в базу результаты (пока предварительные)
    cur.execute('delete from student_strength;')
    strengths = [(row_to_pup_id[row], pup_simple_prob_strength[row], pup_compl_prob_strength[row]) for row in row_to_pup_id]
    cur.executemany('insert into student_strength (student_id, simple_prob, compl_prob) values (?,?,?)', strengths)
    conn.commit()
    for row in cur.execute('''
            select v1.student_id, round(v1.simple_prob,4) simple_prob, round(v2.simple_prob,4) as simple_v2, round(v1.compl_prob,4) compl_prob, round(v2.compl_prob,4) as compl_v2, round(abs(v1.compl_prob-v2.compl_prob),4) df,
                    count(*) cnt, sum(score>0) sol
            from student_strength as v1
            join temp_pup_strength_2 as v2 using (student_id)
            left join temp_real_problem_scores s on v1.student_id=s.student_id
            group by 1, 2, 3, 4, 5, 6
            order by 6 desc
            limit 3;
        ''').fetchall():
        print(row)
    cur.execute('drop table if exists temp_pup_strength_2;')
    return row['df']


def main(cur: sqlite3.Cursor):
    drop_temp_tables(cur)

    # Считаем баллы по каждой задаче.
    # По тестовым может быть немного меньше, если было много попыток.
    # Также добавлены записи по синонимичным задачам
    # temp_problem_scores (student_id, synonyms, score)
    create_results_with_scores_for_test_problems_and_synonim_duplicates(cur)

    # Создать стартовую таблицу problem_complexity со стоимостью задач
    # problem_complexity (synonyms, for_weak, for_strong)
    # student_strength (student_id, simple_prob, compl_prob)
    create_dummy_problem_complexity_table_and_pupil_strength(cur)

    # Повторяем дважды
    for i in range(3):
        # На выходе таблица temp_student_visits, в которой для каждого студента для каждого занятия
        # выбран наиболее успешный уровень
        # temp_student_visits (student_id, lesson, level)
        create_student_visits_table(cur)

        # Таблица точных результатов:
        # null, если школьника не было на занятии-уровне,
        # 0, если был на занятии-уровне, но не решил задачу
        # score, если был на занятии-уровне, и решил задачу
        # В этой таблице уже используются подменные ID для синонимичных задач
        # temp_real_problem_scores (student_id, lesson_id, level, synonyms, score)
        # Здесь уже для синонимичных задач используется подменный synonyms
        create_real_problem_scores(cur)

        # Получаем реальный список задач и студентов (без нулевых)
        # Здесь уже для синонимичных задач используется подменный synonyms
        pupils_ids, problems_ids = get_all_real_problem_and_student_ids(cur)
        pup_to_row = {id: r for r, id in enumerate(pupils_ids)}
        row_to_pup_id = {r: id for r, id in enumerate(pupils_ids)}
        assert len(pup_to_row) == len(row_to_pup_id)
        prob_to_col = {id: c for c, id in enumerate(problems_ids)}
        col_to_prob_id = {c: id for c, id in enumerate(problems_ids)}
        assert len(prob_to_col) == len(col_to_prob_id)
        # Берём текущие силы и сложности
        complexities, strengths = get_complexities_and_strengths(cur)

        # Заполняем таблицу
        data = create_data_table(pup_to_row, prob_to_col, cur)
        # np.savetxt(rf"Y:\data_{i}.tsv", data, delimiter="\t", fmt='%4.3f')
        prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength = \
            create_complexity_and_strength_array(pup_to_row, prob_to_col, complexities, strengths)
        # Вычисляем силы и сложности
        prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength = \
            calc(data, prob_compl_for_strong, prob_compl_for_weak, pup_compl_prob_strength, pup_simple_prob_strength)

        # Обновляем сложности
        df_compl = update_compl(col_to_prob_id, prob_compl_for_weak, prob_compl_for_strong, cur, conn)
        # Обновляем силы
        df_strength = update_strength(row_to_pup_id, pup_simple_prob_strength, pup_compl_prob_strength, cur, conn)
        # Если изменений уже нет, то останавливаемся
        if df_compl < 1e-5 and df_strength < 1e-5:
            break

    # Теперь, когда всё посчитано, считаем оконный рейтинг
    create_result_rolling_window_scores(cur)


conn = get_conn()
cur = conn.cursor()
# Вся основная обработка
main(cur)
# Теперь, когда всё посчитано, считаем оконный рейтинг
create_result_rolling_window_scores(cur)

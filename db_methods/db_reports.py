from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_REPORTS(DB_ABC):
    def calc_last_lesson_stat(self) -> List[dict]:
        """Посчитать статистику решаемости по последнему занятию.
        Возвращает список словарей с ключами prb, frac, perc, title
        """
        cur = self.db.conn.execute("""
            with pre as (
                select r.lesson, r.group_id, p.prob, p.item, r.problem_id,
                       p.title, r.student_id,
                       case when max(r.verdict) > 0 then 1 else 0 end verdict
                from results r
                join problems p on r.problem_id = p.id
                where p.lesson = (select max(lesson) as last_lesson from problems)
                group by 1, 2, 3, 4, 5, 6, 7
            ),
                 res as (
            select pre.lesson || coalesce(g.short_code, pre.group_id) || '.' || pre.prob || pre.item as prb, pre.title, sum(pre.verdict) plus,
                   (select count(distinct pre2.student_id) from pre as pre2 where pre.group_id = pre2.group_id) tot,
                   (select count(distinct student_id) from results as rr where rr.problem_id = pre.problem_id) dist_prob
            from pre
            left join groups g on g.group_id = pre.group_id
            group by pre.lesson, pre.group_id, pre.prob, pre.item, pre.title, g.sort_order
            order by g.sort_order, pre.group_id, pre.prob, pre.item)
            select prb, plus||'/'||dist_prob||'/'||tot as frac, replace(round(plus*100.0/tot,1), '.', ',')||'%' perc, title from res
        """)
        rows = cur.fetchall()
        return rows


report = DB_REPORTS(sql)

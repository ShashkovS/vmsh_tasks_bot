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
                select r.lesson, r.level, p.prob, p.item,
                       p.title, r.student_id,
                       case when max(r.verdict) > 0 then 1 else 0 end verdict
                from results r
                         join problems p on r.problem_id = p.id
                where p.lesson = (select max(lesson) as last_lesson from problems)
                group by 1, 2, 3, 4, 5, 6
            ),
                 res as (
            select lesson || level || '.' || prob || item as prb, title, sum(verdict) plus,
                   (select count(distinct student_id) from pre as pre2 where pre.level = pre2.level) tot
            from pre
            group by lesson, level, prob, item, title
            order by level, prob, item)
            select prb, plus||'/'||tot as frac, replace(round(plus*100.0/tot,1), '.', ',')||'%' perc, title from res
        """)
        rows = cur.fetchall()
        return rows


report = DB_REPORTS(sql)

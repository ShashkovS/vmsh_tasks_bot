from typing import List
from .db_abc import DB_ABC, sql


# ██      ███████ ███████ ███████  ██████  ███    ██ ███████
# ██      ██      ██      ██      ██    ██ ████   ██ ██
# ██      █████   ███████ ███████ ██    ██ ██ ██  ██ ███████
# ██      ██           ██      ██ ██    ██ ██  ██ ██      ██
# ███████ ███████ ███████ ███████  ██████  ██   ████ ███████

class DB_LESSON(DB_ABC):
    def update(self):
        """Создать записи с уроками на основе списка задач.
        По записи на каждую возможную пару (lesson, group_id)"""
        with self.db.conn as conn:
            conn.execute("""
                insert into lessons (lesson, group_id)
                select distinct p.lesson, p.group_id
                from problems p
                where (p.lesson, p.group_id) not in (select l.lesson, l.group_id from lessons l)
            """)

    def get_all(self, group_id: str = None) -> List[dict]:
        """Получить список всех уроков.
        Возвращает список словарей с ключами lesson, group_id, group_code"""
        return self.db.conn.execute('''
            SELECT l.lesson, l.group_id, g.short_code as group_code
            FROM lessons l
            left join groups g on g.group_id = l.group_id
            where (:group_id is null or :group_id = l.group_id)
            order by l.lesson, g.sort_order, l.group_id
            ''', locals()).fetchall()

    def get_last(self, group_id: str = None) -> int:
        """Получить номер последнего урока данной группы или вообще любого"""
        cur = self.db.conn.execute('''
            SELECT max(lesson) as mx 
            FROM lessons
            where (:group_id is null or :group_id = group_id)
        ''', locals())
        row = cur.fetchone()
        return row['mx']


lesson = DB_LESSON(sql)

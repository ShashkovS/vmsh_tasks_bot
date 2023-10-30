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
        По записи на каждую возможную пару (lesson, level)"""
        with self.db.conn as conn:
            conn.execute("""
                insert into lessons (lesson, level)
                select distinct p.lesson, p.level
                from problems p
                where (p.lesson, p.level) not in (select l.lesson, l.level from lessons l)
            """)

    def get_all(self, level: str = None) -> List[dict]:
        """Получить список всех уроков.
        Возвращает список словарей с ключами level, lesson"""
        return self.db.conn.execute('''
            SELECT level, lesson 
            FROM lessons 
            where :level is null or :level = level
            order by lesson, level
            ''', locals()).fetchall()

    def get_last(self, level: str = None) -> int:
        """Получить номер последнего урока данного уровня или вообще любого уровня"""
        cur = self.db.conn.execute('''
            SELECT max(lesson) as mx 
            FROM lessons
            where :level is null or :level = level
        ''', locals())
        row = cur.fetchone()
        return row['mx']


lesson = DB_LESSON(sql)

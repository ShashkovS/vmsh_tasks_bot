from typing import List, Optional
from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_MEDIA_GROUPS(DB_ABC):
    def check(self, media_group_id: int) -> Optional[int]:
        """Получить номер задачи, к которой относится данная медиа-группа.
        Или None, если группа новая"""
        saved_problem_id = self.db.conn.execute('''
            select problem_id from media_groups
            where media_group_id = :media_group_id
        ''', locals()).fetchone()
        return saved_problem_id and saved_problem_id['problem_id']

    def insert(self, media_group_id: int, problem_id: int) -> bool:
        """Сохранить номер задачи, к которой привязана данная медиагруппа.
        Необходимо для того, чтобы понять, к какой задаче относятся
        вторая и далее отправленная фотка с решением"""
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            cur = conn.execute("""
                insert into media_groups ( media_group_id,  problem_id,  ts) 
                values                   (:media_group_id, :problem_id, :ts) 
                on conflict (media_group_id) DO NOTHING
            """, locals())
            duplicate = cur.rowcount == 0
            return duplicate


media_group = DB_MEDIA_GROUPS(sql)

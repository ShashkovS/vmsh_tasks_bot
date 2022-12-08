import sqlite3
from typing import List, Optional
from datetime import datetime


class DB_MEDIA_GROUPS():
    conn: sqlite3.Connection

    def media_group_check(self, media_group_id: int) -> Optional[int]:
        cur = self.conn.cursor()
        saved_problem_id = cur.execute('''
            select problem_id from media_groups
            where media_group_id = :media_group_id
        ''', locals()).fetchone()
        print(f'{saved_problem_id=}')
        return saved_problem_id and saved_problem_id['problem_id']

    def media_group_add(self, media_group_id: int, problem_id: int) -> bool:
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            insert into media_groups ( media_group_id,  problem_id,  ts) 
            values                   (:media_group_id, :problem_id, :ts) 
            on conflict (media_group_id) DO NOTHING
        """, locals())
        self.conn.commit()
        duplicate = cur.rowcount == 0
        return duplicate

from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


# ██     ██  █████  ██ ████████ ██      ██ ███████ ████████
# ██     ██ ██   ██ ██    ██    ██      ██ ██         ██
# ██  █  ██ ███████ ██    ██    ██      ██ ███████    ██
# ██ ███ ██ ██   ██ ██    ██    ██      ██      ██    ██
#  ███ ███  ██   ██ ██    ██    ███████ ██ ███████    ██


class DB_WAITLIST(DB_ABC):
    @staticmethod
    def _group_filter(group_ids, *, alias: str = 'p'):
        if not group_ids:
            return '', {}
        group_ids = list(group_ids)
        placeholders = []
        params = {}
        for idx, group_id in enumerate(group_ids):
            key = f'group_id_{idx}'
            placeholders.append(f':{key}')
            params[key] = group_id
        clause = f' and {alias}.group_id in ({", ".join(placeholders)})'
        return clause, params

    def insert_to_waitlist(self, student_id: int, problem_id: int):
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            conn.execute("""
                INSERT INTO waitlist  ( student_id, entered, problem_id )
                VALUES                (:student_id, :ts,    :problem_id )
            """, locals())

    def delete(self, student_id: int):
        with self.db.conn as conn:
            conn.execute("""
                DELETE FROM waitlist
                WHERE  student_id = :student_id
            """, locals())

    def get_top(self, top_n: int, group_ids=None) -> List[dict]:
        group_clause, params = self._group_filter(group_ids)
        params['top_n'] = top_n
        query = f"""
            SELECT w.* FROM waitlist w
            join problems p on w.problem_id = p.id
            where 1=1 {group_clause}
            ORDER BY entered
            LIMIT :top_n
        """
        return self.db.conn.execute(query, params).fetchall()


waitlist = DB_WAITLIST(sql)

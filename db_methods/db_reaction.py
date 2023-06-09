from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_REACTION(DB_ABC):
    def write_reaction(self, *, result_id: int = None, zoom_conversation_id: int = None, reaction_type_id: int, reaction_id: int) -> int:
        """Записывает в БД в отношение reaction реакцию ученика/учителя на письменную/устную сдачу."""
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            return conn.execute("""
                INSERT INTO reactions ( ts,  result_id,  zoom_conversation_id,  reaction_id,  reaction_type_id)
                               VALUES (:ts, :result_id, :zoom_conversation_id, :reaction_id, :reaction_type_id);
            """, locals()).lastrowid

    def get_reaction_by_id(self, reaction_id: int) -> str:
        """Возвращает текст реакции (вместе с эмоджи) в зависимости от номера реакции."""
        cur = self.db.conn.execute("""
            SELECT reaction FROM reaction_enum 
            WHERE reaction_id = :reaction_id;
        """, locals())
        res = cur.fetchone()
        return res['reaction']

    def get_reactions_enum(self, reaction_type_id: int) -> list:
        """ Возвращает все реакции для данного типа реакции (вместе с эмоджи)
        в виде списка словарей (с ключами 'reaction_id' и 'reaction').
        """
        return self.db.conn.execute("""
            SELECT reaction_id, reaction 
            FROM reaction_enum 
            WHERE reaction_type_id = :reaction_type_id
            ORDER BY reaction_id;
        """, locals()).fetchall()

    def get_reaction_types(self) -> list:
        """ Возвращает все типы реакции в виде списка словарей
        (с ключами 'reaction_type_id' и 'reaction_type').
        """
        return self.db.conn.execute("""
            SELECT reaction_type_id, reaction_type 
            FROM reaction_type_enum 
            ORDER BY reaction_type_id;
        """, locals()).fetchall()


reaction = DB_REACTION(sql)

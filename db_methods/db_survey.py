import sqlite3
from datetime import datetime
from typing import List, Dict


class DB_SURVEY():
    conn: sqlite3.Connection

    def add_survey(self, survey_type: str, for_user_type: int, is_active: bool, question: str, choices: List[str]) -> int:
        """Записывает в БД в отношение reaction реакцию ученика/учителя на письменную/устную сдачу."""
        ts = datetime.now().isoformat()
        with self.conn as conn:
            conn.execute("""begin""")
            survey_id = conn.execute("""
                INSERT INTO surveys ( survey_type,  for_user_type,  is_active,  question,  ts)
                             VALUES (:survey_type, :for_user_type,  :is_active, :question, :ts);
            """, locals()).lastrowid
            for text in choices:
                conn.execute("""
                    INSERT INTO survey_choices ( survey_id,  text)
                                        VALUES (:survey_id, :text);
                """, locals())
        return survey_id

    def get_active_surveys(self, for_user_type: int) -> List[dict]:
        """Возвращает список всех активных опросов
        вместе с вариантами ответов"""
        surveys = self.conn.execute("""
            SELECT * FROM surveys 
            WHERE is_active = true and for_user_type = :for_user_type
            order by id;
        """, locals()).fetchall()
        for survey in surveys:
            survey_id = survey['id']
            survey['choices'] = self.conn.execute("""
                SELECT * FROM survey_choices 
                WHERE survey_id = :survey_id;
            """, locals()).fetchall()
        return surveys

    def get_survey_by_id(self, survey_id: int) -> dict:
        """Возвращает список всех активных опросов
        вместе с вариантами ответов"""
        survey = self.conn.execute("""
            SELECT * FROM surveys 
            WHERE id = :survey_id
        """, locals()).fetchone()
        if survey:
            survey['choices'] = self.conn.execute("""
                SELECT * FROM survey_choices 
                WHERE survey_id = :survey_id;
            """, locals()).fetchall()
        return survey

    def update_survey_result(self, user_id: int, survey_id: int, selection_ids: List[int]):
        """Обновляем результат опроса
        """
        ts = datetime.now().isoformat()
        selection_ids = ';'.join(map(str, selection_ids))
        with self.conn as conn:
            conn.execute("""
                INSERT INTO survey_results ( survey_id,  user_id,  selection_ids,  ts)
                                    VALUES (:survey_id, :user_id, :selection_ids, :ts)
                ON CONFLICT (survey_id, user_id) DO UPDATE SET 
                selection_ids = :selection_ids,
                ts = :ts
            """, locals())

    def disable_survey(self, survey_id: int):
        """Обновляем результат опроса
        """
        with self.conn as conn:
            conn.execute("""
                update surveys
                set is_active = false
                WHERE id = :survey_id
            """, locals())

    def get_survey_result(self, user_id: int, survey_id: int) -> Dict:
        """Получить результаты опроса
        """
        with self.conn as conn:
            row = conn.execute("""
                SELECT selection_ids FROM survey_results 
                WHERE user_id = :user_id and survey_id = :survey_id
            """, locals()).fetchone()
        return (row and list(map(int, row['selection_ids'].split(';')))) or []

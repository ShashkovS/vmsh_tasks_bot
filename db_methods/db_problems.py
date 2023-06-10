from typing import List

from .db_abc import DB_ABC, sql


# ██████  ██████   ██████  ██████  ██      ███████ ███    ███ ███████
# ██   ██ ██   ██ ██    ██ ██   ██ ██      ██      ████  ████ ██
# ██████  ██████  ██    ██ ██████  ██      █████   ██ ████ ██ ███████
# ██      ██   ██ ██    ██ ██   ██ ██      ██      ██  ██  ██      ██
# ██      ██   ██  ██████  ██████  ███████ ███████ ██      ██ ███████

class DB_PROBLEM(DB_ABC):
    def insert(self, data: dict) -> int:
        """Записать в базу (или обновить) новую задачу.
        Уникальным ключом является тройка (level, lesson, prob, item)"""
        with self.db.conn as conn:
            cur = conn.execute("""
                insert into problems ( level,  lesson,  prob,  item,  title,  prob_text,  prob_type,  ans_type,  
                                       ans_validation,  validation_error,  cor_ans,  cor_ans_checker,  wrong_ans,  congrat) 
                values               (:level, :lesson, :prob, :item, :title, :prob_text, :prob_type, :ans_type, 
                                      :ans_validation, :validation_error, :cor_ans, :cor_ans_checker, :wrong_ans, :congrat) 
                on conflict (level, lesson, prob, item) do update 
                set 
                title = excluded.title,
                prob_text = excluded.prob_text,
                prob_type = excluded.prob_type,
                ans_type = excluded.ans_type,
                ans_validation = excluded.ans_validation,
                validation_error = excluded.validation_error,
                cor_ans = excluded.cor_ans,
                cor_ans_checker = excluded.cor_ans_checker,
                wrong_ans = excluded.wrong_ans,
                congrat = excluded.congrat
            """, data)
            return cur.lastrowid

    def get_all(self) -> List[dict]:
        """Получить список вообще всех задача"""
        return self.db.conn.execute("""
            SELECT * FROM problems
        """).fetchall()

    def get_all_by_lesson(self, level: str, lesson: int) -> List[dict]:
        """Получить список задач данного урока и данного уровня"""
        return self.db.conn.execute("""
            SELECT * FROM problems 
            where level = :level and lesson = :lesson
        """, locals()).fetchall()

    def get_by_id(self, problem_id: int) -> dict:
        """Получить атрибуты задачи про её id"""
        return self.db.conn.execute("""
            SELECT * FROM problems 
            where id = :problem_id limit 1
        """, locals()).fetchone()

    def get_by_text_number(self, level: str, lesson: int, prob: int, item: '') -> dict:
        """Получить атрибуты задачи по тройке (level, lesson, prob, item),
        которая является уникальным идентификатором задачи"""
        return self.db.conn.execute("""
            SELECT * FROM problems 
            where level = :level
              and lesson = :lesson
              and prob = :prob
              and item = :item
            limit 1
        """, locals()).fetchone()

    def update_type(self, level: str, lesson: int, from_prob_type: int, to_prob_type: int):
        """Обновить тип данной задачи (например, с устной на письменную)"""
        with self.db.conn as conn:
            conn.execute("""
                UPDATE problems SET prob_type = :to_prob_type
                WHERE level = :level and lesson = :lesson and prob_type = :from_prob_type
            """, locals())

    def update_synonyms(self):
        """Синонимичными считаются задачи с одинаковым названием и одинаковым номером урока.
        В поле synonyms хранится список id-шников всех синонимичных задач в порядке возрастания.
        Благодаря этому у всех синонимичных задач совпадает поле synonyms.
        К сожалению, поля всех задач нужно обновлять при любом обновлении задач.
        Пока это не является проблемой из-за малого числа задач (тысячи, но не сотни тысяч)"""
        with self.db.conn as conn:
            conn.execute("""
                update problems
                set synonyms = (
                    select group_concat(id, ';') 
                    from problems p2 
                    where p2.lesson=problems.lesson and 
                    ( 
                      p2.title = problems.title
                        or -- Отдельный кейс для названий с ценой
                      p2.title like '%⚡%' and ltrim(p2.title,'0123456789⚡ ') = ltrim(problems.title,'0123456789⚡ ')
                    )
                )
                where 1=1;
            """)


problem = DB_PROBLEM(sql)

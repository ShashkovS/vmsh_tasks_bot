from typing import List, Dict
from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_GAME(DB_ABC):
    def get_student_payments(self, user_id: int, command_id: int) -> List[dict]:
        """Получить все игровые траты данного студента.
        Возвращает список словарей с ключами ts, amount"""
        return self.db.conn.execute('''
            SELECT gp.ts, gp.amount FROM game_payments gp
            join game_map_opened_cells gmoc on gp.cell_id = gmoc.id
            where student_id = :user_id and gmoc.command_id = :command_id
            order by ts
        ''', locals()).fetchall()

    def add_payment(self, user_id: int, command_id: int, x: int, y: int, amount: int) -> bool:
        """Записывает в базу факт открытия клетки в игре.
        В транзакции клетка помечается открытой и записывается трата.
        Если «деньги» успешно списаны, то возвращается True.
        Иначе (например, если клетка уже куплена), возвращается False"""
        ts = datetime.now().isoformat()
        try:
            with self.db.conn as conn:
                conn.execute('BEGIN TRANSACTION')
                cur = conn.execute('''
                    insert into game_map_opened_cells (command_id, x, y)
                    values (:command_id, :x, :y)
                ''', locals())
                cell_id = cur.lastrowid
                res = cur.execute('''
                      INSERT INTO game_payments  ( ts, student_id, amount, cell_id)
                      VALUES               (:ts, :user_id, :amount, :cell_id)
                ''', locals())
                return True
        except:
            return False

    def check_neighbours(self, student_command: int, x: int, y: int, ) -> bool:
        """Проверить, что хотя бы одна соседняя ячейка открыта"""
        return bool(self.db.conn.execute("""
            SELECT 1 
            FROM game_map_opened_cells
            where command_id = :student_command and
            ((x = :x and (y = :y - 1 or y = :y + 1))) or (y = :y and (x = :x - 1 or x = :x + 1))
            limit 1 
        """, locals()).fetchone())

    def get_opened_cells(self, student_command: int) -> List[dict]:
        """Получить список всех открытых клеток данного студента.
        Возвращет список словарей с ключами x и y"""
        return self.db.conn.execute("""
            SELECT x, y 
            FROM game_map_opened_cells
            where command_id = :student_command
        """, locals()).fetchall()

    def get_opened_cells_timeline(self, student_command: int) -> List[dict]:
        """Получить последовательность игровых событий данной команды.
        Возвращает список словарей с ключами ts, x, y, student_id"""
        return self.db.conn.execute("""
            SELECT gp.ts, oc.x, oc.y, gp.student_id
            FROM game_map_opened_cells oc 
            join game_payments gp on gp.cell_id = oc.id
            where oc.command_id = :student_command
            order by gp.ts
        """, locals()).fetchall()

    def set_student_command(self, user_id: int, level: str, command_id: int) -> int:
        """Записать или обновить id команды студента"""
        with self.db.conn as conn:
            cur = conn.execute("""
                INSERT INTO game_students_commands ( student_id,  command_id, level)
                VALUES                             (:user_id, :command_id, :level) 
                on conflict (student_id) do update set 
                command_id = excluded.command_id,
                level = excluded.level
            """, locals())
            return cur.lastrowid

    def get_student_command(self, user_id: int) -> Dict:
        """Получить id команды и её уровень для данного студента.
        Возвращает словарь с ключами {command_id, level}"""
        res = self.db.conn.execute("""
            SELECT
            command_id, level
            from game_students_commands WHERE
            student_id =:user_id
        """, locals()).fetchone()
        return res

    def get_all_students_by_command(self, command_id: int) -> List[int]:
        """Получить id всех студентов данной команды"""
        res = self.db.conn.execute("""
            SELECT
            student_id
            from game_students_commands WHERE
            command_id =:command_id
        """, locals()).fetchall()
        return res and [row['student_id'] for row in res]

    def set_student_flag(self, student_id: int, command_id: int, x: int, y: int) -> int:
        """Обновить координаты флага данного студента (или записать их)"""
        with self.db.conn as conn:
            cur = conn.execute("""
                INSERT INTO game_map_flags ( student_id,  command_id,  x,  y)
                VALUES                     (:student_id, :command_id, :x, :y) 
                on conflict (student_id, command_id) do update set 
                x = excluded.x,
                y = excluded.y
            """, locals())
            return cur.lastrowid

    def get_flags_by_command(self, command_id: int) -> List[dict]:
        """Получить список всех флагов данной команды.
        Возвращает список словарей с ключами x, y"""
        return self.db.conn.execute("""
            SELECT
            x, y
            from game_map_flags WHERE
            command_id =:command_id
        """, locals()).fetchall()

    def get_flag_by_student_and_command(self, user_id: int, command_id: int) -> List[int]:
        """Получить координаты флага данного студента"""
        return self.db.conn.execute("""
            SELECT
            x, y
            from game_map_flags WHERE
            command_id =:command_id and student_id = :user_id
        """, locals()).fetchall()

    def add_student_chest(self, user_id: int, command_id: int, x: int, y: int, bonus: int) -> int:
        """Добавить открытый студентом сундук"""
        ts = datetime.now().isoformat()
        with self.db.conn as conn:
            cur = conn.execute("""
                        INSERT INTO game_map_chests ( ts,  student_id,  command_id,  x,  y,  bonus)
                        VALUES                      (:ts, :user_id,    :command_id, :x, :y, :bonus) 
                        on conflict (student_id, command_id, x, y) do update set 
                        bonus = excluded.bonus
                    """, locals())
            return cur.lastrowid

    def get_student_chests(self, user_id: int, command_id: int) -> List[dict]:
        """Получить список сундуков, которые студент открыл.
        Возвращает список словарей с ключами {ts, bonus, x, y}"""
        return self.db.conn.execute("""
            SELECT
            ts, bonus, x, y
            from game_map_chests WHERE
            command_id = :command_id and student_id = :user_id 
            order by ts
        """, locals()).fetchall()


game = DB_GAME(sql)

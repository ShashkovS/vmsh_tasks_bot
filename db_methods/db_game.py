import sqlite3
from typing import List
from datetime import datetime


class DB_GAME():
    conn: sqlite3.Connection

    def get_student_payments(self, user_id: int) -> List[dict]:
        return self.conn.execute('''
            SELECT ts, amount FROM game_payments
            where student_id = :user_id
            order by ts
        ''', locals()).fetchall()
    def add_payment(self, user_id: int, command_id: int, x: int, y: int, amount: int) -> bool:
        cur = self.conn.cursor()
        ts = datetime.now().isoformat()
        cur = self.conn.cursor()

        try:
            with self.conn:
                self.conn.execute('BEGIN TRANSACTION')
                cur = self.conn.execute('''
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

    def get_opened_cells(self, student_command: int) -> List[dict]:
        return self.conn.execute("""
        SELECT x, y 
        FROM game_map_opened_cells
        where command_id = :student_command
        """, locals()).fetchall()

    def get_opened_cells_timeline (self,student_command: int) -> List[dict]:
        return self.conn.execute("""
        SELECT gp.ts, oc.x, oc.y, gp.student_id
        FROM game_map_opened_cells oc 
        join game_payments gp on gp.cell_id = oc.id
        where oc.command_id = :student_command
        order by gp.ts
        """, locals()).fetchall()

    def set_student_command(self, user_id: int, level: str, command_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute("""
                    INSERT INTO game_students_commands ( student_id,  command_id, level)
                    VALUES                             (:user_id, :command_id, :level) 
                    on conflict (student_id) do update set 
                    command_id = excluded.command_id,
                    level = excluded.level
                """, locals())
        self.conn.commit()
        return cur.lastrowid

    def get_student_command(self, user_id: int) -> int:
        res = self.conn.execute("""
                            SELECT
                            command_id, level
                            from game_students_commands WHERE
                            student_id =:user_id
                        """, locals()).fetchone()
        return res

    def get_all_students_by_command(self, command_id: int) -> List[int]:
        res = self.conn.execute("""
                            SELECT
                            student_id
                            from game_students_commands WHERE
                            command_id =:command_id
                        """, locals()).fetchall()
        return res and [row['student_id'] for row in res]

    def set_student_flag(self, user_id: int, command_id: int, x: int, y: int) -> int:
        self.conn.execute("""
                    INSERT INTO game_map_flags ( student_id,  command_id,  x,  y)
                    VALUES                     (:user_id,    :command_id, :x, :y) 
                    on conflict (student_id, command_id) do update set 
                    x = excluded.x,
                    y = excluded.y
                """, locals())
        self.conn.commit()
        return self.conn.cursor().lastrowid

    def get_flags_by_command(self, command_id: int) -> List[dict]:
        return self.conn.execute("""
            SELECT
            x, y
            from game_map_flags WHERE
            command_id =:command_id
        """, locals()).fetchall()

    def get_flag_by_student_and_command(self, user_id: int, command_id: int) -> List[int]:
        return self.conn.execute("""
            SELECT
            x, y
            from game_map_flags WHERE
            command_id =:command_id and student_id = :user_id
        """, locals()).fetchall()


    def add_student_chest(self, user_id: int, command_id: int, x: int, y: int, bonus: int) -> int:
        ts = datetime.now().isoformat()
        self.conn.execute("""
                    INSERT INTO game_map_chests ( ts,  student_id,  command_id,  x,  y,  bonus)
                    VALUES                      (:ts, :user_id,    :command_id, :x, :y, :bonus) 
                    on conflict (student_id, command_id, x, y) do update set 
                    bonus = excluded.bonus
                """, locals())
        self.conn.commit()
        return self.conn.cursor().lastrowid


    def get_student_chests(self, user_id: int, command_id: int) -> List[dict]:
        return self.conn.execute("""
            SELECT
            ts, bonus, x, y
            from game_map_chests WHERE
            command_id = :command_id and student_id = :user_id 
            order by ts
        """, locals()).fetchall()

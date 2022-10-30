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

    def add_payment(self, user_id: int, x: int, y: int, amount: int) -> bool:
        cur = self.conn.cursor()
        ts = datetime.now().isoformat()
        command_id = self.get_student_command(user_id)
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

    def get_opened_cells(self, user_id: int) -> List[dict]:
        return self.conn.execute("""
        SELECT x, y 
        FROM game_map_opened_cells
        where command_id = (SELECT command_id from game_students_commands WHERE student_id = :user_id)
        """, locals()).fetchall()

    def set_student_command(self, user_id: int, command_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute("""
                    INSERT INTO game_students_commands ( student_id,  command_id)
                    VALUES                             (:user_id, :command_id) 
                    on conflict (student_id) do update set 
                    command_id = excluded.command_id
                """, locals())
        self.conn.commit()
        return cur.lastrowid

    def get_student_command(self, user_id : int) -> int:
        res = self.conn.execute("""
                            SELECT
                            command_id
                            from game_students_commands WHERE
                            student_id =:user_id
                        """, locals()).fetchone()
        return res and res['command_id']

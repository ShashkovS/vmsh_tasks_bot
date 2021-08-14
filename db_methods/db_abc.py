# -*- coding: utf-8 -*-
import sqlite3
import yoyo
import os

DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DB_FILE_FOLDER = 'db'


class DB_CONNECTION:
    """Класс, реализующий все взаимодействия с БД"""
    conn: sqlite3.Connection

    def __init__(self, db_file=None):
        """Инициализация и подключение к базе"""
        self.db_file = None
        if db_file is not None:
            self.setup(db_file)

    @staticmethod
    def get_db_file_full_path(db_file: str):
        return os.path.join(DB_FILE_FOLDER, db_file)

    def setup(self, db_file: str):
        self.db_file = self.get_db_file_full_path(db_file)
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._run_migrations()
        self._connect_to_db()

    @staticmethod
    def _dict_factory(cursor, row: tuple) -> dict:
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _connect_to_db(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = self._dict_factory

    def _run_migrations(self):
        backend = yoyo.get_backend(f'sqlite:///{self.db_file}')
        migrations = yoyo.read_migrations('migrations')
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))

    def disconnect(self):
        if self.conn:
            self.conn.close()

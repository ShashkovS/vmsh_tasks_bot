# -*- coding: utf-8 -*-
import sqlite3
import yoyo
import os

DB_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class _KeyValueStore(dict):
    def __init__(self, conn):
        self.conn = conn
        self.conn.execute("CREATE TABLE IF NOT EXISTS kv (key text unique, value text)")

    def close(self):
        self.conn.commit()
        self.conn.close()

    def __len__(self):
        rows = self.conn.execute('SELECT COUNT(*) cnt FROM kv').fetchone()['cnt']
        return rows if rows is not None else 0

    def iterkeys(self):
        c = self.conn.cursor()
        for row in self.conn.execute('SELECT key FROM kv'):
            yield row['key']

    def itervalues(self):
        c = self.conn.cursor()
        for row in c.execute('SELECT value FROM kv'):
            yield row['value']

    def iteritems(self):
        c = self.conn.cursor()
        for row in c.execute('SELECT key, value FROM kv'):
            yield row['key'], row['value']

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

    def items(self):
        return list(self.iteritems())

    def __contains__(self, key):
        return self.conn.execute('SELECT 1 FROM kv WHERE key = ?', (key,)).fetchone() is not None

    def __getitem__(self, key):
        item = self.conn.execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
        if item is None:
            raise KeyError(key)
        return item['value']

    def pop(self, key, default=None):
        item = self.conn.execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
        if item is None:
            return default
        self.conn.execute('DELETE FROM kv WHERE key = ?', (key,))
        self.conn.commit()
        return item['value']

    def get(self, key, default=None):
        item = self.conn.execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
        if item is None:
            return default
        return item['value']

    def __setitem__(self, key, value):
        self.conn.execute('REPLACE INTO kv (key, value) VALUES (?,?)', (key, value))
        self.conn.commit()

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.conn.execute('DELETE FROM kv WHERE key = ?', (key,))
        self.conn.commit()

    def __iter__(self):
        return self.iterkeys()


class DB_CONNECTION:
    """Класс, реализующий все взаимодействия с БД"""
    conn: sqlite3.Connection

    def __init__(self, db_file=None):
        """Инициализация и подключение к базе"""
        self.db_file = None
        self.kv = None
        self.conn = None
        if db_file is not None:
            self.setup(db_file)

    def setup(self, db_file: str):
        # # Если уже есть подключение, то ничего не делаем
        if self.conn is not None:
            return
        self.db_file = db_file
        if db_file != ':memory:':
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._run_migrations()
        self._connect_to_db()

    # @staticmethod
    # def _dict_factory(cursor, row: tuple) -> dict:
    #     d = {}
    #     for idx, col in enumerate(cursor.description):
    #         d[col[0]] = row[idx]
    #     return d

    def _connect_to_db(self):
        self.conn = sqlite3.connect(self.db_file)
        self.kv = _KeyValueStore(self.conn)
        # Set journal mode to WAL.
        self.conn.execute('PRAGMA journal_mode=WAL')
        # self.conn.row_factory = self._dict_factory
        self.conn.row_factory = sqlite3.Row

    def _run_migrations(self):
        migrations = yoyo.read_migrations('migrations')
        with yoyo.get_backend(f'sqlite:///{self.db_file}') as backend:
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))

    def disconnect(self):
        if self.conn is not None:
            self.conn.rollback()
            self.conn.close()
        self.conn = None


class DB_ABC:
    db: DB_CONNECTION

    def __init__(self, db: DB_CONNECTION):
        self.conn = None
        self.db = db


# Перед использованием объекта db, нужно открыть коннекшн командой вида
# db.sql.setup(db_file="some.db")
sql = DB_CONNECTION()

if __name__ == '__main__':
    sql.setup(':memory:')
    sql.kv['foo'] = 'baz'
    assert sql.kv['foo'] == 'baz'

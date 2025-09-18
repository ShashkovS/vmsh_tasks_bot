from typing import List
from datetime import datetime

from .db_abc import DB_ABC, sql


class DB_SETTINGS(DB_ABC):
    def add_ui_message(self, key: str, value: str):
        change_ts = datetime.now().isoformat()
        with self.db.conn as conn:
            conn.execute("""
                         INSERT INTO z_ui_messages (key, value, change_ts)
                         VALUES (:key, :value, :change_ts)
                         ON CONFLICT (key) DO UPDATE SET value     = :value,
                                                         change_ts = :change_ts
                         """, locals())

    def get_ui_messages(self) -> dict:
        ui_messages_list = self.db.conn.execute("""
                                    SELECT key, value
                                    FROM z_ui_messages
                                    """, locals()).fetchall()
        ui_messages_dict = {
            setting['key']: setting['value']
            for setting in ui_messages_list
        }
        return ui_messages_dict

    def add_setting(self, key: str, value: str):
        change_ts = datetime.now().isoformat()
        with self.db.conn as conn:
            conn.execute("""
                         INSERT INTO z_settings (key, value, change_ts)
                         VALUES (:key, :value, :change_ts)
                         ON CONFLICT (key) DO UPDATE SET value     = :value,
                                                         change_ts = :change_ts
                         """, locals())

    def get_settings(self) -> dict:
        settings_list = self.db.conn.execute("""
                                    SELECT key, value
                                    FROM z_settings
                                    """, locals()).fetchall()
        settings_dict = {
            setting['key']: setting['value']
            for setting in settings_list
        }
        return settings_dict


settings = DB_SETTINGS(sql)

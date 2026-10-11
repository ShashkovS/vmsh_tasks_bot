"""Roster/Zoom input cases, only in guarded E2E state; docs/teacher-work.md."""

import sqlite3
from contextlib import closing

from vmshpwa.scripts.seed_e2e_oral import _require_e2e_target


def seed(config):
    path = _require_e2e_target(config)
    with closing(sqlite3.connect(path)) as connection, connection:
        day = connection.execute(
            "SELECT s.starts_on FROM courses c JOIN seasons s ON s.id=c.season_id WHERE c.id=1"
        ).fetchone()[0]
        for user_id, surname, name in [
            (29101, "Ероховец", "Елена"), (29102, "Зиненко", "Ирина"),
            (29103, "Фетисова", "Александра"),
            (29201, "Агеев", "Юрий"), (29202, "Агеев", "Николай"),
        ]:
            connection.execute(
                "INSERT OR IGNORE INTO users(id,type,surname,name) VALUES(?,2,?,?)",
                (user_id, surname, name),
            )
            if user_id >= 29200:
                continue
            for offset, label in enumerate([f"Принимающий {surname}", f"принимающий {surname.lower()}"]):
                connection.execute(
                    """INSERT OR IGNORE INTO zoom_events(id,event,event_ts,zoom_user_name,zoom_user_id)
                    VALUES(?,'meeting.participant_joined',?,?,?)""",
                    (user_id * 10 + offset, day + "T13:00:00", label, str(user_id)),
                )

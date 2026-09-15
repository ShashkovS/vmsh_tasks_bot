"""Figure layout migration preserves the previous schema on rollback."""

import sqlite3
import yoyo
from db_methods.pwa.migrations import MIGRATIONS_ROOT


def test_figure_layout_migration_up_down_up(tmp_path):
    path = tmp_path / "layout.sqlite3"
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT))
    with yoyo.get_backend(f"sqlite:///{path}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))
            selected = migrations.filter(lambda m: m.id == "0093.pwa_figure_layout")
            backend.rollback_migrations(backend.to_rollback(selected))
            with sqlite3.connect(path) as connection:
                assert not connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='content_figure_layouts'"
                ).fetchall()
            backend.apply_migrations(backend.to_apply(selected))
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA foreign_key_check(content_figure_layouts)").fetchall() == []
        assert (
            connection.execute(
                "SELECT count(*) FROM content_figure_layouts"
            ).fetchone()[0]
            == 0
        )

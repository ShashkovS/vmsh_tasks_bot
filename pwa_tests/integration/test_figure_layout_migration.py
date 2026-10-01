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


def test_figure_presentation_migration_up_down_up(tmp_path):
    path = tmp_path / "presentation.sqlite3"
    migrations = yoyo.read_migrations(str(MIGRATIONS_ROOT))
    selected = migrations.filter(lambda m: m.id == "0106.pwa_figure_presentation")
    with yoyo.get_backend(f"sqlite:///{path}") as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migrations))
            backend.rollback_migrations(backend.to_rollback(selected))
            with sqlite3.connect(path) as connection:
                assert "legacy_scales_json" not in {
                    r[1]
                    for r in connection.execute(
                        "PRAGMA table_info(publication_figure_layouts)"
                    )
                }
            backend.apply_migrations(backend.to_apply(selected))
    with sqlite3.connect(path) as connection:
        assert "legacy_scales_json" in {
            r[1]
            for r in connection.execute("PRAGMA table_info(publication_figure_layouts)")
        }


def test_figure_presentation_migration_freezes_only_legacy_scales():
    """Historical -1 rows keep their visible size and immutable trigger."""
    import json
    import pytest

    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE publication_figure_layouts(publication_id INTEGER, layout_version INTEGER);
        CREATE TABLE lesson_publications(id INTEGER, revision_id INTEGER);
        CREATE TABLE content_figure_scales(revision_id INTEGER, asset_id TEXT, scale REAL);
        INSERT INTO lesson_publications VALUES (1, 10), (2, 10), (3, 20);
        INSERT INTO publication_figure_layouts VALUES (1, -1), (2, 4), (3, -1);
        INSERT INTO content_figure_scales VALUES (10, 'same-file', 0.25);
        CREATE TRIGGER publication_figure_layouts_immutable_update BEFORE UPDATE ON publication_figure_layouts BEGIN SELECT RAISE(ABORT, 'published figure layout is immutable'); END;
    """)
    connection.executescript(
        (MIGRATIONS_ROOT / "0106.pwa_figure_presentation.sql").read_text()
    )
    assert [
        json.loads(r[0])
        for r in connection.execute(
            "SELECT legacy_scales_json FROM publication_figure_layouts ORDER BY publication_id"
        )
    ] == [{"same-file": 0.25}, {}, {}]
    connection.execute("UPDATE content_figure_scales SET scale=2.5")
    assert json.loads(
        connection.execute(
            "SELECT legacy_scales_json FROM publication_figure_layouts WHERE publication_id=1"
        ).fetchone()[0]
    ) == {"same-file": 0.25}
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            "UPDATE publication_figure_layouts SET legacy_scales_json='{}'"
        )
    connection.close()

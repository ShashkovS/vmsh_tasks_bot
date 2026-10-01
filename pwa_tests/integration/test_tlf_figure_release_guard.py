"""TLF cutover data proof; docs/deploy/tlf-app/deploy_figure_layout.sh."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "docs/deploy/tlf-app/figure_layout_data_check.py"


def legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE publication_figure_layouts(publication_id INTEGER, layout_version INTEGER, document_json TEXT);
            CREATE TABLE lesson_publications(id INTEGER, revision_id INTEGER);
            CREATE TABLE content_figure_scales(revision_id INTEGER, asset_id TEXT, scale REAL);
            CREATE TABLE courses(id INTEGER, metadata_model TEXT);
            INSERT INTO courses VALUES (1, 'owner-selected-model');
            INSERT INTO lesson_publications VALUES (1, 10), (2, 10);
            INSERT INTO publication_figure_layouts VALUES (1, -1, '{}'), (2, 4, '{}');
            INSERT INTO content_figure_scales VALUES (10, 'same-file', 0.25);
            CREATE TRIGGER publication_figure_layouts_immutable_update BEFORE UPDATE ON publication_figure_layouts BEGIN SELECT RAISE(ABORT, 'published figure layout is immutable'); END;
        """)


def report(path: Path) -> dict:
    return json.loads(
        subprocess.check_output([sys.executable, str(CHECKER), str(path)])
    )


def migrate(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            (ROOT / "migrations/0106.pwa_figure_presentation.sql").read_text()
        )


def test_release_guard_preserves_old_rows_and_includes_course_models(tmp_path):
    path = tmp_path / "isolated.sqlite3"
    legacy_database(path)
    before = report(path)
    migrate(path)
    assert report(path) == before
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE courses SET metadata_model='different-model'")
    assert report(path)["courses"] != before["courses"]


def test_release_guard_rejects_incorrect_frozen_legacy_scale(tmp_path):
    path = tmp_path / "isolated.sqlite3"
    legacy_database(path)
    migrate(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER publication_figure_layouts_immutable_update")
        connection.execute(
            "UPDATE publication_figure_layouts SET legacy_scales_json='{}'"
        )
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(path)], capture_output=True
    )
    assert result.returncode != 0
    assert b"AssertionError" in result.stderr

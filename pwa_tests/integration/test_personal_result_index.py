"""Measured 0123 lookup index is reversible and never rewrites ledger data."""
import sqlite3
from contextlib import closing

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.progress import COURSE_RESULTS_SQL
from pwa_tests.sqlite_template import create_test_database
from pwa_tests.integration import test_written_result_precedence as projection


def test_result_lookup_index_up_down_up_keeps_data_and_scoped_results(tmp_path):
    path = tmp_path/'index.sqlite3'
    create_test_database(path)
    with closing(sqlite3.connect(path)) as c:
        c.row_factory = sqlite3.Row
        projection._seed(c)
        projection._add(c, 17, 1)
        projection._add(c, 13, 3)
        c.commit()
        before = {table: [tuple(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY 1')]
                  for table in ('results','live_mark_cells','live_mark_results')}
        params = {'student_user_id':projection.STUDENT,'course_id':-1}
        expected = c.execute(COURSE_RESULTS_SQL,params).fetchall()
    migration = next(m for m in yoyo.read_migrations(str(MIGRATIONS_ROOT)) if m.id=='0123.personal_result_lookup')
    backend = yoyo.get_backend(f'sqlite:///{path}')
    with backend.lock():
        backend.rollback_migrations([migration])
        with closing(sqlite3.connect(path)) as c:
            assert not c.execute("SELECT 1 FROM sqlite_schema WHERE name='live_mark_cells_result_idx'").fetchall()
        backend.apply_migrations(backend.to_apply(yoyo.read_migrations(str(MIGRATIONS_ROOT))))
    with closing(sqlite3.connect(path)) as c:
        c.row_factory = sqlite3.Row
        assert {table: [tuple(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY 1')]
                for table in before} == before
        assert [tuple(r) for r in c.execute(COURSE_RESULTS_SQL,params)] == [tuple(r) for r in expected]
        assert any('live_mark_cells_result_idx' in r[3] for r in c.execute('EXPLAIN QUERY PLAN '+COURSE_RESULTS_SQL,params))

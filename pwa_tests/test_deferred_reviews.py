import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest
from db_methods.pwa.deferred_reviews import evidence, hold, restore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript('''
      PRAGMA foreign_keys=ON;
      CREATE TABLE users(id INTEGER PRIMARY KEY);
      CREATE TABLE problems(id INTEGER PRIMARY KEY);
      INSERT INTO users VALUES(1),(2);
      INSERT INTO problems VALUES(1),(2);
      CREATE TABLE submission_threads(id,student_user_id,problem_id,status,version,latest_result_id);
      CREATE TABLE submission_entries(id,thread_id,author_kind,state,version,text);
      CREATE TABLE submission_attachments(id,entry_id,upload_status,asset_id);
      CREATE TABLE media_assets(id,object_key,sha256,byte_size);
      CREATE TABLE submission_review_evidence_entries(entry_id);
      INSERT INTO submission_threads VALUES(1,1,1,'awaiting_review',3,NULL);
      INSERT INTO submission_entries VALUES(1,1,'student','submitted',2,'answer');
      INSERT INTO media_assets VALUES(1,'lost.webp','hash',10);
      INSERT INTO submission_attachments VALUES(1,1,'stored',1);
    ''')
    baseline = (ROOT/'migrations/0111.current_schema.sql').read_text()
    c.executescript(re.search(r'CREATE TABLE written_tasks_queue\s*\(.*?\n\);', baseline, re.S)[0])
    t = ast.parse((ROOT/'migrations/0124.deferred_review_queue.py').read_text())
    definition = next(n for n in t.body if isinstance(n, ast.Assign) and n.targets[0].id == 'steps')
    c.execute(ast.literal_eval(definition.value.elts[0].args[0]))
    c.execute("INSERT INTO written_tasks_queue(id,ts,student_id,problem_id,cur_status,teacher_id,teacher_ts,claim_token,claimed_at,lease_expires_at) VALUES(1,'2026-10-31',1,1,1,2,'2026-11-17','token','2026-11-17T01:00Z','2026-11-17T02:00Z')")
    c.commit()
    yield c
    c.close()


def item(c):
    return {'queue_id': 1, 'student_id': 1, 'problem_id': 1,
            'evidence': evidence(c, 1, 1), 'missing_keys': ['lost.webp']}


def test_hold_restore_preserves_work_and_drops_stale_lease(db):
    before = evidence(db, 1, 1)
    plan = item(db)
    assert hold(db, [plan], batch='incident', now='2026-11-17T03:00Z') == [1]
    assert hold(db, [plan], batch='incident', now='2026-11-17T03:00Z') == []
    assert db.execute('select count(*) from written_tasks_queue').fetchone()[0] == 0
    assert evidence(db, 1, 1) == before
    assert restore(db, batch='incident', now='2026-11-18T03:00Z')['restored'] == [1]
    row = db.execute('select * from written_tasks_queue').fetchone()
    assert row['ts'] == '2026-10-31' and row['cur_status'] == 0
    assert row['teacher_id'] is None and row['claim_token'] is None
    assert evidence(db, 1, 1) == before
    assert restore(db, batch='incident', now='2026-11-18T03:00Z')['restored'] == []


def test_injected_failure_rolls_back_everything(db):
    with pytest.raises(RuntimeError, match='Injected'):
        hold(db, [item(db)], batch='incident', now='now', fail_after=1)
    assert db.execute('select count(*) from written_tasks_queue').fetchone()[0] == 1
    assert db.execute('select count(*) from deferred_review_queue').fetchone()[0] == 0


def test_changed_submission_blocks_hold(db):
    plan = item(db)
    db.execute('update submission_threads set version=4');db.commit()
    with pytest.raises(ValueError, match='Submission changed'):
        hold(db, [plan], batch='incident', now='now')


@pytest.mark.parametrize('conflict', ['new_queue', 'review_completed'])
def test_restore_never_overwrites_new_work(db, conflict):
    hold(db, [item(db)], batch='incident', now='now')
    if conflict == 'new_queue':
        db.execute("INSERT INTO written_tasks_queue(id,ts,student_id,problem_id,cur_status) VALUES(2,'new',1,1,0)")
    else:
        db.execute("UPDATE submission_threads SET status='accepted',version=4,latest_result_id=9")
    db.commit()
    result = restore(db, batch='incident', now='later')
    assert result['restored'] == [] and result['skipped_changed_or_active'] == [1]


def test_available_or_text_only_work_cannot_be_held(db):
    plan = item(db);plan['missing_keys'] = []
    with pytest.raises(ValueError, match='confirmed missing'):
        hold(db, [plan], batch='incident', now='now')

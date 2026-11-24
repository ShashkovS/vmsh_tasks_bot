"""Quarantine/restore queue positions with lost media; see deferred-reviews.md."""
import argparse
import asyncio
from datetime import datetime, UTC
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

p = argparse.ArgumentParser(__doc__)
p.add_argument('action', choices=['plan', 'hold', 'restore', 'list'])
p.add_argument('--code', type=Path, default=Path('/web/vmsh_tasks_bot/vmsh_tasks_bot'))
p.add_argument('--database', type=Path, required=True)
p.add_argument('--manifest', type=Path)
p.add_argument('--batch', default='beget-loss-lesson8-20261117')
p.add_argument('--queue-id', type=int, action='append')
a = p.parse_args()
os.umask(0o077)
spec = importlib.util.spec_from_file_location('deferred', a.code/'db_methods/pwa/deferred_reviews.py')
d = importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
if a.action in {'hold', 'restore'} and os.geteuid() == 0:
    # Keep SQLite WAL/SHM owned by the application, even from a root SSH session.
    owner = a.database.stat()
    os.setgroups([])
    os.setgid(owner.st_gid)
    os.setuid(owner.st_uid)


def connect(readonly=False):
    c = sqlite3.connect('file:'+str(a.database)+('?mode=ro' if readonly else '?mode=rw'), uri=True)
    c.row_factory = sqlite3.Row
    c.execute('pragma foreign_keys=on')
    return c


def storage():
    sys.path.insert(0, str(a.code))
    from helpers.object_storage import S3ObjectStorage
    from helpers.pwa.storage_config import StorageConfig
    cfg = json.loads((a.code/'creds_prod/vmsh_bot_config_prod.json').read_text())
    return S3ObjectStorage(StorageConfig.s3(
        endpoint_url=cfg['s3_url'], bucket_name=cfg['s3_bucket_name'], region=cfg['s3_region'],
        access_key=cfg['s3_access_key'], secret_key=cfg['s3_secret_key'],
        prefix=cfg.get('s3_prefix', ''), public_base_url=cfg['s3_public_base_url'], secret_source='production',
    ))


async def plan():
    s = storage()
    # A failure here must not classify an inaccessible bucket as missing images.
    await s.head('content/sha256/64/f4/64f482ea9a62721253a678dae4deab39dd34a62bf91e8691a2b38005781af72d.svg')
    with connect(True) as c:
        rows = c.execute('SELECT q.id,q.student_id,q.problem_id FROM written_tasks_queue q '
                         'JOIN problem_catalog p ON p.id=q.problem_id WHERE p.lesson=8 ORDER BY q.id').fetchall()
        candidates = [{**dict(r), 'evidence': d.evidence(c, r['student_id'], r['problem_id'])} for r in rows]
    keys = {e['object_key'] for r in candidates for e in r['evidence']['entries'] if e['object_key']}
    sem = asyncio.Semaphore(4)
    async def missing(k):
        async with sem:
            try:await s.head(k);return k, False
            except FileNotFoundError:return k, True
    absent = dict(await asyncio.gather(*(missing(k) for k in keys)))
    selected, retained = [], []
    for r in candidates:
        attached = {e['object_key'] for e in r['evidence']['entries'] if e['object_key']}
        if attached and all(absent[k] for k in attached):
            selected.append({'queue_id': r['id'], 'student_id': r['student_id'], 'problem_id': r['problem_id'],
                             'evidence': r['evidence'], 'missing_keys': sorted(attached)})
        else:retained.append(r['id'])
    result = {'batch': a.batch, 'checked_at': datetime.now(UTC).isoformat(),
              'items': selected, 'retained_queue_ids': retained,
              'object_count': len(keys), 'missing_count': sum(absent.values())}
    assert a.manifest and not a.manifest.exists(), 'Use a new private manifest path'
    a.manifest.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'selected': len(selected), 'retained': len(retained),
                      'checkedObjects': len(keys), 'missingObjects': sum(absent.values())}))


async def restore_checked():
    s = storage()
    with connect(True) as c:
        rows = c.execute('SELECT queue_id,evidence_json FROM deferred_review_queue '
                         'WHERE batch=? AND restored_at IS NULL', (a.batch,)).fetchall()
    expected = {}
    for row in rows:
        if a.queue_id is not None and row['queue_id'] not in a.queue_id:
            continue
        for entry in json.loads(row['evidence_json'])['entries']:
            if entry['object_key']:
                expected[entry['object_key']] = (entry['sha256'], entry['byte_size'])
    for key, (sha, size) in expected.items():
        data = await s.get(key)
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('Recovered object differs from the original; no queue rows restored')
    with connect() as c:
        result = d.restore(c, batch=a.batch, now=datetime.now(UTC).isoformat(), queue_ids=a.queue_id)
    print(json.dumps(result))


if a.action == 'plan':
    asyncio.run(plan())
elif a.action == 'hold':
    manifest = json.loads(a.manifest.read_text())
    assert manifest['batch'] == a.batch
    with connect() as c:
        moved = d.hold(c, manifest['items'], batch=a.batch, now=datetime.now(UTC).isoformat())
    print(json.dumps({'held': len(moved)}))
elif a.action == 'restore':
    asyncio.run(restore_checked())
else:
    with connect(True) as c:
        print(json.dumps([dict(r) for r in c.execute(
            'SELECT queue_id,batch,reason,held_at,restored_at FROM deferred_review_queue WHERE batch=?', (a.batch,))]))

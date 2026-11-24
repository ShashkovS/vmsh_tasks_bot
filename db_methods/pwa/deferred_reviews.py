"""Administrative queue quarantine; docs/deploy/deferred-reviews.md.

Only the operational queue moves. Submission threads/evidence/results are never
changed. The holding table stays inside the normal encrypted SQLite backup.
"""
import json
import sqlite3


def evidence(connection, student_id, problem_id):
    threads = [dict(r) for r in connection.execute(
        "SELECT id,status,version,latest_result_id FROM submission_threads "
        "WHERE student_user_id=? AND problem_id=? ORDER BY id",
        (student_id, problem_id),
    )]
    entries = [dict(r) for r in connection.execute(
        "SELECT e.id,e.version,length(e.text) text_length,a.id attachment_id,a.upload_status,"
        "m.id asset_id,m.object_key,m.sha256,m.byte_size "
        "FROM submission_threads t JOIN submission_entries e ON e.thread_id=t.id "
        "LEFT JOIN submission_attachments a ON a.entry_id=e.id "
        "LEFT JOIN media_assets m ON m.id=a.asset_id "
        "WHERE t.student_user_id=? AND t.problem_id=? AND e.author_kind='student' "
        "AND e.state='submitted' AND NOT EXISTS "
        "(SELECT 1 FROM submission_review_evidence_entries v WHERE v.entry_id=e.id) "
        "ORDER BY e.id,a.id", (student_id, problem_id),
    )]
    return {'threads': threads, 'entries': entries}


def hold(connection, items, *, batch, now, fail_after=None):
    """Guard a reviewed missing-object manifest and move rows atomically."""
    if connection.in_transaction:
        raise ValueError('An independent transaction is required')
    connection.row_factory = sqlite3.Row
    connection.execute('BEGIN IMMEDIATE')
    moved = []
    try:
        for item in items:
            row = connection.execute('SELECT * FROM written_tasks_queue WHERE id=?',
                                     (item['queue_id'],)).fetchone()
            if row is None:
                previous = connection.execute(
                    'SELECT batch,restored_at FROM deferred_review_queue WHERE queue_id=?',
                    (item['queue_id'],),
                ).fetchone()
                if previous and previous['batch'] == batch and previous['restored_at'] is None:
                    continue
                raise ValueError('Queue changed; rebuild the manifest')
            row = dict(row)
            if (row['student_id'], row['problem_id']) != (item['student_id'], item['problem_id']):
                raise ValueError('Queue identity changed')
            if evidence(connection, row['student_id'], row['problem_id']) != item['evidence']:
                raise ValueError('Submission changed; rebuild the manifest')
            keys = {e['object_key'] for e in item['evidence']['entries'] if e['object_key']}
            if not keys or keys != set(item['missing_keys']):
                raise ValueError('All attached objects must be confirmed missing')
            connection.execute(
                'INSERT INTO deferred_review_queue VALUES (?,?,?,?,?,?,?,?,NULL)',
                (row['id'], batch, row['student_id'], row['problem_id'],
                 json.dumps(row, ensure_ascii=False), json.dumps(item['evidence'], ensure_ascii=False),
                 'beget_object_loss', now),
            )
            connection.execute('DELETE FROM written_tasks_queue WHERE id=?', (row['id'],))
            moved.append(row['id'])
            if fail_after and len(moved) >= fail_after:
                raise RuntimeError('Injected failure')
        connection.commit()
        return moved
    except BaseException:
        connection.rollback()
        raise


def restore(connection, *, batch, now, queue_ids=None):
    """Restore only unchanged/ungraded work; never revive an expired claim."""
    connection.row_factory = sqlite3.Row
    connection.execute('BEGIN IMMEDIATE')
    restored, skipped = [], []
    try:
        for item in connection.execute(
            'SELECT * FROM deferred_review_queue WHERE batch=? AND restored_at IS NULL ORDER BY queue_id',
            (batch,),
        ).fetchall():
            if queue_ids is not None and item['queue_id'] not in queue_ids:
                continue
            conflict = connection.execute(
                'SELECT 1 FROM written_tasks_queue WHERE id=? OR (student_id=? AND problem_id=?)',
                (item['queue_id'], item['student_id'], item['problem_id']),
            ).fetchone()
            if conflict or evidence(connection, item['student_id'], item['problem_id']) != json.loads(item['evidence_json']):
                skipped.append(item['queue_id'])
                continue
            row = json.loads(item['queue_json'])
            # PRAGMA table_info omits the generated public_id column.
            columns = [r['name'] for r in connection.execute('PRAGMA table_info(written_tasks_queue)')]
            row.update(cur_status=0, teacher_id=None, teacher_ts=None, claim_token=None,
                       claimed_at=None, lease_expires_at=None,
                       lease_version=row['lease_version'] + 1, updated_at=now)
            connection.execute(
                'INSERT INTO written_tasks_queue (' + ','.join(columns) + ') VALUES (' +
                ','.join('?' for _ in columns) + ')', [row[c] for c in columns],
            )
            connection.execute('UPDATE deferred_review_queue SET restored_at=? WHERE queue_id=?',
                               (now, item['queue_id']))
            restored.append(item['queue_id'])
        connection.commit()
        return {'restored': restored, 'skipped_changed_or_active': skipped}
    except BaseException:
        connection.rollback()
        raise

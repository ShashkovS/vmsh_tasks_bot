"""Whole-entry transfer storage; policy in models.pwa.review_transfers.

See vmshpwa/docs/serial-review-feed.md. All mutations share one transaction.
"""

import json


def source(connection, entry_id):
    return connection.execute(
        """
        SELECT e.*, t.student_user_id, t.problem_id, t.version AS thread_version,
        t.status AS thread_status, t.latest_result_id, (SELECT verdict FROM results WHERE id=t.latest_result_id) AS latest_verdict,
        p.public_id AS problem_public_id, p.group_id, p.lesson,
        p.prob, p.item, p.title, g.short_code, g.public_id AS group_public_id,
        c.public_id AS course_public_id, u.name, u.surname,
        EXISTS(SELECT 1 FROM submission_review_evidence_entries x WHERE x.entry_id=e.id) AS reviewed,
        EXISTS(SELECT 1 FROM submission_material_reassignment_items x WHERE x.source_entry_id=e.id) AS was_reassigned
        FROM submission_entries e JOIN submission_threads t ON t.id=e.thread_id
        JOIN problems p ON p.id=t.problem_id JOIN groups g ON g.group_id=p.group_id
        JOIN courses c ON c.id=g.course_id JOIN users u ON u.id=t.student_user_id
        WHERE e.public_id=?
    """,
        (entry_id,),
    ).fetchone()


def targets(connection, src):
    return connection.execute(
        """
        SELECT p.id, p.public_id, p.title, p.lesson, p.prob, p.item, g.short_code,
        revision.id AS revision_id, revision.content_revision_id,
        t.id AS thread_id, t.public_id AS thread_public_id, coalesce(t.version,0) AS thread_version,
        t.latest_result_id, t.status AS thread_status
        FROM problems p JOIN groups g ON g.group_id=p.group_id
        JOIN problem_revisions revision ON revision.id=(
          SELECT pr.id FROM problem_revisions pr JOIN content_revisions cr
          ON cr.id=pr.content_revision_id AND cr.status='ready'
          WHERE pr.problem_id=p.id ORDER BY pr.id DESC LIMIT 1)
        LEFT JOIN submission_threads t ON t.id=(SELECT id FROM submission_threads
          WHERE student_user_id=? AND problem_id=p.id ORDER BY id DESC LIMIT 1)
        WHERE p.group_id=? AND p.lesson=? AND p.id<>? AND p.prob_type IN (2,3,4)
        AND revision.problem_type IN (2,3,4) AND p.prob>0
        AND NOT EXISTS (SELECT 1 FROM problem_synonym_members a
          JOIN problem_synonym_members b ON b.synonym_group_id=a.synonym_group_id
          JOIN problem_synonym_groups sg ON sg.id=a.synonym_group_id AND sg.status='active'
          WHERE a.problem_id=? AND b.problem_id=p.id AND a.removed_at IS NULL AND b.removed_at IS NULL)
        ORDER BY p.prob,p.item,p.id
    """,
        (
            src["student_user_id"],
            src["group_id"],
            src["lesson"],
            src["problem_id"],
            src["problem_id"],
        ),
    ).fetchall()


def attachments(connection, entry_id):
    return connection.execute(
        "SELECT * FROM submission_attachments WHERE entry_id=? ORDER BY ordinal,id",
        (entry_id,),
    ).fetchall()


def queued_target_case(connection, student, problem):
    return connection.execute(
        """SELECT q.public_id FROM written_tasks_queue q
      WHERE q.student_id=? AND (q.problem_id=? OR EXISTS(
        SELECT 1 FROM problem_synonym_members a JOIN problem_synonym_members b
        ON b.synonym_group_id=a.synonym_group_id JOIN problem_synonym_groups sg
        ON sg.id=a.synonym_group_id AND sg.status='active'
        WHERE a.problem_id=? AND b.problem_id=q.problem_id
        AND a.removed_at IS NULL AND b.removed_at IS NULL)) ORDER BY q.id LIMIT 1""",
        (student, problem, problem),
    ).fetchone()


def replay(connection, actor, key):
    return connection.execute(
        "SELECT * FROM submission_entry_transfers WHERE actor_user_id=? AND idempotency_key=?",
        (actor, key),
    ).fetchone()


def label(row):
    return f"{row['lesson']}{row['short_code']}.{row['prob']}{row['item'] or ''} · {row['title'] or ''}"


def release_remaining(connection, actor, token, now):
    connection.execute(
        """UPDATE written_tasks_queue SET cur_status=0,
      teacher_id=NULL,teacher_ts=NULL,claim_token=NULL,claimed_at=NULL,
      lease_expires_at=NULL,lease_version=lease_version+1,updated_at=?
      WHERE teacher_id=? AND claim_token=?""",
        (now, actor, token),
    )


def commit(
    connection,
    src,
    target,
    photos,
    *,
    actor,
    key,
    digest,
    mode,
    now,
    notices,
    empty_source_status,
):
    target_thread = target["thread_id"]
    if target_thread is None:
        target_thread = connection.execute(
            """INSERT INTO submission_threads
          (student_user_id,problem_id,condition_revision_id,status,latest_entry_at,created_at,updated_at)
          VALUES(?,?,?,'awaiting_review',?,?,?) RETURNING id""",
            (
                src["student_user_id"],
                target["id"],
                target["content_revision_id"],
                now,
                now,
                now,
            ),
        ).fetchone()["id"]
    # Draft first: photo-only submissions become nonempty after the attachment insert.
    entry = connection.execute(
        """INSERT INTO submission_entries
      (thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,
       client_created_at,server_received_at)
      VALUES(?,?,'student',?,'staff','submission','draft',?,?,?) RETURNING id,public_id""",
        (
            target_thread,
            target["revision_id"],
            src["student_user_id"],
            src["text"],
            src["client_created_at"],
            now,
        ),
    ).fetchone()
    for photo in photos:
        connection.execute(
            """INSERT INTO submission_attachments
          (entry_id,asset_id,ordinal,client_filename,upload_status,created_at)
          VALUES(?,?,?,?,'stored',?)""",
            (
                entry["id"],
                photo["asset_id"],
                photo["ordinal"],
                photo["client_filename"],
                now,
            ),
        )
    connection.execute(
        "UPDATE submission_entries SET state='submitted',version=version+1 WHERE id=?",
        (entry["id"],),
    )
    response = {
        "schemaVersion": 1,
        "mode": mode,
        "sourceEntryId": src["public_id"],
        "targetEntryId": entry["public_id"],
        "targetProblemId": target["public_id"],
        "targetLabel": label(target),
    }
    connection.execute(
        """INSERT INTO submission_entry_transfers
      (actor_user_id,idempotency_key,payload_sha256,mode,source_entry_id,target_entry_id,created_at,response_json)
      VALUES(?,?,?,?,?,?,?,?)""",
        (actor, key, digest, mode, src["id"], entry["id"], now, json.dumps(response)),
    )
    if mode == "move":
        connection.execute(
            "UPDATE submission_entries SET state='deleted',deleted_at=?,version=version+1 WHERE id=?",
            (now, src["id"]),
        )
    for thread_id, text in [
        (src["thread_id"], notices[0]),
        (target_thread, notices[1]),
    ]:
        connection.execute(
            """INSERT INTO submission_entries
          (thread_id,author_kind,channel,entry_kind,state,text,server_received_at)
          VALUES(?,'system','system','system_event','submitted',?,?)""",
            (thread_id, text, now),
        )
        connection.execute(
            "UPDATE submission_threads SET version=version+1,latest_entry_at=?,updated_at=? WHERE id=?",
            (now, now, thread_id),
        )
    connection.execute(
        "UPDATE submission_threads SET status='awaiting_review',version=version+1 WHERE id=?",
        (target_thread,),
    )
    connection.execute(
        """INSERT INTO written_tasks_queue(ts,student_id,problem_id,cur_status,updated_at)
      VALUES(?,?,?,0,?) ON CONFLICT(student_id,problem_id) DO UPDATE SET updated_at=excluded.updated_at""",
        (now, src["student_user_id"], target["id"], now),
    )
    if mode == "move":
        remaining = connection.execute(
            """SELECT 1 FROM submission_entries e WHERE e.thread_id=?
          AND e.author_kind='student' AND e.state='submitted' AND NOT EXISTS
          (SELECT 1 FROM submission_review_evidence_entries x WHERE x.entry_id=e.id) LIMIT 1""",
            (src["thread_id"],),
        ).fetchone()
        if remaining is None:
            connection.execute(
                "DELETE FROM written_tasks_queue WHERE student_id=? AND problem_id=?",
                (src["student_user_id"], src["problem_id"]),
            )
            connection.execute(
                "UPDATE submission_threads SET status=?,version=version+1 WHERE id=?",
                (empty_source_status, src["thread_id"]),
            )
    return response

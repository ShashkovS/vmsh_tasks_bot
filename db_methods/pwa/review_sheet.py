"""SQLite reads/writes for the sheet; policy: models.pwa.review_sheet.

See vmshpwa/docs/review-sheet.md. No leases are created by these reads.
"""

from db_methods.pwa import review_corrections as corrections


THREAD_SELECT = """
SELECT t.*, p.public_id AS problem_public_id, p.group_id, p.lesson, p.prob,
 p.item, p.title, p.prob_type, pg.logical_key,
 g.public_id AS group_public_id, g.public_name AS group_name, g.short_code,
 g.color_key, c.public_id AS course_public_id, c.name AS course_name,
 u.public_id AS student_public_id, u.name, u.surname,
 (SELECT min(peer.id) FROM submission_threads peer
  JOIN result_problem_groups pp ON pp.problem_id=peer.problem_id
  WHERE peer.student_user_id=t.student_user_id AND pp.logical_key=pg.logical_key) AS anchor_id
FROM submission_threads t JOIN problem_catalog p ON p.id=t.problem_id
JOIN result_problem_groups pg ON pg.problem_id=p.id
JOIN groups g ON g.group_id=p.group_id JOIN courses c ON c.id=g.course_id
JOIN users u ON u.id=t.student_user_id
"""


def lessons(connection):
    return connection.execute(
        """SELECT gl.public_id AS lesson_id, gl.group_id, cl.lesson_number AS lesson,
        g.public_id AS group_public_id, g.public_name AS group_name, g.short_code,
        c.public_id AS course_public_id, c.name AS course_name
        FROM group_lessons gl JOIN course_lessons cl ON cl.id=gl.course_lesson_id
        JOIN groups g ON g.group_id=gl.group_id JOIN courses c ON c.id=gl.course_id
        ORDER BY c.sort_order,c.id,cl.lesson_number,g.sort_order,g.group_id"""
    ).fetchall()


def lesson(connection, lesson_id):
    return next(
        (row for row in lessons(connection) if row["lesson_id"] == lesson_id), None
    )


def problem_lesson(connection, problem_id):
    return connection.execute(
        """SELECT gl.public_id FROM group_lessons gl
        JOIN course_lessons cl ON cl.id=gl.course_lesson_id
        JOIN problem_catalog p ON p.group_id=gl.group_id AND p.lesson=cl.lesson_number
        WHERE p.public_id=?""",
        (problem_id,),
    ).fetchone()


def problems(connection, selected):
    return connection.execute(
        """SELECT p.*, g.short_code FROM problem_catalog p
        JOIN groups g ON g.group_id=p.group_id
        WHERE p.group_id=? AND p.lesson=? AND p.prob>0 AND p.prob_type IN (2,3,4)
        ORDER BY p.prob,p.item,p.id""",
        (selected["group_id"], selected["lesson"]),
    ).fetchall()


def _group_id(connection, selected):
    return connection.execute(
        "SELECT group_id FROM groups WHERE public_id=?", (selected["group_public_id"],)
    ).fetchone()["group_id"]


def lesson_threads(connection, selected):
    return connection.execute(
        THREAD_SELECT + " WHERE p.group_id=? AND p.lesson=? AND p.prob>0 "
        "AND p.prob_type IN (2,3,4) ORDER BY p.prob,p.item,t.created_at,u.surname,u.name,t.id",
        (_group_id(connection, selected), selected["lesson"]),
    ).fetchall()


def case_threads(connection, case_id):
    return connection.execute(
        THREAD_SELECT
        + """ WHERE (t.student_user_id,pg.logical_key)=(
        SELECT a.student_user_id,ag.logical_key FROM submission_threads a
        JOIN result_problem_groups ag ON ag.problem_id=a.problem_id WHERE a.public_id=?)
        ORDER BY p.lesson,p.prob,p.item,t.id""",
        (case_id,),
    ).fetchall()


def queues(connection, threads):
    return connection.execute(
        "SELECT * FROM written_tasks_queue WHERE student_id=? AND problem_id IN ("
        + ",".join("?" for _ in threads)
        + ") ORDER BY ts,id",
        (threads[0]["student_user_id"], *(row["problem_id"] for row in threads)),
    ).fetchall()


def latest_review(connection, threads):
    return connection.execute(
        """SELECT DISTINCT r.*, u.name AS teacher_name,u.surname AS teacher_surname,
        comment.text AS comment FROM submission_reviews r
        JOIN submission_review_evidence_entries x ON x.review_id=r.id
        JOIN users u ON u.id=r.reviewer_user_id
        LEFT JOIN submission_entries comment ON comment.id=r.comment_entry_id
        WHERE x.thread_id IN ("""
        + ",".join("?" for _ in threads)
        + ") ORDER BY r.id DESC LIMIT 1",
        tuple(row["id"] for row in threads),
    ).fetchone()


def latest_result(connection, threads):
    return connection.execute(
        """SELECT r.id FROM results r JOIN result_problem_groups pg ON pg.problem_id=r.problem_id
        WHERE r.student_id=? AND pg.logical_key=? AND r.res_type IN (2,3,4) ORDER BY r.id DESC LIMIT 1""",
        (threads[0]["student_user_id"], threads[0]["logical_key"]),
    ).fetchone()


def entries(connection, thread_id, *, review_id=None):
    clause = (
        "AND EXISTS(SELECT 1 FROM submission_review_evidence_entries x WHERE x.entry_id=e.id AND x.review_id=?)"
        if review_id is not None
        else "AND e.state='submitted' AND NOT EXISTS(SELECT 1 FROM submission_review_evidence_entries x WHERE x.entry_id=e.id)"
    )
    return connection.execute(
        "SELECT e.* FROM submission_entries e WHERE e.thread_id=? AND e.author_kind='student' "
        "AND e.entry_kind IN ('text','submission') "
        + clause
        + " ORDER BY e.server_received_at,e.id",
        (thread_id, review_id) if review_id is not None else (thread_id,),
    ).fetchall()


def attachments(connection, entry_id, *, review_id=None):
    if review_id is not None:
        return connection.execute(
            """SELECT a.* FROM submission_review_evidence_attachments x
            JOIN submission_attachments a ON a.id=x.attachment_id
            WHERE x.review_id=? AND x.entry_id=? ORDER BY x.ordinal,a.id""",
            (review_id, entry_id),
        ).fetchall()
    return connection.execute(
        "SELECT * FROM submission_attachments WHERE entry_id=? ORDER BY ordinal,id",
        (entry_id,),
    ).fetchall()


def annotations(connection, review_id):
    return connection.execute(
        """SELECT n.*,a.public_id AS attachment_public_id FROM submission_review_annotations n
        JOIN submission_attachments a ON a.id=n.attachment_id WHERE n.review_id=? ORDER BY n.id""",
        (review_id,),
    ).fetchall()


def store_evidence(connection, review_id, rows):
    for thread, entry, photos in rows:
        connection.execute(
            """INSERT INTO submission_review_evidence_entries
            (review_id,entry_id,thread_id,problem_id,entry_version,server_received_at)
            VALUES(?,?,?,?,?,?)""",
            (
                review_id,
                entry["id"],
                thread["id"],
                thread["problem_id"],
                entry["version"],
                entry["server_received_at"],
            ),
        )
        for photo in photos:
            connection.execute(
                """INSERT INTO submission_review_evidence_attachments
                (review_id,attachment_id,entry_id,asset_id,ordinal) VALUES(?,?,?,?,?)""",
                (
                    review_id,
                    photo["id"],
                    entry["id"],
                    photo["asset_id"],
                    photo["ordinal"],
                ),
            )


def finish_pending(
    connection,
    threads,
    queue_rows,
    target_thread,
    result_id,
    status,
    comment_created,
    now,
):
    # Follow the existing completion transition, including closing synonym peers.
    for thread in threads:
        if thread["status"] != "awaiting_review":
            continue
        is_target = thread["id"] == target_thread["id"]
        connection.execute(
            """UPDATE submission_threads SET status=?,latest_result_id=?,updated_at=?,
            latest_entry_at=CASE WHEN ? THEN ? ELSE latest_entry_at END,version=version+1 WHERE id=?""",
            (
                status if is_target else "closed",
                result_id if is_target else None,
                now,
                is_target and comment_created,
                now,
                thread["id"],
            ),
        )
    connection.executemany(
        "DELETE FROM written_tasks_queue WHERE id=?", [(r["id"],) for r in queue_rows]
    )


def store_reaction(connection, review_id, actor, reaction_id, now, until):
    connection.execute(
        """INSERT INTO submission_review_internal_reactions
        (review_id,actor_user_id,reaction_id,created_at,editable_until,updated_at,version)
        VALUES(?,?,?,?,?,?,1)""",
        (review_id, actor, reaction_id, now, until, now),
    )
    connection.execute(
        """INSERT INTO submission_review_internal_reaction_events
        (review_id,actor_user_id,event_kind,reaction_id,state_version,created_at)
        VALUES(?,?,'selected',?,1,?)""",
        (review_id, actor, reaction_id, now),
    )


def review_receipt_rows(connection, review_id):
    return connection.execute(
        """SELECT e.public_id,p.public_id AS problem_public_id FROM submission_review_evidence_entries x
        JOIN submission_entries e ON e.id=x.entry_id JOIN problem_catalog p ON p.id=x.problem_id
        WHERE x.review_id=? ORDER BY x.server_received_at,x.entry_id""",
        (review_id,),
    ).fetchall()


def reviewer(connection, actor):
    return connection.execute("SELECT type FROM users WHERE id=?", (actor,)).fetchone()


def reaction_exists(connection, reaction_id):
    return (
        connection.execute(
            "SELECT 1 FROM reaction_enum WHERE reaction_id=? AND reaction_type_id=100",
            (reaction_id,),
        ).fetchone()
        is not None
    )


def review_reaction(connection, review_id):
    return connection.execute(
        "SELECT * FROM submission_review_internal_reactions WHERE review_id=?",
        (review_id,),
    ).fetchone()


def replay(connection, actor, key):
    return corrections.find_replay(connection, actor, key)

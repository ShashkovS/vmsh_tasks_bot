"""Focused private assistant persistence; vmshpwa/docs/ai-review-assistant.md."""


def read_snapshot(connection, operation):
    """One SQLite snapshot for multi-query context and scope checks (ADR 0002)."""
    if connection.in_transaction:
        return operation(connection)
    connection.execute("BEGIN")
    try:
        return operation(connection)
    finally:
        connection.execute("ROLLBACK")


def token_owner(connection, secret_hash):
    return connection.execute(
        """SELECT t.*, a.public_id AS account_public_id, a.status AS account_status,
        a.audience, a.credential_version AS current_credential_version,
        a.linked_user_id, u.type AS user_type
        FROM ai_review_tokens t JOIN auth_accounts a ON a.id=t.account_id
        JOIN users u ON u.id=a.linked_user_id WHERE t.secret_hash=?""",
        (secret_hash,),
    ).fetchone()


def staff_grants(connection, user_id):
    return connection.execute(
        """SELECT s.*, c.public_id AS course_public_id, g.public_id AS group_public_id
        FROM staff_scopes s JOIN courses c ON c.id=s.course_id
        LEFT JOIN groups g ON g.course_id=s.course_id AND g.group_id=s.group_id
        WHERE s.staff_user_id=?""",
        (user_id,),
    ).fetchall()


def list_tokens(connection, account_public_id):
    return connection.execute(
        """SELECT public_id AS tokenId,name,created_at AS createdAt,
        expires_at AS expiresAt,revoked_at AS revokedAt
        FROM ai_review_tokens WHERE account_id=(SELECT id FROM auth_accounts WHERE public_id=?)
        ORDER BY id DESC""",
        (account_public_id,),
    ).fetchall()


def insert_token(
    connection,
    *,
    public_id,
    account_public_id,
    name,
    secret_hash,
    now,
    expires,
    credential_version,
):
    cursor = connection.execute(
        """INSERT INTO ai_review_tokens
        (public_id,account_id,credential_version,name,secret_hash,created_at,expires_at)
        SELECT ?,id,credential_version,?,?,?,? FROM auth_accounts
        WHERE public_id=? AND audience='staff' AND status='active' AND credential_version=?""",
        (
            public_id,
            name,
            secret_hash,
            now,
            expires,
            account_public_id,
            credential_version,
        ),
    )
    if cursor.rowcount != 1:
        raise PermissionError("inactive_staff_account")
    return cursor.lastrowid


def revoke_token(connection, account_public_id, token_id, now):
    connection.execute(
        """UPDATE ai_review_tokens SET revoked_at=coalesce(revoked_at,?)
        WHERE public_id=? AND account_id=(SELECT id FROM auth_accounts WHERE public_id=?)""",
        (now, token_id, account_public_id),
    )
    return connection.execute(
        """SELECT t.id,t.account_id FROM ai_review_tokens t JOIN auth_accounts a ON a.id=t.account_id
        WHERE t.public_id=? AND a.public_id=?""",
        (token_id, account_public_id),
    ).fetchone()


def event(connection, *, account_id, token_id, kind, subject, now):
    connection.execute(
        "INSERT INTO ai_review_events(account_id,token_id,event,subject_id,created_at) VALUES(?,?,?,?,?)",
        (account_id, token_id, kind, subject, now),
    )


def existing_suggestion(connection, token_id, key):
    return connection.execute(
        "SELECT * FROM ai_review_suggestions WHERE token_id=? AND idempotency_key=?",
        (token_id, key),
    ).fetchone()


def has_current_suggestion(connection, case_id, snapshot):
    return (
        connection.execute(
            "SELECT 1 FROM ai_review_suggestions WHERE case_id=? AND snapshot=? LIMIT 1",
            (case_id, snapshot),
        ).fetchone()
        is not None
    )


def queue_anchor(connection, queue_id):
    return connection.execute(
        """SELECT min(t.id) AS anchor_id FROM written_tasks_queue q
        JOIN result_problem_groups pg ON pg.problem_id=q.problem_id
        JOIN submission_threads t ON t.student_user_id=q.student_id
        JOIN result_problem_groups peer ON peer.problem_id=t.problem_id AND peer.logical_key=pg.logical_key
        WHERE q.public_id=?""",
        (queue_id,),
    ).fetchone()


def suggestions(connection, case_id, before=None):
    return connection.execute(
        """SELECT s.*,t.name AS uploader FROM ai_review_suggestions s
        JOIN ai_review_tokens t ON t.id=s.token_id
        WHERE s.case_id=? AND (? IS NULL OR s.id<?) ORDER BY s.id DESC LIMIT 51""",
        (case_id, before, before),
    ).fetchall()


def insert_suggestion(connection, values):
    connection.execute(
        """INSERT INTO ai_review_suggestions
        (public_id,token_id,case_thread_id,case_id,snapshot,idempotency_key,payload_hash,comment,verdict,analysis,source,model,created_at)
        VALUES(:public_id,:token_id,:case_thread_id,:case_id,:snapshot,:idempotency_key,:payload_hash,:comment,:verdict,:analysis,:source,:model,:created_at)""",
        values,
    )


def pending_cases(connection):
    return connection.execute(
        """SELECT q.public_id AS queue_id,p.public_id AS problem_id,u.public_id AS student_id,
        c.public_id AS course_public_id,g.public_id AS group_public_id,
        gl.public_id AS lesson_id,q.ts AS submitted_at,
        (SELECT min(peer.id) FROM submission_threads peer
         JOIN result_problem_groups pp ON pp.problem_id=peer.problem_id
         WHERE peer.student_user_id=q.student_id AND pp.logical_key=pg.logical_key) AS anchor_id
        FROM written_tasks_queue q JOIN problem_catalog p ON p.id=q.problem_id
        JOIN result_problem_groups pg ON pg.problem_id=p.id
        JOIN users u ON u.id=q.student_id JOIN groups g ON g.group_id=p.group_id
        JOIN courses c ON c.id=g.course_id
        LEFT JOIN course_lessons cl ON cl.course_id=c.id AND cl.lesson_number=p.lesson
        LEFT JOIN group_lessons gl ON gl.group_id=g.group_id AND gl.course_lesson_id=cl.id
        WHERE q.problem_id>0 ORDER BY q.ts,q.id"""
    ).fetchall()


def problem_rows(connection):
    return connection.execute(
        """SELECT p.*,g.public_id AS group_public_id,c.public_id AS course_public_id,
        gl.public_id AS lesson_id FROM problem_catalog p
        JOIN groups g ON g.group_id=p.group_id JOIN courses c ON c.id=g.course_id
        LEFT JOIN course_lessons cl ON cl.course_id=c.id AND cl.lesson_number=p.lesson
        LEFT JOIN group_lessons gl ON gl.group_id=g.group_id AND gl.course_lesson_id=cl.id
        ORDER BY c.sort_order,c.id,p.lesson,g.sort_order,p.prob,p.item,p.id"""
    ).fetchall()


def course_groups(connection):
    return connection.execute(
        """SELECT c.public_id AS course_public_id,c.name AS course_name,
        g.public_id AS group_public_id,g.public_name AS group_name
        FROM courses c LEFT JOIN groups g ON g.course_id=c.id
        ORDER BY c.sort_order,c.id,g.sort_order,g.group_id"""
    ).fetchall()


def learning_materials(connection, problem_id, revision_id=None):
    return connection.execute(
        """SELECT cr.public_id AS revision_id,cr.version,cs.kind,d.content_text,m.source_ordinal,
        pr.id AS problem_revision_id,pr.answer_config_json,pr.answer_type
        FROM content_problem_matches m
        JOIN content_revisions cr ON cr.id=m.content_revision_id
        JOIN content_sources cs ON cs.id=cr.source_id
        LEFT JOIN problem_revisions pr ON pr.content_revision_id=cr.id AND pr.problem_id=m.problem_id
        JOIN content_derivatives d ON d.revision_id=cr.id AND d.kind='web_ast' AND d.invalidated_at IS NULL
        WHERE m.problem_id=? AND m.resolved_at IS NOT NULL AND m.decision<>'omit'
        AND cs.kind IN ('condition','hint','solution')
        AND (? IS NULL OR cs.kind<>'condition' OR pr.id=?)
        ORDER BY cr.id DESC,d.id DESC""",
        (problem_id, revision_id, revision_id),
    ).fetchall()


def material_images(connection, revision_id):
    return connection.execute(
        """SELECT m.public_id,m.object_key,m.media_type,m.byte_size,m.sha256,a.logical_name
        FROM content_revision_assets a JOIN media_assets m ON m.id=a.asset_id
        JOIN content_revisions r ON r.id=a.revision_id
        WHERE r.public_id=? AND a.role IN ('figure','tikz','preview') ORDER BY a.ordinal,a.logical_name""",
        (revision_id,),
    ).fetchall()


def answer_revision(connection, problem_id, revision_id=None):
    return connection.execute(
        """SELECT pr.id,pr.config_version,pr.answer_type,pr.answer_config_json,
        cr.public_id AS revision_id FROM problem_revisions pr
        JOIN content_revisions cr ON cr.id=pr.content_revision_id
        WHERE pr.problem_id=? AND (? IS NULL OR pr.id=?) ORDER BY pr.id DESC LIMIT 1""",
        (problem_id, revision_id, revision_id),
    ).fetchone()


def verdicts(connection, ids):
    return connection.execute(
        "SELECT id,tick,val FROM verdicts WHERE id IN ("
        + ",".join("?" for _ in ids)
        + ") ORDER BY id",
        tuple(ids),
    ).fetchall()

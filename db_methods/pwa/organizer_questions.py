"""SQLite queries for account-owned correspondence; docs/organizer-questions.md."""

from helpers.consts import USER_TYPE


def one(c, sql, args=()):
    row = c.execute(sql, args).fetchone()
    return dict(row) if row else None


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


def account(c, public_id):
    return one(c, "SELECT * FROM auth_accounts WHERE public_id=?", (public_id,))


def child(c, account_id, public_id):
    return one(
        c,
        "SELECT u.id FROM users u JOIN family_student_links l ON l.student_user_id=u.id WHERE l.family_account_id=? AND u.public_id=? AND l.revoked_at IS NULL",
        (account_id, public_id),
    )


QUESTION = """SELECT q.*, a.public_id owner_public_id, a.audience owner_audience,
 COALESCE(a.display_name, u.surname || ' ' || u.name, a.username) owner_name,
 ch.public_id child_public_id, ch.surname || ' ' || ch.name child_name,
 e.text latest_text, e.created_at latest_at, e.author_account_id latest_author,
 (SELECT text FROM organizer_question_entries WHERE question_id=q.id ORDER BY id LIMIT 1) first_text
 FROM organizer_questions q JOIN auth_accounts a ON a.id=q.owner_account_id
 LEFT JOIN users u ON u.id=a.linked_user_id LEFT JOIN users ch ON ch.id=q.child_user_id
 JOIN organizer_question_entries e ON e.id=q.latest_entry_id"""


def question(c, public_id):
    return one(c, QUESTION + " WHERE q.public_id=?", (public_id,))


def listing(c, owner_id, state, cursor):
    where, args = ["q.latest_entry_id < ?"], [cursor]
    if owner_id is not None:
        where.append("q.owner_account_id=?")
        args.append(owner_id)
    if state != "all":
        where.append(
            "e.author_account_id "
            + ("=" if state == "awaiting_staff" else "<>")
            + " q.owner_account_id"
        )
    return rows(
        c,
        QUESTION
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY q.latest_entry_id DESC LIMIT 51",
        args,
    )


def counts(c, owner_id):
    if owner_id is None:
        return c.execute(
            "SELECT count(*) AS total FROM organizer_questions q JOIN organizer_question_entries e ON e.id=q.latest_entry_id WHERE e.author_account_id=q.owner_account_id"
        ).fetchone()["total"]
    return c.execute(
        "SELECT count(*) AS total FROM organizer_questions q WHERE owner_account_id=? AND EXISTS(SELECT 1 FROM organizer_question_entries e WHERE e.question_id=q.id AND e.id>q.owner_read_entry_id AND e.author_account_id<>q.owner_account_id)",
        (owner_id,),
    ).fetchone()["total"]


def entries(c, question_id, after):
    return rows(
        c,
        """SELECT e.*, a.audience, COALESCE(a.display_name,u.surname || ' ' || u.name,a.username) author_name
 FROM organizer_question_entries e JOIN auth_accounts a ON a.id=e.author_account_id
 LEFT JOIN users u ON u.id=a.linked_user_id WHERE question_id=? AND e.id>? ORDER BY e.id LIMIT 51""",
        (question_id, after),
    )


def photos(c, entry_id):
    return rows(
        c,
        "SELECT * FROM organizer_question_photos WHERE entry_id=? ORDER BY id",
        (entry_id,),
    )


def photo(c, public_id):
    return one(
        c,
        "SELECT p.*, e.question_id, q.public_id question_public_id FROM organizer_question_photos p LEFT JOIN organizer_question_entries e ON e.id=p.entry_id LEFT JOIN organizer_questions q ON q.id=e.question_id WHERE p.public_id=?",
        (public_id,),
    )


def replay(c, account_id, key):
    return one(
        c,
        "SELECT e.*, q.public_id question_public_id FROM organizer_question_entries e JOIN organizer_questions q ON q.id=e.question_id WHERE author_account_id=? AND idempotency_key=?",
        (account_id, key),
    )


def create_question(c, owner_id, child_id, now):
    return c.execute(
        "INSERT INTO organizer_questions(owner_account_id,child_user_id,created_at) VALUES(?,?,?)",
        (owner_id, child_id, now),
    ).lastrowid


def insert_entry(c, question_id, account_id, text, now, key, digest, photo_ids):
    entry_id = c.execute(
        "INSERT INTO organizer_question_entries(question_id,author_account_id,text,created_at,idempotency_key,payload_sha256) VALUES(?,?,?,?,?,?)",
        (question_id, account_id, text, now, key, digest),
    ).lastrowid
    for photo_id in photo_ids:
        c.execute(
            "UPDATE organizer_question_photos SET entry_id=? WHERE id=? AND entry_id IS NULL",
            (entry_id, photo_id),
        )
    c.execute(
        "UPDATE organizer_questions SET latest_entry_id=? WHERE id=?",
        (entry_id, question_id),
    )
    return entry_id


def insert_photo(c, account_id, key, digest, size, width, height, now):
    photo_id = c.execute(
        "INSERT INTO organizer_question_photos(uploader_account_id,object_key,sha256,byte_size,width,height,created_at) VALUES(?,?,?,?,?,?,?)",
        (account_id, key, digest, size, width, height, now),
    ).lastrowid
    return photo(c, f"oqp-{photo_id}")


def mark_read(c, question_id, entry_id, account_id, session_id, now):
    c.execute(
        "UPDATE organizer_questions SET owner_read_entry_id=max(owner_read_entry_id,?) WHERE id=?",
        (entry_id, question_id),
    )

    c.execute(
        """UPDATE notification_events SET read_at=max(occurred_at,?),read_by_session_id=?
      WHERE account_id=? AND category='thread_updated' AND read_at IS NULL
      AND dedupe_key IN (SELECT 'organizer-' || id FROM organizer_question_entries
                        WHERE question_id=? AND id<=? AND author_account_id<>?)""",
        (now, session_id, account_id, question_id, entry_id, account_id),
    )


def targets(c, question):
    admins = rows(
        c,
        "SELECT a.public_id, a.audience FROM auth_accounts a JOIN users u ON u.id=a.linked_user_id WHERE a.audience='staff' AND a.status='active' AND u.type=?",
        (USER_TYPE.ADMIN,),
    )
    return [
        dict(
            public_id=question["owner_public_id"], audience=question["owner_audience"]
        ),
        *admins,
    ]

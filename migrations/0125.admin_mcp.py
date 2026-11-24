"""Staff OAuth grants for the administrative MCP, docs/admin-mcp/README.md."""

from yoyo import step

__depends__ = {"0123.personal_result_lookup"}

steps = [
    step(
        """CREATE TABLE admin_mcp_jobs (
        job TEXT PRIMARY KEY, owner TEXT NOT NULL, portal TEXT NOT NULL, request_key TEXT NOT NULL,
        fingerprint TEXT NOT NULL, args TEXT NOT NULL, state TEXT NOT NULL, created INTEGER NOT NULL,
        deadline INTEGER NOT NULL, result TEXT, UNIQUE(owner,portal,request_key)
    )""",
        "DROP TABLE admin_mcp_jobs",
    ),
    step(
        """CREATE TABLE lesson_hide_events (
        lesson INTEGER NOT NULL REFERENCES group_lessons(id), target TEXT NOT NULL,
        object_id INTEGER NOT NULL, revision INTEGER NOT NULL, stamp TEXT NOT NULL,
        due TEXT NOT NULL, actor INTEGER NOT NULL REFERENCES users(id), state TEXT NOT NULL,
        version INTEGER NOT NULL, PRIMARY KEY(lesson,target)
    )""",
        "DROP TABLE lesson_hide_events",
    ),
    step(
        "CREATE INDEX lesson_hide_events_due ON lesson_hide_events(due) WHERE state='scheduled'",
        "DROP INDEX lesson_hide_events_due",
    ),
    step(
        """CREATE TABLE staff_lesson_creation_receipts (
        account TEXT NOT NULL, request_key TEXT NOT NULL, payload TEXT NOT NULL,
        group_lesson TEXT NOT NULL, course_lesson TEXT NOT NULL, request_id TEXT NOT NULL,
        PRIMARY KEY(account, request_key)
    )""",
        "DROP TABLE staff_lesson_creation_receipts",
    ),
    step(
        """CREATE TABLE admin_mcp_exports (
        public_id TEXT PRIMARY KEY, account TEXT NOT NULL, resource TEXT NOT NULL,
        lesson TEXT NOT NULL, revision TEXT NOT NULL, filename TEXT NOT NULL,
        mime TEXT NOT NULL, content BLOB NOT NULL, expires INTEGER NOT NULL
    )""",
        "DROP TABLE admin_mcp_exports",
    ),
    step(
        """CREATE TABLE admin_mcp_grants (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES auth_accounts(id) ON DELETE CASCADE,
        account TEXT NOT NULL,
        session TEXT NOT NULL REFERENCES auth_sessions(public_id) ON DELETE CASCADE,
        credential_version INTEGER NOT NULL,
        session_version INTEGER NOT NULL,
        resource TEXT NOT NULL,
        client TEXT NOT NULL,
        redirect TEXT NOT NULL,
        challenge TEXT NOT NULL,
        code_hash TEXT UNIQUE,
        code_expires INTEGER NOT NULL,
        access_hash TEXT UNIQUE,
        access_expires INTEGER,
        refresh_hash TEXT UNIQUE,
        refresh_expires INTEGER,
        revoked INTEGER NOT NULL DEFAULT 0
    )""",
        "DROP TABLE admin_mcp_grants",
    ),
]

"""Private MCP proposals, never student feedback; vmshpwa/docs/ai-review-assistant.md."""

from yoyo import step

__depends__ = {"0121.review_sheet_indexes"}

steps = [
    step(
        """CREATE TABLE ai_review_tokens (
        id INTEGER PRIMARY KEY,
        public_id TEXT NOT NULL UNIQUE,
        account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
        credential_version INTEGER NOT NULL,
        name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
        secret_hash TEXT NOT NULL UNIQUE CHECK(length(secret_hash)=64),
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL CHECK(expires_at>created_at),
        revoked_at TEXT
        )""",
        "DROP TABLE ai_review_tokens",
    ),
    step(
        """CREATE TABLE ai_review_suggestions (
        id INTEGER PRIMARY KEY,
        public_id TEXT NOT NULL UNIQUE,
        token_id INTEGER NOT NULL REFERENCES ai_review_tokens(id),
        case_thread_id INTEGER NOT NULL REFERENCES submission_threads(id),
        case_id TEXT NOT NULL CHECK(case_id='st-'||case_thread_id),
        snapshot TEXT NOT NULL CHECK(length(snapshot)=64),
        idempotency_key TEXT NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 128),
        payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64),
        comment TEXT CHECK(comment IS NULL OR length(comment)<=100000),
        verdict INTEGER REFERENCES verdicts(id),
        analysis TEXT CHECK(analysis IS NULL OR length(analysis)<=100000),
        source TEXT NOT NULL CHECK(length(trim(source)) BETWEEN 1 AND 200),
        model TEXT CHECK(model IS NULL OR length(model)<=200),
        created_at TEXT NOT NULL,
        UNIQUE(token_id,idempotency_key),
        CHECK(comment IS NOT NULL OR verdict IS NOT NULL OR analysis IS NOT NULL)
        )""",
        "DROP TABLE ai_review_suggestions",
    ),
    step(
        "CREATE INDEX ai_review_suggestions_case_idx ON ai_review_suggestions(case_id,id DESC)",
        "DROP INDEX ai_review_suggestions_case_idx",
    ),
    step(
        """CREATE TABLE ai_review_events (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
        token_id INTEGER REFERENCES ai_review_tokens(id),
        event TEXT NOT NULL CHECK(event IN ('token_created','token_revoked','suggestion_uploaded')),
        subject_id TEXT NOT NULL,
        created_at TEXT NOT NULL
        )""",
        "DROP TABLE ai_review_events",
    ),
]

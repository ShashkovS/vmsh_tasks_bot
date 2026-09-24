-- depends: 0087.pwa_live_marking 0087.pwa_review_entry_transfers
-- Account-owned private correspondence; vmshpwa/docs/organizer-questions.md.
CREATE TABLE organizer_questions (
 id INTEGER PRIMARY KEY,
 public_id TEXT GENERATED ALWAYS AS ('oq-' || id) VIRTUAL,
 owner_account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
 child_user_id INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL,
 latest_entry_id INTEGER,
 owner_read_entry_id INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX organizer_questions_owner_idx ON organizer_questions(owner_account_id, latest_entry_id DESC);
CREATE TABLE organizer_question_entries (
 id INTEGER PRIMARY KEY,
 public_id TEXT GENERATED ALWAYS AS ('oqe-' || id) VIRTUAL,
 question_id INTEGER NOT NULL REFERENCES organizer_questions(id),
 author_account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
 text TEXT NOT NULL CHECK(length(text)<=100000),
 created_at TEXT NOT NULL,
 idempotency_key TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 UNIQUE(author_account_id, idempotency_key)
);
CREATE INDEX organizer_entries_question_idx ON organizer_question_entries(question_id, id);
CREATE TABLE organizer_question_photos (
 id INTEGER PRIMARY KEY,
 public_id TEXT GENERATED ALWAYS AS ('oqp-' || id) VIRTUAL,
 uploader_account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
 entry_id INTEGER REFERENCES organizer_question_entries(id),
 object_key TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL,
 byte_size INTEGER NOT NULL,
 width INTEGER NOT NULL,
 height INTEGER NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX organizer_photos_entry_idx ON organizer_question_photos(entry_id, id);
CREATE TRIGGER organizer_entry_immutable BEFORE UPDATE ON organizer_question_entries
BEGIN SELECT RAISE(ABORT,'organizer entry is immutable'); END;
CREATE TRIGGER organizer_entry_no_delete BEFORE DELETE ON organizer_question_entries
BEGIN SELECT RAISE(ABORT,'organizer entry deletion is forbidden'); END;

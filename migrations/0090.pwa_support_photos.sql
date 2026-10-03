-- depends: 0089.pwa_communication_targeting
-- Private question attachments; vmshpwa/docs/question-photos.md.
CREATE TABLE support_photos (
 id INTEGER PRIMARY KEY,
 public_id TEXT GENERATED ALWAYS AS ('sup-' || id) VIRTUAL,
 uploader_user_id INTEGER NOT NULL REFERENCES users(id),
 entry_id INTEGER REFERENCES support_entries(id),
 object_key TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL,
 byte_size INTEGER NOT NULL,
 width INTEGER NOT NULL,
 height INTEGER NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX support_photos_entry_idx ON support_photos(entry_id);

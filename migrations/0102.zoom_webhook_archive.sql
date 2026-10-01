-- depends: 0101.pwa_branding
-- docs/deploy/tlf-app/README.md: lossless receipt archive, no queue interpretation.
CREATE TABLE zoom_webhook_receipts (
    id INTEGER PRIMARY KEY,
    received_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    meeting_id TEXT,
    request_id TEXT,
    request_timestamp TEXT NOT NULL,
    raw_body BLOB NOT NULL
);
CREATE INDEX zoom_webhook_receipts_by_meeting ON zoom_webhook_receipts(meeting_id, id);

"""Durable browser-image intents; docs/performance/browser-image-uploads.md."""

from yoyo import step

__depends__ = {"0113.content_upload_compiler_generation"}

steps = [
    step(
        """
        CREATE TABLE pwa_image_uploads (
            id TEXT PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES auth_accounts(id),
            audience TEXT NOT NULL CHECK(audience IN ('student','family','staff')),
            client_id TEXT NOT NULL,
            purpose TEXT NOT NULL CHECK(purpose IN ('written','support','organizer','rich','lesson-block')),
            context TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL CHECK(length(sha256)=64),
            byte_size INTEGER NOT NULL CHECK(byte_size BETWEEN 1 AND 20971520),
            width INTEGER NOT NULL CHECK(width BETWEEN 1 AND 1920),
            height INTEGER NOT NULL CHECK(height BETWEEN 1 AND 1920),
            object_key TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','finalizing','completed','deleting','deleted')),
            expires_at TEXT NOT NULL,
            claim_token TEXT,
            claim_until TEXT,
            response TEXT,
            binding TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(account_id, audience, client_id),
            CHECK((state='completed') = (response IS NOT NULL))
        )
    """,
        "DROP TABLE pwa_image_uploads",
    ),
    step(
        "CREATE INDEX pwa_image_uploads_cleanup ON pwa_image_uploads(state, expires_at)",
        "DROP INDEX pwa_image_uploads_cleanup",
    ),
]

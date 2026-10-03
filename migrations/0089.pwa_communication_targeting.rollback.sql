DROP INDEX group_banner_media_banner_idx;

CREATE TABLE group_banner_media_legacy
(
    id          INTEGER PRIMARY KEY,
    banner_id   INTEGER NOT NULL,
    ordinal     INTEGER NOT NULL CHECK (ordinal >= 0),
    media_id    TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    public_url  TEXT,
    mime_type   TEXT NOT NULL CHECK (mime_type IN ('image/webp', 'image/gif')),
    width       INTEGER NOT NULL CHECK (width > 0 AND width <= 1920),
    height      INTEGER NOT NULL CHECK (height > 0 AND height <= 1920),
    created_at  TEXT NOT NULL,
    UNIQUE (banner_id, ordinal),
    UNIQUE (banner_id, media_id)
);

INSERT INTO group_banner_media_legacy
SELECT id, banner_id, ordinal, media_id, source_url, storage_key, public_url,
       mime_type, width, height, created_at
FROM group_banner_media;

DROP TABLE group_banner_media;
DROP INDEX group_banners_window_idx;

CREATE TABLE group_banners_legacy
(
    id                       INTEGER PRIMARY KEY,
    public_id TEXT GENERATED ALWAYS AS ('bn-' || id) VIRTUAL,
    group_id                 TEXT NOT NULL REFERENCES groups (group_id),
    audience                 TEXT NOT NULL
        CHECK (audience IN ('student', 'family', 'both')),
    html_sanitized           TEXT NOT NULL,
    sanitizer_policy_version INTEGER NOT NULL DEFAULT 1,
    starts_at                TEXT NOT NULL,
    ends_at                  TEXT NOT NULL,
    priority                 INTEGER NOT NULL DEFAULT 0,
    dismissible              INTEGER NOT NULL DEFAULT 1
        CHECK (dismissible IN (0, 1)),
    status                   TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'cancelled')),
    created_by_user_id       INTEGER NOT NULL REFERENCES users (id),
    updated_by_user_id       INTEGER NOT NULL REFERENCES users (id),
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    cancelled_at             TEXT,
    version                  INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    content_format           TEXT NOT NULL DEFAULT 'legacy_html'
        CHECK (content_format IN ('legacy_html', 'rich_markdown_v1')),
    markdown_source          TEXT,
    rich_document_json       TEXT,
    CHECK (length(trim(public_id)) > 0),
    CHECK (length(trim(html_sanitized)) > 0),
    CHECK (sanitizer_policy_version = 1),
    CHECK (ends_at > starts_at),
    CHECK (
        (status = 'active' AND cancelled_at IS NULL)
        OR (status = 'cancelled' AND cancelled_at IS NOT NULL)
    )
);

INSERT INTO group_banners_legacy
    (id, group_id, audience, html_sanitized, sanitizer_policy_version,
     starts_at, ends_at, priority, dismissible, status, created_by_user_id,
     updated_by_user_id, created_at, updated_at, cancelled_at, version,
     content_format, markdown_source, rich_document_json)
SELECT banner.id,
       coalesce(
           banner.group_id,
           (SELECT fallback.group_id FROM groups AS fallback
            WHERE fallback.course_id = banner.course_id
            ORDER BY fallback.sort_order, fallback.group_id LIMIT 1)
       ),
       banner.audience, banner.html_sanitized, banner.sanitizer_policy_version,
       banner.starts_at, banner.ends_at, banner.priority, banner.dismissible,
       banner.status, banner.created_by_user_id, banner.updated_by_user_id,
       banner.created_at, banner.updated_at, banner.cancelled_at, banner.version,
       banner.content_format, banner.markdown_source, banner.rich_document_json
FROM group_banners AS banner;

DROP TABLE group_banners;
ALTER TABLE group_banners_legacy RENAME TO group_banners;

CREATE TABLE group_banner_media
(
    id          INTEGER PRIMARY KEY,
    banner_id   INTEGER NOT NULL REFERENCES group_banners (id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL CHECK (ordinal >= 0),
    media_id    TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    public_url  TEXT,
    mime_type   TEXT NOT NULL CHECK (mime_type IN ('image/webp', 'image/gif')),
    width       INTEGER NOT NULL CHECK (width > 0 AND width <= 1920),
    height      INTEGER NOT NULL CHECK (height > 0 AND height <= 1920),
    created_at  TEXT NOT NULL,
    UNIQUE (banner_id, ordinal),
    UNIQUE (banner_id, media_id)
);

INSERT INTO group_banner_media SELECT * FROM group_banner_media_legacy;
DROP TABLE group_banner_media_legacy;

CREATE INDEX group_banners_window_idx
    ON group_banners (group_id, status, starts_at, ends_at, priority DESC, id);
CREATE INDEX group_banner_media_banner_idx
    ON group_banner_media (banner_id, ordinal);

DROP INDEX news_posts_group_target_feed_idx;
DROP INDEX news_posts_course_target_feed_idx;
ALTER TABLE news_posts DROP COLUMN attendance_mode;
ALTER TABLE news_posts DROP COLUMN audience;

-- depends: 0088.pwa_organizer_questions

-- Audience and attendance targeting for persistent news. Existing Telegram and
-- Staff-authored posts remain visible to both audiences in either format.
ALTER TABLE news_posts ADD COLUMN audience TEXT NOT NULL DEFAULT 'both'
    CHECK (audience IN ('student', 'family', 'both'));
ALTER TABLE news_posts ADD COLUMN attendance_mode TEXT NOT NULL DEFAULT 'all'
    CHECK (attendance_mode IN ('all', 'online', 'in_person'));

CREATE INDEX news_posts_course_target_feed_idx
    ON news_posts
       (owner_course_id, audience, attendance_mode, published_at DESC, id DESC);
CREATE INDEX news_posts_group_target_feed_idx
    ON news_posts
       (owner_group_id, audience, attendance_mode, published_at DESC, id DESC);

-- Group announcements used to require one group. Rebuild the table so one
-- announcement can target either a whole course or one group within it.
CREATE TABLE group_banners_targeted
(
    id                       INTEGER PRIMARY KEY,
    public_id TEXT GENERATED ALWAYS AS ('bn-' || id) VIRTUAL,
    course_id                INTEGER NOT NULL REFERENCES courses (id),
    group_id                 TEXT,
    audience                 TEXT NOT NULL
        CHECK (audience IN ('student', 'family', 'both')),
    attendance_mode          TEXT NOT NULL DEFAULT 'all'
        CHECK (attendance_mode IN ('all', 'online', 'in_person')),
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
    FOREIGN KEY (course_id, group_id) REFERENCES groups (course_id, group_id),
    CHECK (length(trim(public_id)) > 0),
    CHECK (length(trim(html_sanitized)) > 0),
    CHECK (sanitizer_policy_version = 1),
    CHECK (ends_at > starts_at),
    CHECK (
        (status = 'active' AND cancelled_at IS NULL)
        OR (status = 'cancelled' AND cancelled_at IS NOT NULL)
    )
);

INSERT INTO group_banners_targeted
    (id, course_id, group_id, audience, attendance_mode, html_sanitized,
     sanitizer_policy_version, starts_at, ends_at, priority, dismissible,
     status, created_by_user_id, updated_by_user_id, created_at, updated_at,
     cancelled_at, version, content_format, markdown_source, rich_document_json)
SELECT banner.id, owner_group.course_id, banner.group_id, banner.audience, 'all',
       banner.html_sanitized, banner.sanitizer_policy_version, banner.starts_at,
       banner.ends_at, banner.priority, banner.dismissible, banner.status,
       banner.created_by_user_id, banner.updated_by_user_id, banner.created_at,
       banner.updated_at, banner.cancelled_at, banner.version,
       banner.content_format, banner.markdown_source, banner.rich_document_json
FROM group_banners AS banner
JOIN groups AS owner_group ON owner_group.group_id = banner.group_id;

CREATE TABLE group_banner_media_targeted
(
    id          INTEGER PRIMARY KEY,
    banner_id   INTEGER NOT NULL REFERENCES group_banners_targeted (id) ON DELETE CASCADE,
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

INSERT INTO group_banner_media_targeted
    (id, banner_id, ordinal, media_id, source_url, storage_key, public_url,
     mime_type, width, height, created_at)
SELECT id, banner_id, ordinal, media_id, source_url, storage_key, public_url,
       mime_type, width, height, created_at
FROM group_banner_media;

DROP INDEX group_banner_media_banner_idx;
DROP TABLE group_banner_media;
DROP INDEX group_banners_window_idx;
DROP TABLE group_banners;

ALTER TABLE group_banners_targeted RENAME TO group_banners;
ALTER TABLE group_banner_media_targeted RENAME TO group_banner_media;

CREATE INDEX group_banners_window_idx
    ON group_banners
       (course_id, group_id, attendance_mode, status, starts_at, ends_at,
        priority DESC, id);
CREATE INDEX group_banner_media_banner_idx
    ON group_banner_media (banner_id, ordinal);

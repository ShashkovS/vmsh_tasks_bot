-- depends: 0080.pwa_submission_paste_evidence

-- Phase 8 Rich Markdown v1. Legacy projections remain readable while Staff
-- authoring keeps source Markdown and the server-validated authoritative AST.
alter table news_revisions add column content_format text not null default 'legacy'
    check (content_format in ('legacy', 'rich_markdown_v1'));
alter table news_revisions add column markdown_source text;
alter table news_revisions add column rich_document_json text;

alter table news_media add column source_url text;

alter table group_banners add column content_format text not null default 'legacy_html'
    check (content_format in ('legacy_html', 'rich_markdown_v1'));
alter table group_banners add column markdown_source text;
alter table group_banners add column rich_document_json text;

create table group_banner_media
(
    id          integer primary key,
    banner_id   integer not null references group_banners (id) on delete cascade,
    ordinal     integer not null check (ordinal >= 0),
    media_id    text not null,
    source_url  text not null,
    storage_key text not null,
    public_url  text,
    mime_type   text not null check (mime_type in ('image/webp', 'image/gif')),
    width       integer not null check (width > 0 and width <= 1920),
    height      integer not null check (height > 0 and height <= 1920),
    created_at  text not null,
    unique (banner_id, ordinal),
    unique (banner_id, media_id)
);

create index group_banner_media_banner_idx on group_banner_media (banner_id, ordinal);

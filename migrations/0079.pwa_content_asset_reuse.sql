-- depends: 0078.pwa_zero_lesson

-- Global immutable aliases make lesson figures reusable across revisions.
-- TikZ uses a separate versioned canonical-source cache because its logical
-- revision name intentionally remains parser-owned.
create table content_asset_names
(
    id                 integer primary key,
    normalized_name    text    not null unique
        check (length(normalized_name) between 1 and 2000),
    display_name       text    not null
        check (length(trim(display_name)) between 1 and 2000),
    asset_id           integer not null references media_assets (id),
    origin             text    not null
        check (origin in ('upload', 'archive_import', 'backfill')),
    created_by_user_id integer references users (id),
    created_at         text    not null
);

create index content_asset_names_asset_idx
    on content_asset_names (asset_id, normalized_name);

create trigger content_asset_names_immutable_update
before update on content_asset_names
for each row begin
    select raise(abort, 'content asset name is immutable');
end;

create trigger content_asset_names_delete_forbidden
before delete on content_asset_names
for each row begin
    select raise(abort, 'content asset name deletion is forbidden');
end;

create table content_tikz_cache
(
    id                    integer primary key,
    normalized_sha256     text    not null
        check (length(normalized_sha256) = 64 and normalized_sha256 not glob '*[^0-9a-f]*'),
    normalization_version text    not null check (length(trim(normalization_version)) > 0),
    conversion_version    text    not null check (length(trim(conversion_version)) > 0),
    asset_id              integer not null references media_assets (id),
    source_sha256         text    not null
        check (length(source_sha256) = 64 and source_sha256 not glob '*[^0-9a-f]*'),
    created_by_user_id    integer references users (id),
    created_at            text    not null,
    unique (normalized_sha256, normalization_version, conversion_version)
);

create index content_tikz_cache_asset_idx
    on content_tikz_cache (asset_id, normalized_sha256);

create trigger content_tikz_cache_immutable_update
before update on content_tikz_cache
for each row begin
    select raise(abort, 'content TikZ cache is immutable');
end;

create trigger content_tikz_cache_delete_forbidden
before delete on content_tikz_cache
for each row begin
    select raise(abort, 'content TikZ cache deletion is forbidden');
end;

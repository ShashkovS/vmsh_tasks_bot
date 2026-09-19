-- depends: 0079.pwa_content_asset_reuse

alter table submission_entries
    add column paste_count integer not null default 0
        check (paste_count >= 0);

alter table submission_entries
    add column pasted_character_count integer not null default 0
        check (pasted_character_count >= 0);

alter table submission_entries
    add column last_pasted_at text;

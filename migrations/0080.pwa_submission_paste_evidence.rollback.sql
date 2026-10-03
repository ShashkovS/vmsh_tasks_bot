-- depends: 0079.pwa_content_asset_reuse

alter table submission_entries drop column last_pasted_at;
alter table submission_entries drop column pasted_character_count;
alter table submission_entries drop column paste_count;

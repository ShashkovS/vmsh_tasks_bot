-- depends: 0048.pwa_submission_entry_revision

-- Student may remove or reorder pages until review locks the evidence.  A
-- submitted entry must nevertheless remain non-empty even when a caller
-- bypasses the PWA repository.  See Phase 5 in
-- vmshpwa/dev/development-plan/09-phase-5-written-submissions.md.
create trigger submission_attachments_submitted_nonempty_delete
before delete on submission_attachments
for each row
when exists (
    select 1
    from submission_entries as entry
    where entry.id = old.entry_id
      and entry.state = 'submitted'
      and trim(coalesce(entry.text, '')) = ''
      and (
          select count(*)
          from submission_attachments as attachment
          where attachment.entry_id = old.entry_id
      ) <= 1
)
begin
    select raise(abort, 'submitted entry must keep text or an attachment');
end;

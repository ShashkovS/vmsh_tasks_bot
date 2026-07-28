-- depends: 0043.pwa_lesson_window_audit

-- Phase 3 opaque browser identity for legacy-backed problems. Authoritative
-- contract: vmshpwa/dev/development-plan/07-phase-3-student-reading.md.
-- The integer primary key remains the internal Telegram/domain FK. Existing
-- and future legacy inserts receive a separate opaque identifier without
-- requiring the bot or old import scripts to know about the PWA contract.
alter table problems add column public_id text
    check (
        public_id is null
        or (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        )
    );

update problems
set public_id = 'problem-' || lower(hex(randomblob(16)))
where public_id is null;

create unique index problems_public_id_uq
    on problems (public_id)
    where public_id is not null;

create trigger problems_public_id_fill_after_insert
after insert on problems
for each row
when new.public_id is null
begin
    update problems
    set public_id = 'problem-' || lower(hex(randomblob(16)))
    where id = new.id;
end;

create trigger problems_public_id_immutable
before update on problems
for each row
when old.public_id is not null and new.public_id is not old.public_id
begin
    select raise(abort, 'problem public identity is immutable');
end;

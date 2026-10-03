-- depends: 0098.pwa_account_locale
-- Deleted superseded assignment snapshots are intentionally not reconstructed.

drop trigger classroom_assignment_plans_base_insert_valid;
drop trigger classroom_assignment_plans_base_update_valid;
drop trigger classroom_assignments_insert_current_only;
drop trigger classroom_assignments_update_current_only;
drop trigger classroom_assignments_delete_current_only;
drop trigger classroom_assignment_plan_sequence_advance;

create trigger classroom_assignments_insert_working_only
before insert on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = new.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

create trigger classroom_assignments_update_working_only
before update on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

create trigger classroom_assignments_delete_working_only
before delete on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale')
begin
    select raise(abort, 'only a working classroom assignment plan can be edited');
end;

drop table classroom_assignment_plan_sequence;
alter table classroom_assignment_plans drop column base_plan_version;

-- depends: 0098.pwa_account_locale
-- Keep one confirmed assignment plan per event. Historical delivery/import
-- headers remain addressable, while their duplicated assignment rows are removed.

alter table classroom_assignment_plans
    add column base_plan_version integer
        check (base_plan_version is null or base_plan_version > 0);

create table classroom_assignment_plan_sequence
(
    singleton integer primary key check (singleton = 1),
    next_id   integer not null check (next_id > 0)
);

insert into classroom_assignment_plan_sequence (singleton, next_id)
select 1, coalesce(max(id), 0) + 1 from classroom_assignment_plans;

-- Keep the allocator ahead of explicit IDs used by fixtures and maintenance
-- scripts as well as IDs reserved by the application.
create trigger classroom_assignment_plan_sequence_advance
after insert on classroom_assignment_plans
for each row
begin
    update classroom_assignment_plan_sequence
    set next_id = new.id + 1
    where singleton = 1 and next_id <= new.id;
end;

drop trigger classroom_assignments_insert_working_only;
drop trigger classroom_assignments_update_working_only;
drop trigger classroom_assignments_delete_working_only;

-- Superseded plans used to contain a full copy of every assignment. Delivery
-- recipients already hold their own immutable snapshot.
delete from classroom_assignments
where plan_id in (
    select id from classroom_assignment_plans where state = 'superseded'
);

-- Break the historical plan chain before pruning unused headers. A working
-- plan is then based on the one currently confirmed plan and its exact version.
update classroom_assignment_plans
set base_plan_id = null, base_plan_version = null;

update classroom_assignment_plans
set base_plan_id = (
        select confirmed.id
        from classroom_assignment_plans confirmed
        where confirmed.in_person_event_id = classroom_assignment_plans.in_person_event_id
          and confirmed.state = 'confirmed'
    ),
    base_plan_version = (
        select confirmed.version
        from classroom_assignment_plans confirmed
        where confirmed.in_person_event_id = classroom_assignment_plans.in_person_event_id
          and confirmed.state = 'confirmed'
    )
where state in ('draft', 'stale');

delete from classroom_assignment_plans
where state = 'superseded'
  and not exists (
      select 1 from classroom_assignment_delivery_batches batch
      where batch.assignment_plan_id = classroom_assignment_plans.id
  )
  and not exists (
      select 1 from classroom_import_receipts receipt
      where receipt.assignment_plan_id = classroom_assignment_plans.id
  );

create trigger classroom_assignment_plans_base_insert_valid
before insert on classroom_assignment_plans
for each row
when (new.base_plan_id is null) <> (new.base_plan_version is null)
  or (new.state in ('confirmed', 'superseded') and new.base_plan_id is not null)
  or (new.base_plan_id is not null and not exists (
      select 1 from classroom_assignment_plans base
      where base.id = new.base_plan_id
        and base.in_person_event_id = new.in_person_event_id
        and base.state = 'confirmed'
        and (new.state = 'stale' or base.version = new.base_plan_version)
  ))
begin
    select raise(abort, 'invalid classroom assignment base plan');
end;

create trigger classroom_assignment_plans_base_update_valid
before update of base_plan_id, base_plan_version, state, in_person_event_id
on classroom_assignment_plans
for each row
when (new.base_plan_id is null) <> (new.base_plan_version is null)
  or (new.state in ('confirmed', 'superseded') and new.base_plan_id is not null)
  or (new.base_plan_id is not null and not exists (
      select 1 from classroom_assignment_plans base
      where base.id = new.base_plan_id
        and base.in_person_event_id = new.in_person_event_id
        and base.state = 'confirmed'
        and (new.state = 'stale' or base.version = new.base_plan_version)
  ))
begin
    select raise(abort, 'invalid classroom assignment base plan');
end;

create trigger classroom_assignments_insert_current_only
before insert on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = new.plan_id)
    not in ('draft', 'stale', 'confirmed')
begin
    select raise(abort, 'archived classroom assignments cannot be edited');
end;

create trigger classroom_assignments_update_current_only
before update on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale', 'confirmed')
begin
    select raise(abort, 'archived classroom assignments cannot be edited');
end;

create trigger classroom_assignments_delete_current_only
before delete on classroom_assignments
for each row
when (select state from classroom_assignment_plans where id = old.plan_id)
    not in ('draft', 'stale', 'confirmed')
begin
    select raise(abort, 'archived classroom assignments cannot be edited');
end;

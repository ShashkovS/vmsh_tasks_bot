-- depends: 0054.pwa_submission_review_internal_reactions

-- Phase 6F: one current Student reaction per completed review with an
-- append-only change log. The row belongs to the reviewed Student, while the
-- legacy ``reactions`` table remains untouched until its ambiguous history is
-- rehearsed separately.
create table submission_review_student_reactions
(
    review_id       integer primary key references submission_reviews (id),
    actor_user_id   integer not null references users (id),
    reaction_id     integer references reaction_enum (reaction_id),
    created_at      text    not null,
    editable_until  text    not null,
    updated_at      text    not null,
    deleted_at      text,
    version         integer not null check (version > 0),
    check (editable_until >= created_at),
    check (updated_at between created_at and editable_until),
    check (
        (reaction_id is not null and deleted_at is null)
        or (reaction_id is null and deleted_at is not null)
    ),
    check (deleted_at is null or deleted_at = updated_at)
);

create trigger submission_review_student_reactions_scope_insert
before insert on submission_review_student_reactions
for each row
when not exists (
    select 1
    from submission_reviews as review
    join submission_threads as thread on thread.id = review.thread_id
    left join reaction_enum as reaction
      on reaction.reaction_id = new.reaction_id
     and reaction.reaction_type_id = 0
    where review.id = new.review_id
      and thread.student_user_id = new.actor_user_id
      and (new.reaction_id is null or reaction.reaction_id is not null)
)
begin
    select raise(abort, 'student review reaction is outside owner/type scope');
end;

create trigger submission_review_student_reactions_update_guard
before update on submission_review_student_reactions
for each row
when new.review_id is not old.review_id
    or new.actor_user_id is not old.actor_user_id
    or new.created_at is not old.created_at
    or new.editable_until is not old.editable_until
    or new.version <> old.version + 1
    or new.updated_at <= old.updated_at
    or new.updated_at > old.editable_until
    or (
        new.reaction_id is not null
        and not exists (
            select 1 from reaction_enum
            where reaction_id = new.reaction_id and reaction_type_id = 0
        )
    )
begin
    select raise(abort, 'invalid student review reaction update');
end;

create trigger submission_review_student_reactions_delete_forbidden
before delete on submission_review_student_reactions
for each row
begin
    select raise(abort, 'student review reaction deletion is forbidden');
end;

create table submission_review_student_reaction_events
(
    id            integer primary key,
    public_id text generated always as ('rse-' || id) virtual,
    review_id     integer not null references submission_reviews (id),
    actor_user_id integer not null references users (id),
    event_kind    text    not null check (event_kind in ('selected', 'changed', 'deleted')),
    reaction_id   integer references reaction_enum (reaction_id),
    state_version integer not null check (state_version > 0),
    created_at    text    not null,
    unique (review_id, state_version),
    check (
        (event_kind = 'deleted' and reaction_id is null)
        or (event_kind in ('selected', 'changed') and reaction_id is not null)
    )
);

create index submission_review_student_reaction_events_review_idx
    on submission_review_student_reaction_events (review_id, created_at, id);

create trigger submission_review_student_reaction_events_scope_insert
before insert on submission_review_student_reaction_events
for each row
when not exists (
    select 1
    from submission_review_student_reactions as state
    where state.review_id = new.review_id
      and state.actor_user_id = new.actor_user_id
      and state.version = new.state_version
      and (
          (new.event_kind = 'deleted' and state.reaction_id is null)
          or (
              new.event_kind in ('selected', 'changed')
              and state.reaction_id = new.reaction_id
          )
      )
)
begin
    select raise(abort, 'student review reaction event does not match current state');
end;

create trigger submission_review_student_reaction_events_immutable_update
before update on submission_review_student_reaction_events
for each row
begin
    select raise(abort, 'student review reaction event is immutable');
end;

create trigger submission_review_student_reaction_events_delete_forbidden
before delete on submission_review_student_reaction_events
for each row
begin
    select raise(abort, 'student review reaction event deletion is forbidden');
end;

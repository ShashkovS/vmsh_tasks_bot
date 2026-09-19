-- depends: 0044.pwa_problem_identity

-- Student reveals follow the immutable structural match recorded by Staff.
-- Hint/solution revisions intentionally have no duplicate metadata review and
-- therefore no problem_revisions rows. See Phase 3 student material reveals.

drop trigger hint_reveals_publication_kind_insert;

create trigger hint_reveals_publication_kind_insert
before insert on hint_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    join content_problem_matches as problem_match
      on problem_match.content_revision_id = publication.revision_id
     and problem_match.problem_id = new.problem_id
     and problem_match.resolved_at is not null
     and problem_match.decision <> 'omit'
    where publication.id = new.publication_id
      and publication.kind = 'hint'
      and publication.state = 'published'
)
begin
    select raise(abort, 'hint reveal requires a published matched hint');
end;

drop trigger solution_reveals_publication_kind_insert;

create trigger solution_reveals_publication_kind_insert
before insert on solution_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    join content_problem_matches as problem_match
      on problem_match.content_revision_id = publication.revision_id
     and problem_match.problem_id = new.problem_id
     and problem_match.resolved_at is not null
     and problem_match.decision <> 'omit'
    where publication.id = new.publication_id
      and publication.kind = 'solution'
      and publication.state = 'published'
)
begin
    select raise(abort, 'solution reveal requires a published matched solution');
end;

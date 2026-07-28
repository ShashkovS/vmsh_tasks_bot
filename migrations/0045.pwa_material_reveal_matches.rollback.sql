drop trigger solution_reveals_publication_kind_insert;

create trigger solution_reveals_publication_kind_insert
before insert on solution_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    where publication.id = new.publication_id
      and publication.kind = 'solution'
      and publication.state = 'published'
      and exists (
          select 1
          from problem_revisions as problem_revision
          join content_revisions as revision
            on revision.id = problem_revision.content_revision_id
          join content_sources as source on source.id = revision.source_id
          where problem_revision.problem_id = new.problem_id
            and source.group_lesson_id = publication.group_lesson_id
      )
)
begin
    select raise(abort, 'solution reveal requires a published solution');
end;

drop trigger hint_reveals_publication_kind_insert;

create trigger hint_reveals_publication_kind_insert
before insert on hint_reveals
for each row
when not exists (
    select 1
    from lesson_publications as publication
    where publication.id = new.publication_id
      and publication.kind = 'hint'
      and publication.state = 'published'
      and exists (
          select 1
          from problem_revisions as problem_revision
          join content_revisions as revision
            on revision.id = problem_revision.content_revision_id
          join content_sources as source on source.id = revision.source_id
          where problem_revision.problem_id = new.problem_id
            and source.group_lesson_id = publication.group_lesson_id
      )
)
begin
    select raise(abort, 'hint reveal requires a published hint');
end;

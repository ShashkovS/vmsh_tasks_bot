-- depends: 0052.pwa_submission_reviews_evidence

-- Phase 6D: immutable, versioned annotation manifests over exact reviewed
-- evidence attachments. Coordinates are validated by the shared domain layer
-- and stored as normalized 0..1 values in canonical JSON. The original WebP
-- is never modified. See development-plan/10-phase-6-review-and-feedback.md.
create table submission_review_annotations
(
    id             integer primary key,
    public_id      text    not null unique
        check (
            length(public_id) between 1 and 128
            and public_id not glob '*[^a-z0-9._:-]*'
            and substr(public_id, 1, 1) glob '[a-z0-9]'
            and substr(public_id, -1, 1) glob '[a-z0-9]'
        ),
    review_id      integer not null references submission_reviews (id),
    attachment_id  integer not null references submission_attachments (id),
    schema_version integer not null check (schema_version = 1),
    rotation       integer not null check (rotation in (0, 90, 180, 270)),
    marks_json     text    not null
        check (
            json_valid(marks_json) = 1
            and json_type(marks_json) = 'array'
            and json_array_length(marks_json) between 1 and 250
            and length(marks_json) <= 1000000
        ),
    payload_sha256 text    not null
        check (length(payload_sha256) = 64 and payload_sha256 not glob '*[^0-9a-f]*'),
    created_at     text    not null,
    unique (review_id, attachment_id),
    foreign key (review_id, attachment_id)
        references submission_review_evidence_attachments (review_id, attachment_id)
);

create index submission_review_annotations_attachment_idx
    on submission_review_annotations (attachment_id, review_id);

create trigger submission_review_annotations_scope_insert
before insert on submission_review_annotations
for each row
when not exists (
    select 1
    from submission_review_evidence_attachments as evidence
    where evidence.review_id = new.review_id
      and evidence.attachment_id = new.attachment_id
)
begin
    select raise(abort, 'review annotation is outside immutable evidence');
end;

create trigger submission_review_annotations_immutable_update
before update on submission_review_annotations
for each row
begin
    select raise(abort, 'completed review annotation is immutable');
end;

create trigger submission_review_annotations_delete_forbidden
before delete on submission_review_annotations
for each row
begin
    select raise(abort, 'completed review annotation deletion is forbidden');
end;

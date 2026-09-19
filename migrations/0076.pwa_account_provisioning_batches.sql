-- depends: 0075.pwa_staff_audit

-- Owner-confirmed v1 provisioning keeps the submitted Student/Family password
-- for the external mail script. Browser APIs, audit and logs must never return
-- this column; authentication continues to use credential_hash.
alter table auth_accounts add column provisioning_password_plaintext text
    check (
        provisioning_password_plaintext is null
        or length(provisioning_password_plaintext) between 1 and 512
    );

create table family_account_emails
(
    family_account_id integer not null references auth_accounts (id),
    ordinal           integer not null check (ordinal >= 0),
    email             text    not null check (length(trim(email)) between 3 and 320),
    email_normalized  text    not null check (length(trim(email_normalized)) between 3 and 320),
    created_at        text    not null,
    primary key (family_account_id, ordinal),
    unique (family_account_id, email_normalized)
);

create index family_account_emails_normalized_idx
    on family_account_emails (email_normalized);

create trigger family_account_emails_family_only_insert
before insert on family_account_emails
for each row
when not exists (
    select 1 from auth_accounts
    where id = new.family_account_id and audience = 'family'
)
begin
    select raise(abort, 'email owner must be a Family account');
end;

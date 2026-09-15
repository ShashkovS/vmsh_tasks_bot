-- depends: 0068.pwa_group_banners

-- A row exists only when a Student overrides the global push preference for
-- one course/category pair. Quiet hours and in-app visibility stay global.
create table notification_course_preferences
(
    account_id   integer not null references auth_accounts (id),
    course_id    integer not null references courses (id),
    category     text    not null,
    push_enabled integer not null check (push_enabled in (0, 1)),
    updated_at   text    not null,
    primary key (account_id, course_id, category),
    check (length(trim(category)) > 0)
);

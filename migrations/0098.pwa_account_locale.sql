-- depends: 0097.pwa_classroom_assignment_preferences
-- Interface language of a PWA account (adr/0004-pwa-internationalization.md).
-- Russian is the default for every existing and new account.

alter table auth_accounts
    add column locale text not null default 'ru'
        check (locale in ('ru', 'en'));

-- depends: 0100.pwa_lesson_blocks
-- vmshpwa/docs/branding.md: deployment-local identity, not tenant routing.
CREATE TABLE pwa_branding (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    profile_id TEXT NOT NULL,
    default_locale TEXT NOT NULL CHECK (default_locale IN ('ru', 'en')),
    version INTEGER NOT NULL DEFAULT 1
);
INSERT INTO pwa_branding (id, profile_id, default_locale) VALUES (1, 'vmsh', 'ru');
ALTER TABLE auth_accounts ADD COLUMN locale_explicit INTEGER NOT NULL DEFAULT 0
    CHECK (locale_explicit IN (0, 1));
UPDATE auth_accounts SET locale_explicit = 1;

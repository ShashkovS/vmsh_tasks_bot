-- depends: 0102.zoom_webhook_archive
-- vmshpwa/docs/course-attendance-settings.md: preserve enrollment preferences and history.
ALTER TABLE courses ADD COLUMN has_in_person_classes INTEGER NOT NULL DEFAULT 1
    CHECK (has_in_person_classes IN (0, 1));

-- depends: 0103.course_in_person_classes
-- vmshpwa/docs/metadata-generation.md: model applies to the next draft request.
ALTER TABLE courses ADD COLUMN metadata_model TEXT NOT NULL DEFAULT 'openai/gpt-5.6-luna'
    CHECK (length(trim(metadata_model)) BETWEEN 3 AND 200);

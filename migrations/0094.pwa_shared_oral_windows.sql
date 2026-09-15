-- depends: 0093.pwa_figure_layout 0070.pwa_oral_windows
-- One window/version, many lessons: vmshpwa/docs/oral-window-weekly-drafts.md.
CREATE TABLE oral_window_lessons (
 window_id INTEGER NOT NULL REFERENCES oral_windows(id) ON DELETE CASCADE,
 group_lesson_id INTEGER NOT NULL REFERENCES group_lessons(id),
 PRIMARY KEY(window_id, group_lesson_id)
);
CREATE INDEX oral_window_lessons_lesson_idx ON oral_window_lessons(group_lesson_id, window_id);
INSERT INTO oral_window_lessons SELECT id, group_lesson_id FROM oral_windows;
-- Preserve old inserts, including legacy clients and fixture importers.
CREATE TRIGGER oral_window_primary_lesson AFTER INSERT ON oral_windows BEGIN
 INSERT INTO oral_window_lessons VALUES (NEW.id, NEW.group_lesson_id);
END;
CREATE TABLE oral_window_batches (
 actor_user_id INTEGER NOT NULL REFERENCES users(id),
 request_key TEXT NOT NULL,
 fingerprint TEXT NOT NULL,
 window_ids_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(actor_user_id, request_key)
);

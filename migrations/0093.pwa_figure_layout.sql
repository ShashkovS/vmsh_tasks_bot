-- depends: 0092.pwa_statistics_recalculation
-- Draft versus published figure placement: vmshpwa/docs/figure-layout.md.
CREATE TABLE content_figure_layouts (
 revision_id INTEGER PRIMARY KEY REFERENCES content_revisions(id),
 version INTEGER NOT NULL CHECK(version > 0),
 entries_json TEXT NOT NULL,
 updated_by_user_id INTEGER REFERENCES users(id),
 updated_at TEXT NOT NULL
);
CREATE TABLE publication_figure_layouts (
 publication_id INTEGER PRIMARY KEY REFERENCES lesson_publications(id),
 layout_version INTEGER NOT NULL,
 document_json TEXT,
 telegram_html TEXT,
 telegram_sha256 TEXT,
 entries_json TEXT NOT NULL
);
CREATE TRIGGER publication_figure_layouts_immutable_update
BEFORE UPDATE ON publication_figure_layouts BEGIN
 SELECT RAISE(ABORT, 'published figure layout is immutable');
END;
CREATE TRIGGER publication_figure_layouts_immutable_delete
BEFORE DELETE ON publication_figure_layouts BEGIN
 SELECT RAISE(ABORT, 'published figure layout is immutable');
END;
-- Preserve the currently visible derivatives of existing publications before
-- any recompilation. -1 retains their legacy title/scale overlay semantics.
INSERT INTO publication_figure_layouts (publication_id, layout_version, entries_json, document_json)
SELECT publication.id, -1, '[]', (
 SELECT derivative.content_text FROM content_derivatives derivative
 WHERE derivative.revision_id = publication.revision_id
   AND derivative.kind = 'web_ast' AND derivative.invalidated_at IS NULL
 ORDER BY derivative.id DESC LIMIT 1
) FROM lesson_publications publication;

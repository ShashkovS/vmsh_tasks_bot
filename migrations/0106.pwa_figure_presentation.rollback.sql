DROP TRIGGER publication_figure_layouts_immutable_update;
ALTER TABLE publication_figure_layouts DROP COLUMN legacy_scales_json;
CREATE TRIGGER publication_figure_layouts_immutable_update
BEFORE UPDATE ON publication_figure_layouts BEGIN
 SELECT RAISE(ABORT, 'published figure layout is immutable');
END;

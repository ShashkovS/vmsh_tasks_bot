-- depends: 0105.pwa_recheck_receipt_lookup
-- Freeze legacy live scales; vmshpwa/docs/figure-layout.md.
ALTER TABLE publication_figure_layouts ADD COLUMN legacy_scales_json TEXT NOT NULL DEFAULT '{}';
DROP TRIGGER publication_figure_layouts_immutable_update;
UPDATE publication_figure_layouts SET legacy_scales_json = (
 SELECT json_group_object(scale.asset_id, scale.scale)
 FROM content_figure_scales scale JOIN lesson_publications publication
 ON publication.revision_id = scale.revision_id
 WHERE publication.id = publication_figure_layouts.publication_id
) WHERE layout_version = -1;
CREATE TRIGGER publication_figure_layouts_immutable_update
BEFORE UPDATE ON publication_figure_layouts BEGIN
 SELECT RAISE(ABORT, 'published figure layout is immutable');
END;

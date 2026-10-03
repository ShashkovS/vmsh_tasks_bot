-- depends: 0082.pwa_published_metadata_corrections

-- Staff's visual choice is current mutable presentation state, not a new
-- content derivative or an audit trail. One row exists per source revision
-- and logical Web figure ID.
create table content_figure_scales
(
    revision_id integer not null references content_revisions (id),
    asset_id    text not null
        check (length(trim(asset_id)) between 1 and 160),
    scale       real not null check (scale between 0.25 and 2.5),
    updated_at  text not null,
    primary key (revision_id, asset_id)
);

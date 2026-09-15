-- depends: 0078.pwa_zero_lesson

drop trigger content_tikz_cache_delete_forbidden;
drop trigger content_tikz_cache_immutable_update;
drop table content_tikz_cache;

drop trigger content_asset_names_delete_forbidden;
drop trigger content_asset_names_immutable_update;
drop table content_asset_names;

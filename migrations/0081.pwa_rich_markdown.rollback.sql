-- depends: 0081.pwa_rich_markdown

drop index group_banner_media_banner_idx;
drop table group_banner_media;

alter table group_banners drop column rich_document_json;
alter table group_banners drop column markdown_source;
alter table group_banners drop column content_format;

alter table news_media drop column source_url;

alter table news_revisions drop column rich_document_json;
alter table news_revisions drop column markdown_source;
alter table news_revisions drop column content_format;

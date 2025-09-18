create table IF NOT EXISTS z_settings
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

create table IF NOT EXISTS z_ui_messages
(
    id        INTEGER primary key,
    key       text      not null unique,
    value     text      not null,
    change_ts timestamp not null
);

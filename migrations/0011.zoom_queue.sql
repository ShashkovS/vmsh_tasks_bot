CREATE TABLE IF NOT EXISTS zoom_queue
(
    zoom_user_name TEXT NOT NULL PRIMARY KEY UNIQUE,
    enter_ts timestamp NOT NULL,
    status INTEGER NOT NULL
);
create index IF NOT EXISTS zoom_queue_by_ts on zoom_queue
(enter_ts);

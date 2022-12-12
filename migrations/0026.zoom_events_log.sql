CREATE TABLE IF NOT EXISTS zoom_events
(
    id                 INTEGER PRIMARY KEY,
    event_ts           TIMESTAMP NOT NULL,
    event              TEXT      NOT NULL,
    zoom_user_name     TEXT      NULL,
    zoom_user_id       INTEGER   NULL,
    breakout_room_uuid TEXT      NULL,
    user_id            INTEGER   NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

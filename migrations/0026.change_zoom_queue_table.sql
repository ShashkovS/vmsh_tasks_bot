drop table zoom_queue;

CREATE TABLE IF NOT EXISTS zoom_queue
(
    user_id INTEGER PRIMARY KEY UNIQUE NOT NULL,
    zoom_user_name TEXT,
    queue_submission_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status INTEGER NOT NULL
);

create index IF NOT EXISTS zoom_queue_submission_by_ts on zoom_queue
(queue_submission_ts);
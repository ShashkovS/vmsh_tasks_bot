CREATE TABLE IF NOT EXISTS webtokens
(
    user_id         INTEGER PRIMARY KEY UNIQUE,
    webtoken        TEXT    NOT NULL UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

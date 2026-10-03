"""Instance identity storage. See vmshpwa/docs/branding.md and migration 0101."""

import sqlite3


def get_branding(connection: sqlite3.Connection) -> dict:
    row = connection.execute(
        "SELECT profile_id, default_locale, version FROM pwa_branding WHERE id = 1"
    ).fetchone()
    return dict(row)


def update_branding(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    default_locale: str,
    expected_version: int,
) -> bool:
    return (
        connection.execute(
            "UPDATE pwa_branding SET profile_id = ?, default_locale = ?, version = version + 1 "
            "WHERE id = 1 AND version = ?",
            (profile_id, default_locale, expected_version),
        ).rowcount
        == 1
    )

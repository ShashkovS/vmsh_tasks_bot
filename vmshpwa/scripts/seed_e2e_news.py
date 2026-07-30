"""Seed the small Phase-8 news/browser fixture in the isolated E2E database."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import maintenance_database_lock
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = REPOSITORY_ROOT / "db/vmshpwa_e2e.sqlite3"
TIMESTAMP = "2026-07-30T12:00:00Z"
PROJECTS = ("chromium", "webkit", "firefox")
BINDING_PUBLIC_ID = "telegram-binding.phase8.e2e"
POST_PUBLIC_ID = "news.phase8.e2e"
BANNER_PUBLIC_ID = "banner.phase8.e2e"


def _require_e2e_target(runtime_config: PwaMaintenanceConfig) -> Path:
    require_pwa_maintenance_profile(runtime_config)
    if runtime_config.runtime_profile != "pwa-e2e":
        raise RuntimeError("News E2E seed is available only in pwa-e2e")
    if runtime_config.pwa_instance != "e2e":
        raise RuntimeError("News E2E seed requires VMSH_INSTANCE=e2e")
    database_path = Path(runtime_config.db_filename)
    if not database_path.is_absolute():
        database_path = REPOSITORY_ROOT / database_path
    database_path = database_path.absolute()
    if database_path != EXPECTED_DATABASE:
        raise RuntimeError("News E2E seed refuses an unknown SQLite target")
    return database_path


def _seed(connection: sqlite3.Connection) -> int:
    course = connection.execute(
        "SELECT id FROM courses WHERE public_id = 'course-fixture-math-5-7'"
    ).fetchone()
    group = connection.execute(
        "SELECT group_id FROM groups WHERE public_id = 'group-fixture-beginner'"
    ).fetchone()
    actor = connection.execute(
        "SELECT id FROM users WHERE public_id = 'user-admin-fixture'"
    ).fetchone()
    account_ids = {
        str(row["public_id"]): int(row["id"])
        for row in connection.execute(
            "SELECT id, public_id FROM auth_accounts WHERE public_id IN "
            "('account-classroom-e2e-chromium', "
            "'account-classroom-e2e-webkit', "
            "'account-classroom-e2e-firefox', "
            "'account-classroom-family-e2e-chromium', "
            "'account-classroom-family-e2e-webkit', "
            "'account-classroom-family-e2e-firefox')"
        )
    }
    if course is None or group is None or actor is None or len(account_ids) != 6:
        raise RuntimeError("News E2E seed requires baseline and classroom fixtures")

    expected_notifications = {
        f"notification.news.phase8.e2e.{audience}.{project}"
        for audience in ("student", "family")
        for project in PROJECTS
    }
    existing = {
        "binding": connection.execute(
            "SELECT count(*) FROM telegram_bindings WHERE public_id = ?",
            (BINDING_PUBLIC_ID,),
        ).fetchone()[0],
        "post": connection.execute(
            "SELECT count(*) FROM news_posts WHERE public_id = ?", (POST_PUBLIC_ID,)
        ).fetchone()[0],
        "banner": connection.execute(
            "SELECT count(*) FROM group_banners WHERE public_id = ?",
            (BANNER_PUBLIC_ID,),
        ).fetchone()[0],
        "notifications": {
            str(row[0])
            for row in connection.execute(
                "SELECT public_id FROM notification_events "
                "WHERE public_id LIKE 'notification.news.phase8.e2e.%'"
            )
        },
    }
    if any(
        (
            existing["binding"],
            existing["post"],
            existing["banner"],
            existing["notifications"],
        )
    ):
        if (
            existing["binding"] == 1
            and existing["post"] == 1
            and existing["banner"] == 1
            and existing["notifications"] == expected_notifications
        ):
            return 0
        raise RuntimeError("News E2E fixture is only partially present")

    course_id = int(course["id"])
    actor_id = int(actor["id"])
    group_id = str(group["group_id"])
    connection.execute(
        "INSERT INTO telegram_bindings "
        "(public_id, owner_type, owner_course_id, purpose, chat_id, title_cached, "
        "status, verified_at, created_by_user_id, updated_by_user_id, created_at, "
        "updated_at) VALUES (?, 'course', ?, 'news_source', -1001798001, ?, "
        "'verified', ?, ?, ?, ?, ?)",
        (
            BINDING_PUBLIC_ID,
            course_id,
            "Тестовый канал ВМШ",
            TIMESTAMP,
            actor_id,
            actor_id,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
    post_id = int(
        connection.execute(
            "INSERT INTO news_posts "
            "(public_id, source_type, source_binding_public_id, owner_course_id, "
            "source_chat_id, source_message_id, published_at, created_at, updated_at) "
            "VALUES (?, 'telegram', ?, ?, -1001798001, 8001, ?, ?, ?) RETURNING id",
            (
                POST_PUBLIC_ID,
                BINDING_PUBLIC_ID,
                course_id,
                TIMESTAMP,
                TIMESTAMP,
                TIMESTAMP,
            ),
        ).fetchone()["id"]
    )
    content = [
        {"type": "plain", "text": "Разбор "},
        {"type": "plain", "text": "задач", "marks": [{"type": "bold"}]},
        {"type": "plain", "text": " — сегодня в 17:00.\n"},
        {
            "type": "plain",
            "text": "Открыть материалы",
            "marks": [{"type": "link", "href": "/student/tasks"}],
        },
    ]
    content_json = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    source_hash = hashlib.sha256(content_json.encode()).hexdigest()
    connection.execute(
        "INSERT INTO news_revisions "
        "(post_id, revision_number, source_hash, text_plain, content_json, "
        "source_payload_json, created_at) VALUES (?, 1, ?, ?, ?, '{}', ?)",
        (
            post_id,
            source_hash,
            "Разбор задач — сегодня в 17:00.\nОткрыть материалы",
            content_json,
            TIMESTAMP,
        ),
    )
    connection.execute(
        "INSERT INTO news_visibility (post_id, state, updated_at) "
        "VALUES (?, 'visible', ?)",
        (post_id, TIMESTAMP),
    )
    connection.execute(
        "INSERT INTO group_banners "
        "(public_id, group_id, audience, html_sanitized, starts_at, ends_at, "
        "priority, dismissible, created_by_user_id, updated_by_user_id, created_at, "
        "updated_at) VALUES (?, ?, 'both', ?, '2020-01-01T00:00:00Z', "
        "'2030-01-01T00:00:00Z', 20, 1, ?, ?, ?, ?)",
        (
            BANNER_PUBLIC_ID,
            group_id,
            "<b>Разбор сегодня в 17:00</b> · новости уже опубликованы",
            actor_id,
            actor_id,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )

    for audience in ("student", "family"):
        for project in PROJECTS:
            account_id = account_ids[
                f"account-classroom-{'family-' if audience == 'family' else ''}e2e-{project}"
            ]
            connection.execute(
                "INSERT INTO notification_events "
                "(public_id, account_id, category, dedupe_key, route, payload_json, "
                "occurred_at, deliver_after, created_at) VALUES (?, ?, 'news', ?, ?, ?, ?, ?, ?)",
                (
                    f"notification.news.phase8.e2e.{audience}.{project}",
                    account_id,
                    POST_PUBLIC_ID,
                    f"/{audience}/news/{POST_PUBLIC_ID}",
                    json.dumps({"postId": POST_PUBLIC_ID}, separators=(",", ":")),
                    TIMESTAMP,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
    return 11


def seed_e2e_news(runtime_config: PwaMaintenanceConfig) -> int:
    database_path = _require_e2e_target(runtime_config)
    with maintenance_database_lock(database_path):
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            inserted = _seed(connection)
    print(f"Seeded Phase-8 E2E news fixture: inserted={inserted}")
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("seed_e2e_news accepts no arguments")
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("News E2E seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("News E2E seed requires VMSH_RUNTIME_PROFILE=pwa-e2e")
    from helpers.config import config

    seed_e2e_news(config)


if __name__ == "__main__":
    main()

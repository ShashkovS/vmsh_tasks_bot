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
POST_ID = 9601
BINDING_ID = 9601
BANNER_ID = 9601

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
        "SELECT id FROM courses WHERE code = 'math-5-7'"
    ).fetchone()
    group = connection.execute(
        "SELECT group_id FROM groups WHERE course_id = ? AND group_id = 'н'",
        (course["id"],),
    ).fetchone()
    actor = connection.execute(
        "SELECT id FROM users WHERE id = 301"
    ).fetchone()
    credential_hashes = {
        str(row["audience"]): str(row["credential_hash"])
        for row in connection.execute(
            "SELECT audience, credential_hash FROM auth_accounts WHERE username IN "
            "('testovyy-onlayn-14', 'synthetic-family')"
        )
    }
    if (
        course is None
        or group is None
        or actor is None
        or set(credential_hashes)
        != {
            "student",
            "family",
        }
    ):
        raise RuntimeError("News E2E seed requires baseline fixtures")

    expected_account_count = len(PROJECTS) * 2
    expected_notification_count = len(PROJECTS) * 2
    existing = {
        "binding": connection.execute(
            "SELECT count(*) FROM telegram_bindings "
            "WHERE purpose = 'news_source' AND chat_id = -1001798001",
        ).fetchone()[0],
        "post": connection.execute(
            "SELECT count(*) FROM news_posts "
            "WHERE source_chat_id = -1001798001 AND source_message_id = 8001"
        ).fetchone()[0],
        "banner": connection.execute(
            "SELECT count(*) FROM group_banners "
            "WHERE html_sanitized = '<b>Разбор сегодня в 17:00</b> · новости уже опубликованы'",
        ).fetchone()[0],
        "accounts": int(connection.execute(
            "SELECT count(*) FROM auth_accounts "
            "WHERE username LIKE 'news-%-e2e-%'"
        ).fetchone()[0]),
        "notifications": int(connection.execute(
            "SELECT count(*) FROM notification_events "
            "WHERE category = 'news' AND route LIKE '/%/news/news-%'"
        ).fetchone()[0]),
    }
    if any(
        (
            existing["binding"],
            existing["post"],
            existing["banner"],
            existing["accounts"],
            existing["notifications"],
        )
    ):
        if (
            existing["binding"] == 1
            and existing["post"] == 1
            and existing["banner"] == 1
            and existing["accounts"] == expected_account_count
            and existing["notifications"] == expected_notification_count
        ):
            return 0
        raise RuntimeError("News E2E fixture is only partially present")

    course_id = int(course["id"])
    actor_id = int(actor["id"])
    group_id = str(group["group_id"])
    account_ids: dict[str, int] = {}
    for ordinal, project in enumerate(PROJECTS, start=1):
        student_id = int(
            connection.execute(
                "INSERT INTO users "
                "(id, type, group_id, name, surname, online, grade, birthday, "
                "allowed_groups) VALUES (?, 1, ?, 'Новости', ?, 1, 7, '2013-06-01', ?) "
                "RETURNING id",
                (
                    9500 + ordinal,
                    group_id,
                    f"E2E {project}",
                    f";{group_id};",
                ),
            ).fetchone()["id"]
        )
        student_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, display_name, "
                "credential_kind, credential_hash, linked_user_id, status, "
                "credential_version, created_at, updated_at) "
                "VALUES (?, 'student', ?, ?, 1, 'synthetic_e2e_news', ?, "
                "'telegram_token', ?, ?, 'active', 1, ?, ?) RETURNING id",
                (
                    9510 + ordinal,
                    f"news-student-e2e-{project}",
                    f"news-student-e2e-{project}",
                    f"Новости E2E {project}",
                    credential_hashes["student"],
                    student_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        family_account_id = int(
            connection.execute(
                "INSERT INTO auth_accounts "
                "(id, audience, username, username_normalized, "
                "username_algorithm_version, provisioning_source, display_name, "
                "credential_kind, credential_hash, linked_user_id, status, "
                "credential_version, created_at, updated_at) "
                "VALUES (?, 'family', ?, ?, NULL, 'synthetic_e2e_news', ?, "
                "'password', ?, NULL, 'active', 1, ?, ?) RETURNING id",
                (
                    9520 + ordinal,
                    f"news-family-e2e-{project}",
                    f"news-family-e2e-{project}",
                    f"Семья новости E2E {project}",
                    credential_hashes["family"],
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 1, ?, ?)",
            (family_account_id, student_id, TIMESTAMP, TIMESTAMP),
        )
        enrollment_id = int(
            connection.execute(
            "INSERT INTO course_enrollments "
            "(id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'online', 'active', ?, ?) RETURNING id",
                (
                    9530 + ordinal,
                    student_id,
                    course_id,
                    group_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, granted_by, reason, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'e2e_news_seed', ?, ?)",
            (
                enrollment_id,
                course_id,
                group_id,
                TIMESTAMP,
                actor_id,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        account_ids[f"student.{project}"] = student_account_id
        account_ids[f"family.{project}"] = family_account_id

    connection.execute(
        "INSERT INTO telegram_bindings "
        "(id, owner_type, owner_course_id, purpose, chat_id, title_cached, "
        "status, verified_at, created_by_user_id, updated_by_user_id, created_at, "
        "updated_at) VALUES (?, 'course', ?, 'news_source', -1001798001, ?, "
        "'verified', ?, ?, ?, ?, ?)",
        (
            BINDING_ID,
            course_id,
            "Тестовый канал ВМШ",
            TIMESTAMP,
            actor_id,
            actor_id,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
    binding_id = int(connection.execute(
        "SELECT id FROM telegram_bindings "
        "WHERE purpose = 'news_source' AND chat_id = -1001798001"
    ).fetchone()["id"])
    post = connection.execute(
        "INSERT INTO news_posts "
        "(id, source_type, source_binding_id, owner_course_id, "
        "source_chat_id, source_message_id, published_at, created_at, updated_at) "
        "VALUES (?, 'telegram', ?, ?, -1001798001, 8001, ?, ?, ?) "
        "RETURNING id, public_id",
        (
            POST_ID,
            binding_id,
            course_id,
            TIMESTAMP,
            TIMESTAMP,
            TIMESTAMP,
        ),
    ).fetchone()
    post_id = int(post["id"])
    post_public_id = str(post["public_id"])
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
        "(id, group_id, audience, html_sanitized, starts_at, ends_at, "
        "priority, dismissible, created_by_user_id, updated_by_user_id, created_at, "
        "updated_at) VALUES (?, ?, 'both', ?, '2020-01-01T00:00:00Z', "
        "'2030-01-01T00:00:00Z', 20, 1, ?, ?, ?, ?)",
        (
            BANNER_ID,
            group_id,
            "<b>Разбор сегодня в 17:00</b> · новости уже опубликованы",
            actor_id,
            actor_id,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )

    for audience, offset in (("student", 9610), ("family", 9620)):
        for ordinal, project in enumerate(PROJECTS, start=1):
            account_id = account_ids[f"{audience}.{project}"]
            connection.execute(
                "INSERT INTO notification_events "
                "(id, account_id, category, dedupe_key, route, payload_json, "
                "occurred_at, deliver_after, created_at) VALUES (?, ?, 'news', ?, ?, ?, ?, ?, ?)",
                (
                    offset + ordinal,
                    account_id,
                    post_public_id,
                    f"/{audience}/news/{post_public_id}",
                    json.dumps({"postId": post_public_id}, separators=(",", ":")),
                    TIMESTAMP,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
    return 29


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

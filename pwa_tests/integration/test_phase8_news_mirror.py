"""Phase-8 storage and Telegram-export characterization for the news mirror."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from db_methods.pwa.news import get_post, list_media
from db_methods.pwa.telegram_bindings import set_binding_status
from helpers.pwa.telegram_news import iter_export_updates
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.news import ingest_telegram_news
from models.pwa.auth import AuthAudience
from models.pwa.telegram_bindings import create_binding
from pwa_tests.integration.test_classroom_catalog_http_api import _headers
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    NOW,
    _insert_parents,
)
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _migrations,
    _rollback,
)


MIGRATION_ID = "0067.pwa_news_mirror"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _objects(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name LIKE 'news_%' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_news_migration_up_down_up_is_exact(tmp_path):
    database_path = tmp_path / "news.sqlite3"
    migrations = {item.id: item for item in _migrations()}
    assert {item.id for item in migrations[MIGRATION_ID].depends} == {
        "0066.pwa_telegram_bindings"
    }
    _apply(database_path, set(migrations) - {MIGRATION_ID})
    assert _objects(database_path) == set()

    expected = {
        "news_posts",
        "news_posts_telegram_message_uq",
        "news_posts_telegram_album_uq",
        "news_posts_course_feed_idx",
        "news_posts_group_feed_idx",
        "news_revisions",
        "news_revisions_latest_idx",
        "news_media",
        "news_visibility",
        "news_visibility_state_idx",
        "news_ingest_diagnostics",
        "news_ingest_diagnostics_created_idx",
    }
    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)

    _rollback(database_path, {MIGRATION_ID})
    assert _objects(database_path) == set()
    _apply(database_path, {MIGRATION_ID})
    assert _objects(database_path) == expected


def _database(tmp_path: Path) -> sqlite3.Connection:
    database_path = tmp_path / "news-ingest.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _insert_parents(connection)
    binding = create_binding(
        connection,
        public_id="news-binding",
        owner_type="course",
        owner_public_id="course-assignment",
        purpose="news_source",
        chat_id=-100179,
        message_thread_id=None,
        title_cached="Test news",
        actor_user_id=2,
        now=NOW,
    )
    set_binding_status(
        connection,
        public_id=str(binding["public_id"]),
        expected_version=1,
        status="verified",
        verified_at=NOW,
        title_cached=None,
        actor_user_id=2,
        now=NOW,
    )
    return connection


def _update(text: str = "Условия занятия") -> dict[str, object]:
    return {
        "chat_id": -100179,
        "message_id": 17,
        "media_group_id": "album-17",
        "published_at": "2026-04-01T08:00:00Z",
        "edited_at": None,
        "deleted": False,
        "content": [
            {"type": "bold", "text": text},
            {"type": "plain", "text": "\n"},
            {"type": "link", "text": "Сайт", "href": "https://example.test"},
        ],
        "media": [
            {
                "kind": "image",
                "source_message_id": 17,
                "source_file_id": "photo-17",
                "storage_key": "news/test/photo-17.webp",
                "public_url": "https://cdn.example.test/news/test/photo-17.webp",
                "mime_type": "image/webp",
                "width": 1200,
                "height": 900,
                "storage_status": "stored",
            }
        ],
        "source_payload": {"message_id": 17},
    }


def test_ingest_is_idempotent_and_keeps_immutable_revisions(tmp_path):
    with _database(tmp_path) as connection:
        created = ingest_telegram_news(connection, update=_update(), now=NOW)
        duplicate = ingest_telegram_news(connection, update=_update(), now=NOW)
        set_binding_status(
            connection,
            public_id="news-binding",
            expected_version=2,
            status="disabled",
            verified_at=None,
            title_cached=None,
            actor_user_id=2,
            now="2026-04-01T08:04:00Z",
        )
        edited_update = _update("Уточнённые условия занятия")
        edited_update["edited_at"] = "2026-04-01T08:05:00Z"
        updated = ingest_telegram_news(
            connection, update=edited_update, now="2026-04-01T08:05:01Z"
        )

        assert (created["status"], duplicate["status"], updated["status"]) == (
            "created",
            "duplicate",
            "updated",
        )
        assert created["post_id"] == duplicate["post_id"] == updated["post_id"]
        rows = connection.execute(
            "SELECT revision_number, text_plain FROM news_revisions ORDER BY revision_number"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            (1, "Условия занятия\nСайт"),
            (2, "Уточнённые условия занятия\nСайт"),
        ]
        post = get_post(connection, int(created["post_id"]))
        assert post is not None
        assert (post["revision_number"], post["visibility_state"], post["version"]) == (
            2,
            "visible",
            2,
        )
        assert len(list_media(connection, int(post["revision_id"]))) == 1

        deleted_update = {**edited_update, "deleted": True}
        deleted = ingest_telegram_news(
            connection, update=deleted_update, now="2026-04-01T08:06:00Z"
        )
        assert deleted["status"] == "deleted"
        assert get_post(connection, int(created["post_id"]))["visibility_state"] == (
            "source_deleted"
        )


def test_unmapped_source_stops_in_diagnostics(tmp_path):
    with _database(tmp_path) as connection:
        update = {**_update(), "chat_id": -404, "media_group_id": None}
        result = ingest_telegram_news(connection, update=update, now=NOW)
        assert result == {"status": "diagnostic", "code": "news_source_unmapped"}
        assert connection.execute("SELECT count(*) FROM news_posts").fetchone()[0] == 0
        diagnostic = connection.execute(
            "SELECT code, detail FROM news_ingest_diagnostics"
        ).fetchone()
        assert tuple(diagnostic) == ("news_source_unmapped", None)


def test_historical_export_is_fully_partitioned_without_copying_content():
    export_path = (
        REPOSITORY_ROOT / "_external_pipelines/ChatExport_2026-07-25/result.json"
    )
    export = json.loads(export_path.read_text())
    updates = list(iter_export_updates(export, chat_id=-1003913815635))
    covered_messages = sum(
        len(update["source_payload"]["exportMessages"]) for update in updates
    )
    media_count = sum(len(update["media"]) for update in updates)

    assert covered_messages == 196
    assert media_count == 167
    assert any(update["media_group_id"] is not None for update in updates)
    assert any(
        node.get("unsupportedType") == "custom_emoji"
        for update in updates
        for node in update["content"]
    )


@pytest.mark.asyncio
async def test_student_and_family_read_course_and_group_news(classroom_http):
    def seed(connection):
        for public_id, owner_type, owner_id, chat_id in (
            ("feed-course", "course", "classroom-layout-course", -501),
            ("feed-group", "group", "classroom-layout-group", -502),
        ):
            binding = create_binding(
                connection,
                public_id=public_id,
                owner_type=owner_type,
                owner_public_id=owner_id,
                purpose="news_source",
                chat_id=chat_id,
                message_thread_id=None,
                title_cached=public_id,
                actor_user_id=958_001,
                now=NOW,
            )
            set_binding_status(
                connection,
                public_id=str(binding["public_id"]),
                expected_version=1,
                status="verified",
                verified_at=NOW,
                title_cached=None,
                actor_user_id=958_001,
                now=NOW,
            )

        course_update = {
            **_update(),
            "chat_id": -501,
            "message_id": 1,
            "media_group_id": None,
            "published_at": "2026-10-05T10:00:00Z",
            "content": [
                {"type": "plain", "text": "A😀"},
                {
                    "type": "plain",
                    "text": "Б",
                    "marks": [
                        {"type": "bold"},
                        {"type": "link", "href": "https://example.test/live"},
                    ],
                },
            ],
            "media": [],
        }
        group_update = {
            **_update(),
            "chat_id": -502,
            "message_id": 2,
            "media_group_id": None,
            "published_at": "2026-10-05T11:00:00Z",
        }
        return (
            ingest_telegram_news(connection, update=course_update, now=NOW),
            ingest_telegram_news(connection, update=group_update, now=NOW),
        )

    classroom_http.factory.run_write(seed)
    student_cookies = {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: classroom_http.student_cookie
    }
    first = await classroom_http.client.get(
        "/student/api/v1/news?limit=1",
        headers=_headers(),
        cookies=student_cookies,
    )
    assert first.status == 200, await first.text()
    first_payload = await first.json()
    assert len(first_payload["items"]) == 1
    assert first_payload["items"][0]["media"][0]["kind"] == "photo"
    assert first_payload["items"][0]["attribution"] == {"channel": "feed-group"}
    assert first_payload["nextCursor"] is not None

    detail = await classroom_http.client.get(
        f"/student/api/v1/news/{first_payload['items'][0]['postId']}",
        headers=_headers(),
        cookies=student_cookies,
    )
    assert detail.status == 200
    assert (await detail.json())["item"] == first_payload["items"][0]

    second = await classroom_http.client.get(
        f"/student/api/v1/news?limit=1&cursor={first_payload['nextCursor']}",
        headers=_headers(),
        cookies=student_cookies,
    )
    assert second.status == 200
    second_payload = await second.json()
    assert second_payload["nextCursor"] is None
    assert second_payload["items"][0]["blocks"] == [
        {
            "kind": "text",
            "text": "A😀Б",
            "entities": [
                {"type": "bold", "offset": 3, "length": 1},
                {
                    "type": "link",
                    "offset": 3,
                    "length": 1,
                    "href": "https://example.test/live",
                },
            ],
        }
    ]

    family = await classroom_http.client.get(
        "/family/api/v1/news",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: classroom_http.family_cookie
        },
    )
    assert family.status == 200
    assert len((await family.json())["items"]) == 2

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from db_methods.pwa.telegram_bindings import set_binding_status
from helpers.object_storage import LocalObjectStorage
from helpers.pwa.live_news import ingest_live_news
from models.pwa.telegram_bindings import create_binding
from pwa_tests.test_news_media import Converter


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _message(
    *,
    message_id: int = 41,
    text: str | None = "Новая публикация",
    edited: bool = False,
    media_group_id: str | None = None,
    photo: bool = False,
):
    return SimpleNamespace(
        message_id=message_id,
        chat=SimpleNamespace(id=-801),
        date=datetime(2026, 7, 29, 16, tzinfo=UTC),
        edit_date=(datetime(2026, 7, 29, 16, 5, tzinfo=UTC) if edited else None),
        media_group_id=media_group_id,
        text=text,
        caption=None,
        entities=None,
        caption_entities=None,
        photo=(
            [SimpleNamespace(file_id=f"photo-{message_id}", width=1200, height=900)]
            if photo
            else None
        ),
        video=None,
        animation=None,
        audio=None,
        voice=None,
        document=None,
    )


@pytest.mark.asyncio
async def test_live_news_writes_verified_source_and_invalidates(
    classroom_http, tmp_path
):
    def seed(connection):
        binding = create_binding(
            connection,
            public_id="live-news-source",
            owner_type="course",
            owner_public_id="classroom-layout-course",
            purpose="news_source",
            chat_id=-801,
            message_thread_id=None,
            title_cached="Live channel",
            actor_user_id=958_001,
            now="2026-07-29T15:00:00Z",
        )
        set_binding_status(
            connection,
            public_id=str(binding["public_id"]),
            expected_version=1,
            status="verified",
            verified_at="2026-07-29T15:00:00Z",
            title_cached=None,
            actor_user_id=958_001,
            now="2026-07-29T15:00:00Z",
        )

    classroom_http.factory.run_write(seed)
    invalidations: list[str] = []

    async def download(_file_id: str) -> bytes:
        raise AssertionError("text post has no download")

    result = await ingest_live_news(
        [_message()],
        factory=classroom_http.factory,
        storage=LocalObjectStorage(tmp_path / "media"),
        converter=Converter(),
        download=download,
        invalidate=lambda reason: _append(invalidations, reason),
    )
    duplicate = await ingest_live_news(
        [_message()],
        factory=classroom_http.factory,
        storage=LocalObjectStorage(tmp_path / "media"),
        converter=Converter(),
        download=download,
        invalidate=lambda reason: _append(invalidations, reason),
    )
    assert result["status"] == "created"
    assert result["notification_count"] == 2
    assert duplicate["status"] == "duplicate"
    assert invalidations == ["telegram-news-changed"]
    assert (
        classroom_http.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS amount FROM news_posts"
            ).fetchone()["amount"]
        )
        == 1
    )
    assert classroom_http.factory.run_read(
        lambda connection: [
            (item["audience"], item["category"], item["payload_json"])
            for item in connection.execute(
                "SELECT account.audience, event.category, event.payload_json "
                "FROM notification_events event JOIN auth_accounts account "
                "ON account.id = event.account_id ORDER BY account.audience DESC"
            ).fetchall()
        ]
    ) == [
        ("student", "news", result_payload(result)),
        ("family", "news", result_payload(result)),
    ]


async def _append(values: list[str], value: str) -> None:
    values.append(value)


def result_payload(result: dict[str, object]) -> str:
    return f'{{"postId":"{result["public_id"]}","courseId":"classroom-layout-course"}}'


@pytest.mark.asyncio
async def test_partial_edited_album_is_diagnostic_not_replacement(
    classroom_http, tmp_path
):
    invalidations: list[str] = []

    async def download(_file_id: str) -> bytes:
        raise AssertionError("incomplete album stops before download")

    result = await ingest_live_news(
        [_message(edited=True, media_group_id="album-41")],
        factory=classroom_http.factory,
        storage=LocalObjectStorage(tmp_path / "media"),
        converter=Converter(),
        download=download,
        invalidate=lambda reason: _append(invalidations, reason),
    )
    assert result == {"status": "diagnostic", "code": "incomplete_edited_album"}
    assert invalidations == []
    assert (
        classroom_http.factory.run_read(
            lambda connection: connection.execute(
                "SELECT code FROM news_ingest_diagnostics"
            ).fetchone()["code"]
        )
        == "incomplete_edited_album"
    )


@pytest.mark.asyncio
async def test_live_album_edit_keeps_unmodified_media(classroom_http, tmp_path):
    def seed(connection):
        binding = create_binding(
            connection,
            public_id="live-album-source",
            owner_type="course",
            owner_public_id="classroom-layout-course",
            purpose="news_source",
            chat_id=-801,
            message_thread_id=None,
            title_cached="Live channel",
            actor_user_id=958_001,
            now="2026-07-29T15:00:00Z",
        )
        set_binding_status(
            connection,
            public_id=str(binding["public_id"]),
            expected_version=1,
            status="verified",
            verified_at="2026-07-29T15:00:00Z",
            title_cached=None,
            actor_user_id=958_001,
            now="2026-07-29T15:00:00Z",
        )

    classroom_http.factory.run_write(seed)
    storage = LocalObjectStorage(tmp_path / "media")
    invalidations: list[str] = []

    async def download(file_id: str) -> bytes:
        return file_id.encode()

    created = await ingest_live_news(
        [
            _message(media_group_id="album-41", photo=True),
            _message(
                message_id=42,
                text=None,
                media_group_id="album-41",
                photo=True,
            ),
        ],
        factory=classroom_http.factory,
        storage=storage,
        converter=Converter(),
        download=download,
        invalidate=lambda reason: _append(invalidations, reason),
    )
    classroom_http.factory.run_write(
        lambda connection: set_binding_status(
            connection,
            public_id="live-album-source",
            expected_version=2,
            status="disabled",
            verified_at=None,
            title_cached=None,
            actor_user_id=958_001,
            now="2026-07-29T16:04:00Z",
        )
    )
    updated = await ingest_live_news(
        [
            _message(
                text="Исправленная подпись",
                edited=True,
                media_group_id="album-41",
                photo=True,
            )
        ],
        factory=classroom_http.factory,
        storage=storage,
        converter=Converter(),
        download=download,
        invalidate=lambda reason: _append(invalidations, reason),
    )
    assert (created["status"], updated["status"]) == ("created", "updated")

    def revision(connection):
        row = connection.execute(
            "SELECT id, text_plain FROM news_revisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        media = connection.execute(
            "SELECT source_message_id FROM news_media WHERE revision_id = ? "
            "ORDER BY ordinal",
            (row["id"],),
        ).fetchall()
        return row["text_plain"], [item["source_message_id"] for item in media]

    assert classroom_http.factory.run_read(revision) == (
        "Исправленная подпись",
        [41, 42],
    )
    assert invalidations == ["telegram-news-changed", "telegram-news-changed"]

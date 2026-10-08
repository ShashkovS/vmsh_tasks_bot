"""Stored URLs, frozen publications and immutable guards survive migration 0114.

See vmshpwa/docs/public-media-domain-20261008.md; no external storage is used.
"""

import hashlib
import json
import sqlite3
from contextlib import closing

import pytest
import yoyo

from db_methods.pwa import apply_schema_migrations
from db_methods.pwa.migrations import MIGRATIONS_ROOT
from helpers.pwa.content import ContentRole, compile_latex
from helpers.pwa.content.web_document import WebAssetDescriptor
from models.pwa.content import ContentKind, PublicationState
from pwa_tests.integration.test_content_repository import (
    _create_group_lesson,
    _create_source_revision,
    content_fixture as _content_fixture,
)
from pwa_tests.integration.test_publication_lifecycle_migration import _snapshot

content_fixture = _content_fixture

MIGRATION_ID = "0115.vmsh_public_media_domain"
MIGRATION_FILE = next(
    item
    for item in yoyo.read_migrations(str(MIGRATIONS_ROOT))
    if item.id == MIGRATION_ID
)
MIGRATION_FILE.load()
MIGRATION = vars(MIGRATION_FILE.module)

OLD_ORIGIN = "https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud"
NEW_ORIGIN = "https://vmshstor.shashkovs.ru"
KEY = "content/sha256/aa/e6/fixture.svg"
OLD_URL = f"{OLD_ORIGIN}/{KEY}"
NEW_URL = f"{NEW_ORIGIN}/{KEY}"
PATH_URL = f"https://s3.ru1.storage.beget.cloud/d3ca76cf4cf5-images-bucket/{KEY}"
OTHER_URL = f"https://tlfprepimages.nbg1.your-objectstorage.com/{KEY}"
LOOKALIKE_URL = f"{OLD_ORIGIN}.example.invalid/{KEY}"
NOW = "2026-09-20T13:00:00.000000Z"


async def _seed(fixture):
    _, lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="domain-course",
        course_id=fixture.course_id,
        lesson_number=79,
        group_id="content-a",
        group_lesson_public_id="domain-group",
    )
    _, revision = await _create_source_revision(
        fixture,
        group_lesson_id=lesson.id,
        suffix="domain",
        canonical_document={"children": [], "type": "document", "originalUrl": OLD_URL},
    )
    media = await fixture.repository.register_media_asset(
        public_id="domain-media",
        sha256=hashlib.sha256(b"fixture-svg").hexdigest(),
        storage_namespace="content",
        object_key=KEY,
        public_url=OLD_URL,
        media_type="image/svg+xml",
        byte_size=11,
        width=10,
        height=10,
        actor_user_id=fixture.actor_user_id,
    )
    for index, url in enumerate((NEW_URL, OTHER_URL, LOOKALIKE_URL)):
        await fixture.repository.register_media_asset(
            public_id=f"domain-preserved-{index}",
            sha256=hashlib.sha256(f"preserved-{index}".encode()).hexdigest(),
            storage_namespace="content",
            object_key=f"content/preserved-{index}.svg",
            public_url=url,
            media_type="image/svg+xml",
            byte_size=10,
            actor_user_id=fixture.actor_user_id,
        )
    descriptor = WebAssetDescriptor(
        asset_id=media.public_id,
        content_sha256=media.sha256,
        src=OLD_URL,
        media_type="image/svg+xml",
        width=10,
        height=10,
    )
    compiled = compile_latex(
        r"\begin{document}\задача\includegraphics{picture.svg}\кзадача\end{document}".encode(),
        source_name="domain.tex",
        role=ContentRole.CONDITION,
        revision_id=revision.public_id,
        known_assets={"picture.svg": descriptor},
    )
    assert not compiled.has_errors
    for kind, derivative in (
        ("web_ast", compiled.web_document),
        ("web_html", compiled.web),
        ("telegram_html", compiled.telegram),
    ):
        await fixture.repository.add_derivative(
            revision_id=revision.id,
            kind=kind,
            renderer_version="domain-test",
            provenance={"originalUrl": OLD_URL},
            content_text=derivative.content,
        )
    archived = await fixture.repository.add_derivative(
        revision_id=revision.id,
        kind="web_html",
        renderer_version="domain-archived",
        provenance={"originalUrl": OLD_URL},
        content_text=f'<img src="{PATH_URL}">',
    )
    publication = await fixture.repository.create_publication(
        public_id="domain-publication",
        group_lesson_id=lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=revision.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )
    document = json.dumps({"image": OLD_URL, "file": PATH_URL, "other": OTHER_URL})
    escaped_document = document.replace("/", r"\/")
    markdown = f"![рисунок]({OLD_URL})\n[файл]({PATH_URL})"
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "UPDATE content_derivatives SET invalidated_at=? WHERE id=?",
            (NOW, archived.id),
        )
        block_id = connection.execute(
            "INSERT INTO lesson_blocks (group_lesson_id, position, created_at, updated_at) "
            "VALUES (?, 'before', ?, ?) RETURNING id",
            (lesson.id, NOW, NOW),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO lesson_block_revisions (block_id, revision_number, markdown, "
            "document_json, created_at, created_by_user_id) VALUES (?, 1, ?, ?, ?, ?)",
            (block_id, markdown, document, NOW, fixture.actor_user_id),
        )
        post_id = connection.execute(
            "INSERT INTO news_posts (source_type, owner_course_id, published_at, "
            "created_at, updated_at) VALUES ('local', ?, ?, ?, ?) RETURNING id",
            (fixture.course_id, NOW, NOW, NOW),
        ).fetchone()[0]
        news_id = connection.execute(
            "INSERT INTO news_revisions (post_id, revision_number, source_hash, "
            "text_plain, content_json, source_payload_json, created_at, "
            "content_format, markdown_source, rich_document_json) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, 'rich_markdown_v1', ?, ?) RETURNING id",
            (
                post_id,
                "a" * 64,
                OLD_URL,
                escaped_document,
                document,
                NOW,
                markdown,
                document,
            ),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO news_media (revision_id, ordinal, media_kind, storage_key, "
            "public_url, storage_status, created_at, updated_at, source_url) "
            "VALUES (?, 0, 'image', ?, ?, 'stored', ?, ?, ?)",
            (news_id, KEY, PATH_URL, NOW, NOW, OLD_URL),
        )
        banner_id = connection.execute(
            "INSERT INTO group_banners (course_id, audience, html_sanitized, "
            "starts_at, ends_at, created_by_user_id, updated_by_user_id, "
            "created_at, updated_at, content_format, markdown_source, rich_document_json) "
            "VALUES (?, 'both', ?, ?, '2027-01-01T00:00:00Z', ?, ?, ?, ?, "
            "'rich_markdown_v1', ?, ?) RETURNING id",
            (
                fixture.course_id,
                f'<img src="{OLD_URL}">',
                NOW,
                fixture.actor_user_id,
                fixture.actor_user_id,
                NOW,
                NOW,
                markdown,
                document,
            ),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO group_banner_media (banner_id, ordinal, media_id, source_url, "
            "storage_key, public_url, mime_type, width, height, created_at) "
            "VALUES (?, 0, 'probe', ?, ?, ?, 'image/webp', 10, 10, ?)",
            (banner_id, OLD_URL, KEY, OLD_URL, NOW),
        )
        connection.execute(
            "DELETE FROM _yoyo_migration WHERE migration_id=?", (MIGRATION_ID,)
        )
        connection.commit()
    return lesson, publication, media


def _assert_transport_only(connection, before, after):
    assert after[0] == before[0]  # Every table/index/trigger definition is restored.
    for table, old_rows in before[1].items():
        new_rows = after[1][table]
        assert len(new_rows) == len(old_rows)
        columns = [
            row[1] for row in connection.execute(f'PRAGMA table_xinfo("{table}")')
        ]
        changed = set(MIGRATION["TEXT_COLUMNS"].get(table, ()))
        changed.update(
            hash_column
            for (hash_table, _column), hash_column in MIGRATION["HASH_COLUMNS"].items()
            if hash_table == table
        )
        preserved = [
            index for index, column in enumerate(columns) if column not in changed
        ]
        assert [tuple(row[i] for i in preserved) for row in new_rows] == [
            tuple(row[i] for i in preserved) for row in old_rows
        ], table


@pytest.mark.parametrize("legacy_fk_defect", [False, True])
async def test_migration_updates_all_projections_and_preserves_history(
    content_fixture, legacy_fk_defect
):
    fixture = content_fixture
    lesson, publication, media = await _seed(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        if legacy_fk_defect:
            connection.execute(
                "CREATE TABLE legacy_domain_probe (id INTEGER REFERENCES users(id))"
            )
            connection.execute("INSERT INTO legacy_domain_probe VALUES (999999999)")
            connection.commit()
        before = _snapshot(connection)
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    assert apply_schema_migrations(fixture.database_path).is_current
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        after = _snapshot(connection)
        _assert_transport_only(connection, before, after)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == foreign_keys
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        for table, columns in MIGRATION["TEXT_COLUMNS"].items():
            for column in columns:
                for (text,) in connection.execute(f'SELECT "{column}" FROM "{table}"'):
                    if text is not None:
                        assert OLD_URL not in text and PATH_URL not in text
                        assert OLD_URL.replace("/", r"\/") not in text
        assert connection.execute(
            "SELECT public_url FROM media_assets WHERE id=?", (media.id,)
        ).fetchone() == (NEW_URL,)
        preserved_urls = connection.execute(
            "SELECT public_url FROM media_assets WHERE id<>? ORDER BY id", (media.id,)
        ).fetchall()
        assert preserved_urls == [(NEW_URL,), (OTHER_URL,), (LOOKALIKE_URL,)]
        for text, digest in connection.execute(
            "SELECT content_text, sha256 FROM content_derivatives"
        ):
            assert hashlib.sha256(text.encode()).hexdigest() == digest
        html, digest = connection.execute(
            "SELECT telegram_html, telegram_sha256 FROM publication_figure_layouts"
        ).fetchone()
        assert NEW_URL in html
        assert hashlib.sha256(html.encode()).hexdigest() == digest
        news_document = json.loads(
            connection.execute("SELECT content_json FROM news_revisions").fetchone()[0]
        )
        assert news_document == {"image": NEW_URL, "file": NEW_URL, "other": OTHER_URL}
        # Direct rerun and downgrade keep both pre-existing and migrated new URLs.
        MIGRATION["apply"](connection)
        MIGRATION["rollback"](connection)
        assert _snapshot(connection) == after
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE content_derivatives SET content_text='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE lesson_block_revisions SET markdown='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE publication_figure_layouts SET document_json='{}'")
    assert apply_schema_migrations(fixture.database_path).is_current
    published = await fixture.repository.get_published_content(
        group_lesson_public_id=lesson.public_id,
        kind=ContentKind.CONDITION,
    )
    assert published.publication == publication
    assert published.document["problems"][0]["blocks"][0]["asset"]["src"] == NEW_URL
    # Reusing an existing figure now resolves to the migrated URL too.
    assert (
        await fixture.repository.get_media_asset(media.public_id)
    ).public_url == NEW_URL


@pytest.mark.parametrize("failure", ["update", "restore_trigger"])
async def test_migration_failure_restores_all_data_and_guards(content_fixture, failure):
    fixture = content_fixture
    await _seed(fixture)
    with closing(sqlite3.connect(fixture.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        before = _snapshot(connection)

        def authorizer(action, name, _column, _database, _trigger):
            denied = (
                action == sqlite3.SQLITE_UPDATE and name == "publication_figure_layouts"
                if failure == "update"
                else action == sqlite3.SQLITE_CREATE_TRIGGER
            )
            return sqlite3.SQLITE_DENY if denied else sqlite3.SQLITE_OK

        connection.set_authorizer(authorizer)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                MIGRATION["apply"](connection)
        finally:
            connection.set_authorizer(None)
        assert not connection.in_transaction
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert _snapshot(connection) == before

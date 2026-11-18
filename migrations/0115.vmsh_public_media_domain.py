"""Move stored VMSH public media URLs without changing objects or source history.

Decision and deployment: vmshpwa/docs/public-media-domain-20261008.md.
Both origins remain readable; a downgrade deliberately retains the new URLs.
"""

import hashlib

from yoyo import step

__depends__ = {"0114.browser_image_uploads"}
# Own one atomic data/trigger transaction, as in migrations 0112 and 0113.
__transactional__ = False

NEW_ORIGIN = "https://vmshstor.shashkovs.ru"
OLD_ORIGINS = (
    "https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud",
    "https://s3.ru1.storage.beget.cloud/d3ca76cf4cf5-images-bucket",
)

# Only persisted presentation fields. Raw LaTeX/Telegram source, provenance,
# audit and idempotency receipts retain the originally observed URLs/hashes.
TEXT_COLUMNS = {
    "media_assets": ("public_url",),
    "content_derivatives": ("content_text",),
    "publication_figure_layouts": ("document_json", "telegram_html"),
    "lesson_block_revisions": ("markdown", "document_json"),
    "news_media": ("public_url",),
    "news_revisions": ("content_json", "markdown_source", "rich_document_json"),
    "group_banner_media": ("public_url",),
    "group_banners": ("html_sanitized", "markdown_source", "rich_document_json"),
}
HASH_COLUMNS = {
    ("content_derivatives", "content_text"): "sha256",
    ("publication_figure_layouts", "telegram_html"): "telegram_sha256",
}
IMMUTABILITY_TRIGGERS = (
    "content_derivatives_payload_immutable",
    "content_derivatives_invalidation_once",
    "publication_figure_layouts_immutable_update",
    "lesson_block_revisions_immutable",
    "media_assets_locked_submission_immutable",
    "media_assets_review_evidence_immutable",
)


def _identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _rewrite(text):
    for origin in OLD_ORIGINS:
        # Include the path separator: similarly named hosts/buckets must not
        # match. Preserve JSON's optional escaped slashes and all other bytes.
        text = text.replace(origin + "/", NEW_ORIGIN + "/")
        text = text.replace(
            (origin + "/").replace("/", r"\/"),
            (NEW_ORIGIN + "/").replace("/", r"\/"),
        )
    return text


def apply(connection):
    if connection.in_transaction:
        raise RuntimeError("Public media migration requires its own transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        foreign_key_errors = sorted(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        triggers = []
        for name in IMMUTABILITY_TRIGGERS:
            row = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type='trigger' AND name=?",
                (name,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Missing public media immutability guard")
            triggers.append((name, row[0]))
        for name, _sql in triggers:
            connection.execute(f"DROP TRIGGER {_identifier(name)}")

        for table, columns in TEXT_COLUMNS.items():
            key = "publication_id" if table == "publication_figure_layouts" else "id"
            names = ", ".join(map(_identifier, (key, *columns)))
            # Stream the scan; never load a whole publication corpus into RAM.
            rows = connection.execute(f"SELECT {names} FROM {_identifier(table)}")
            for row in rows:
                updates = {}
                for column, old_text in zip(columns, row[1:], strict=True):
                    if old_text is None:
                        continue
                    new_text = _rewrite(old_text)
                    if new_text == old_text:
                        continue
                    updates[column] = new_text
                    hash_column = HASH_COLUMNS.get((table, column))
                    if hash_column:
                        updates[hash_column] = hashlib.sha256(
                            new_text.encode("utf-8")
                        ).hexdigest()
                if updates:
                    assignments = ", ".join(
                        f"{_identifier(column)}=?" for column in updates
                    )
                    connection.execute(
                        f"UPDATE {_identifier(table)} SET {assignments} "
                        f"WHERE {_identifier(key)}=?",
                        (*updates.values(), row[0]),
                    )

        for _name, sql in triggers:
            connection.execute(sql)
        if (
            sorted(connection.execute("PRAGMA foreign_key_check").fetchall())
            != foreign_key_errors
        ):
            raise RuntimeError("Public media migration changed foreign key violations")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def rollback(connection):
    # Reversing every new-origin URL would also modify URLs created before or
    # after this migration. Keep compatible URLs and preserve published history;
    # use the maintenance backup when an exact data restoration is required.
    pass


steps = [step(apply, rollback)]

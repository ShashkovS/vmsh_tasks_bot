"""Focused intent/claim queries; docs/performance/browser-image-uploads.md."""

import json


class ImageUploadConflict(ValueError):
    """An immutable identity or an exclusive claim conflicts."""


def get(connection, upload_id):
    row = connection.execute(
        "SELECT * FROM pwa_image_uploads WHERE id=?", (upload_id,)
    ).fetchone()
    return None if row is None else dict(row)


def prepare(connection, record):
    old = connection.execute(
        "SELECT * FROM pwa_image_uploads WHERE account_id=? AND audience=? AND client_id=?",
        (record["account_id"], record["audience"], record["client_id"]),
    ).fetchone()
    if old is not None:
        if old["fingerprint"] != record["fingerprint"]:
            raise ImageUploadConflict("payload")
        if old["state"] != "deleted":
            return dict(old)
        connection.execute(
            "DELETE FROM pwa_image_uploads WHERE id=? AND state='deleted'", (old["id"],)
        )
    columns = tuple(record)
    connection.execute(
        f"INSERT INTO pwa_image_uploads ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        tuple(record.values()),
    )
    return get(connection, record["id"])


def renew(connection, upload_id, expires_at):
    changed = connection.execute(
        "UPDATE pwa_image_uploads SET expires_at=max(expires_at,?) WHERE id=? AND state='pending'",
        (expires_at, upload_id),
    ).rowcount
    if not changed:
        raise ImageUploadConflict("state")
    return get(connection, upload_id)


def claim(connection, upload_id, token, until, now):
    connection.execute(
        "UPDATE pwa_image_uploads SET state='pending',claim_token=NULL,claim_until=NULL "
        "WHERE id=? AND state='finalizing' AND claim_until<?",
        (upload_id, now),
    )
    changed = connection.execute(
        "UPDATE pwa_image_uploads SET state='finalizing',claim_token=?,claim_until=? "
        "WHERE id=? AND state='pending'",
        (token, until, upload_id),
    ).rowcount
    record = get(connection, upload_id)
    if not changed and (record is None or record["state"] != "completed"):
        raise ImageUploadConflict("state")
    return record


def complete(connection, upload_id, token, result, binding):
    changed = connection.execute(
        "UPDATE pwa_image_uploads SET state='completed',response=?,binding=?,claim_token=NULL,claim_until=NULL "
        "WHERE id=? AND state='finalizing' AND claim_token=?",
        (
            json.dumps(result, ensure_ascii=False, sort_keys=True),
            binding,
            upload_id,
            token,
        ),
    ).rowcount
    if not changed:
        raise ImageUploadConflict("claim")


def release(connection, upload_id, token):
    connection.execute(
        "UPDATE pwa_image_uploads SET state='pending',claim_token=NULL,claim_until=NULL "
        "WHERE id=? AND state='finalizing' AND claim_token=?",
        (upload_id, token),
    )


def claim_cleanup(connection, cutoff, now, token, until):
    # Finalizing work has a bounded lease; complete() cannot commit a stolen claim.
    connection.execute(
        "UPDATE pwa_image_uploads SET state='pending',claim_token=NULL,claim_until=NULL "
        "WHERE state='finalizing' AND claim_until<?",
        (now,),
    )
    row = connection.execute(
        "SELECT id FROM pwa_image_uploads WHERE expires_at<=? AND "
        "(state='pending' OR (state='deleting' AND claim_until<?)) ORDER BY expires_at LIMIT 1",
        (cutoff, now),
    ).fetchone()
    if row is None:
        return None
    connection.execute(
        "UPDATE pwa_image_uploads SET state='deleting',claim_token=?,claim_until=? WHERE id=?",
        (token, until, row["id"]),
    )
    return get(connection, row["id"])


def deleted(connection, upload_id, token):
    connection.execute(
        "UPDATE pwa_image_uploads SET state='deleted',claim_token=NULL,claim_until=NULL "
        "WHERE id=? AND state='deleting' AND claim_token=?",
        (upload_id, token),
    )


def known_rich_images(connection, source_urls):
    if not source_urls:
        return {}
    placeholders = ",".join("?" for _ in source_urls)
    rows = connection.execute(
        "SELECT object_key,byte_size,response FROM pwa_image_uploads "
        "WHERE state='completed' AND purpose IN ('rich','lesson-block') "
        f"AND json_extract(response,'$.image.url') IN ({placeholders})",
        tuple(source_urls),
    ).fetchall()
    result = {}
    for row in rows:
        image = json.loads(row["response"])["image"]
        result[image["url"]] = {
            **image,
            "objectKey": row["object_key"],
            "byteSize": row["byte_size"],
        }
    return result

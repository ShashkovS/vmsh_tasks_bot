"""HEAD-only atomic image uploads; docs/performance/browser-image-uploads.md."""

import asyncio
import base64
import hashlib
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from db_methods.pwa import image_uploads as db
from helpers.pwa.image_uploads import (
    ImageUploadService,
    ImageUploadRejected,
    prepared_webp,
)
from pwa_tests.integration import test_content_http_api as support

content_http = support.content_http
PHOTO = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()


class DirectStorage(support.MemoryAssetStorage):
    supports_signed_uploads = True

    def __init__(self):
        super().__init__()
        self.heads, self.signs, self.deletes = [], [], []
        self.override = None

    async def signed_write_url(self, key, **metadata):
        self.signs.append((key, metadata))
        return "https://s3.example.test/upload?signature=redacted"

    async def head(self, key):
        self.heads.append(key)
        if key not in self.objects:
            raise FileNotFoundError()
        return self.override or dict(
            byteSize=len(self.objects[key]),
            mimeType="image/webp",
            checksumSHA256=base64.b64encode(
                hashlib.sha256(self.objects[key]).digest()
            ).decode(),
        )

    async def get(self, key):
        raise AssertionError("Direct finalize must never GET the object")

    async def delete(self, key):
        self.deletes.append(key)
        self.objects.pop(key, None)

    def public_url(self, key):
        return f"https://s3.example.test/{key}"


def description(**extra):
    image = prepared_webp(PHOTO)
    return dict(
        schemaVersion=1,
        clientId=str(uuid.uuid4()),
        purpose="support",
        context={},
        filename="page.webp",
        sha256=image.output_sha256,
        byteSize=len(PHOTO),
        width=image.width,
        height=image.height,
        **extra,
    )


async def request(f, role, path, **kwargs):
    audience = "staff" if role in ("admin", "teacher") else role
    return await f.client.post(
        f"/{audience}/api/v1{path}",
        cookies=support._cookie(f, role),
        headers=support._headers(unsafe=True),
        **kwargs,
    )


def record(f, upload_id):
    return f.factory.run_read(lambda c: db.get(c, upload_id))


@pytest.mark.parametrize("upload_id", [None, {}, 1, "not-an-id"])
async def test_upload_id_is_validated_before_sqlite(content_http, upload_id):
    uploader = ImageUploadService(content_http.factory, content_http.asset_storage)
    with pytest.raises(ImageUploadRejected) as rejected:
        await uploader.owned(upload_id, 1, "student")
    assert rejected.value.status == 422


async def test_direct_support_head_only_replay_and_owner(content_http):
    f = content_http
    storage = DirectStorage()
    f.client.server.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    data = description()
    response = await request(f, "student", "/image-uploads/prepare", json=data)
    assert response.status == 200, await response.text()
    grant = await response.json()
    assert grant["transport"] == "s3"
    assert "Content-Length" not in grant["headers"]
    again = await request(f, "student", "/image-uploads/prepare", json=data)
    assert (await again.json())["uploadId"] == grant["uploadId"]
    changed = await request(
        f,
        "student",
        "/image-uploads/prepare",
        json={**data, "filename": "another.webp"},
    )
    assert changed.status == 409
    reference = {"schemaVersion": 1, "uploadId": grant["uploadId"]}
    missing = await request(f, "student", "/questions/photos", json=reference)
    assert missing.status == 409
    assert (await missing.json())["error"]["code"] == "image_upload_not_uploaded"
    storage.objects[record(f, grant["uploadId"])["object_key"]] = PHOTO
    wrong_owner = await request(f, "admin", "/questions/photos", json=reference)
    assert wrong_owner.status == 404
    result = await request(f, "student", "/questions/photos", json=reference)
    assert result.status == 200, await result.text()
    saved = await result.json()
    replay = await request(f, "student", "/questions/photos", json=reference)
    assert await replay.json() == saved
    assert len(storage.heads) == 2  # missing object plus the successful finalize
    assert storage.puts == []
    assert record(f, grant["uploadId"])["state"] == "completed"
    assert (
        f.factory.run_read(
            lambda c: c.execute("SELECT count(*) n FROM support_photos").fetchone()["n"]
        )
        == 1
    )


@pytest.mark.parametrize(
    "field,value",
    [("byteSize", 1), ("mimeType", "image/png"), ("checksumSHA256", "bad")],
)
async def test_direct_integrity_failure_never_publishes(content_http, field, value):
    f, storage = content_http, DirectStorage()
    f.client.server.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    grant = await (
        await request(f, "student", "/image-uploads/prepare", json=description())
    ).json()
    key = record(f, grant["uploadId"])["object_key"]
    storage.objects[key] = PHOTO
    storage.override = {**await storage.head(key), field: value}
    result = await request(
        f,
        "student",
        "/questions/photos",
        json={"schemaVersion": 1, "uploadId": grant["uploadId"]},
    )
    assert result.status == 422
    assert record(f, grant["uploadId"])["state"] == "pending"
    assert (
        f.factory.run_read(
            lambda c: c.execute("SELECT count(*) n FROM support_photos").fetchone()["n"]
        )
        == 0
    )


async def test_atomic_callback_rollback_and_cleanup_claim(content_http):
    f, storage = content_http, DirectStorage()
    account = f.factory.run_read(
        lambda c: c.execute(
            "SELECT id FROM auth_accounts WHERE public_id='a-1'"
        ).fetchone()["id"]
    )
    clock = [support.NOW]
    uploader = ImageUploadService(f.factory, storage, clock=lambda: clock[0])
    grant = await uploader.prepare(account, "student", description())
    key = record(f, grant["uploadId"])["object_key"]
    storage.objects[key] = PHOTO

    async def broken(item, on_saved):
        def write(c):
            on_saved(c, {"photoId": "will-rollback"})
            raise RuntimeError("transaction rollback")

        return await f.factory.run_write_async(write)

    args = dict(
        upload_id=grant["uploadId"],
        account_id=account,
        audience="student",
        purpose="support",
        context={},
        binding={"path": "/questions/photos"},
    )
    with pytest.raises(RuntimeError, match="rollback"):
        await uploader.finalize(**args, persist=broken)
    assert record(f, grant["uploadId"])["state"] == "pending"
    clock[0] += timedelta(hours=24, minutes=11)
    entered, proceed = asyncio.Event(), asyncio.Event()
    original_delete = storage.delete

    async def slow_delete(key):
        entered.set()
        await proceed.wait()
        await original_delete(key)

    storage.delete = slow_delete
    cleanup = asyncio.create_task(uploader.cleanup())
    await entered.wait()
    with pytest.raises(ImageUploadRejected, match="expired"):
        await uploader.grant(record(f, grant["uploadId"]))
    with pytest.raises(ImageUploadRejected, match="expired"):
        await uploader.finalize(**args, persist=broken)
    proceed.set()
    await cleanup
    assert record(f, grant["uploadId"])["state"] == "deleted"
    assert key not in storage.objects


async def test_completed_intents_survive_cleanup_and_renew(content_http):
    f, storage = content_http, DirectStorage()
    f.client.server.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    grant = await (
        await request(f, "student", "/image-uploads/prepare", json=description())
    ).json()
    key = record(f, grant["uploadId"])["object_key"]
    storage.objects[key] = PHOTO
    result = await request(
        f,
        "student",
        "/questions/photos",
        json={"schemaVersion": 1, "uploadId": grant["uploadId"]},
    )
    assert result.status == 200
    uploader = ImageUploadService(
        f.factory, storage, clock=lambda: support.NOW + timedelta(days=500)
    )
    await uploader.cleanup()
    assert storage.deletes == []
    renewed = await request(
        f, "student", f"/image-uploads/{grant['uploadId']}/renew", json={}
    )
    assert (await renewed.json())["transport"] == "completed"


async def test_proxy_prepared_image_stores_exact_bytes_without_converter(content_http):
    f = content_http
    grant = await (
        await request(f, "student", "/image-uploads/prepare", json=description())
    ).json()
    assert grant["transport"] == "proxy"
    response = await f.client.post(
        "/student/api/v1/questions/photos",
        data=PHOTO,
        cookies=support._cookie(f, "student"),
        headers={
            **support._headers(unsafe=True),
            "Content-Type": "image/webp",
            "X-Vmsh-Image-Upload": grant["uploadId"],
        },
    )
    assert response.status == 200, await response.text()
    assert f.asset_storage.objects[record(f, grant["uploadId"])["object_key"]] == PHOTO


@pytest.mark.parametrize(
    "role,purpose,context,status",
    [
        ("family", "support", {}, 403),
        ("teacher", "rich", {}, 403),
        ("teacher", "organizer", {}, 403),
        ("student", "rich", {}, 403),
        ("student", "support", {"threadId": "foreign"}, 422),
        ("student", "written", {"problemId": []}, 422),
    ],
)
async def test_prepare_authorization_and_context(
    content_http, role, purpose, context, status
):
    response = await request(
        content_http,
        role,
        "/image-uploads/prepare",
        json={**description(), "purpose": purpose, "context": context},
    )
    assert response.status == status, await response.text()


def test_prepared_container_rejects_exif_and_bad_length():
    with pytest.raises(ImageUploadRejected):
        prepared_webp(PHOTO + b"EXIF")
    data = bytearray(PHOTO)
    data[4:8] = (len(PHOTO) - 9).to_bytes(4, "little")
    with pytest.raises(ImageUploadRejected):
        prepared_webp(bytes(data))


@pytest.mark.parametrize(
    "role,purpose,path",
    [
        ("student", "organizer", "/organizer-questions/photos"),
        ("family", "organizer", "/organizer-questions/photos"),
        ("admin", "organizer", "/organizer-questions/photos"),
        ("teacher", "support", "/questions/photos"),
        ("admin", "rich", "/rich-media/uploads"),
        ("admin", "lesson-block", "/group-lessons/gl-1/blocks/media/uploads"),
    ],
)
async def test_direct_existing_photo_endpoints_replay(
    content_http, role, purpose, path
):
    f, storage = content_http, DirectStorage()
    f.client.server.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    context = {"groupLessonId": f.group_lesson_a} if purpose == "lesson-block" else {}
    response = await request(
        f,
        role,
        "/image-uploads/prepare",
        json={**description(), "purpose": purpose, "context": context},
    )
    assert response.status == 200, await response.text()
    grant = await response.json()
    key = record(f, grant["uploadId"])["object_key"]
    storage.objects[key] = PHOTO
    reference = {"schemaVersion": 1, "uploadId": grant["uploadId"]}
    result = await request(f, role, path, json=reference)
    assert result.status in (200, 201), await result.text()
    replay = await request(f, role, path, json=reference)
    assert await replay.json() == await result.json()
    assert storage.puts == []
    assert len(storage.heads) == 1


async def test_direct_written_attachment_versions_and_replay(content_http):
    f, storage = content_http, DirectStorage()
    problem, revision = await support._prepare_published_test_problem(f, problem_type=2)
    f.client.server.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    grant_response = await request(
        f,
        "student",
        "/image-uploads/prepare",
        json={**description(), "purpose": "written", "context": {"problemId": problem}},
    )
    assert grant_response.status == 200, await grant_response.text()
    grant = await grant_response.json()
    created = await request(
        f,
        "student",
        f"/problems/{problem}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": str(uuid.uuid4()),
            "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
            "text": None,
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "clientCreatedAt": support._timestamp(),
        },
    )
    assert created.status == 201, await created.text()
    draft = await created.json()
    key = record(f, grant["uploadId"])["object_key"]
    storage.objects[key] = PHOTO
    reference = {
        "schemaVersion": 1,
        "uploadId": grant["uploadId"],
        "idempotencyKey": str(uuid.uuid4()),
        "expectedEntryVersion": draft["entry"]["version"],
        "expectedThreadVersion": draft["threadVersion"],
        "ordinal": 0,
    }
    path = f"/thread-entries/{draft['entry']['entryId']}/attachments"
    attached = await request(f, "student", path, json=reference)
    assert attached.status == 201, await attached.text()
    result = await attached.json()
    assert result["entry"]["version"] == draft["entry"]["version"] + 1
    assert len(result["entry"]["attachments"]) == 1
    replay = await request(f, "student", path, json=reference)
    assert await replay.json() == result
    assert len(storage.heads) == 1
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT conversion_version FROM media_assets WHERE object_key=?", (key,)
            ).fetchone()["conversion_version"]
        )
        == "pwa-browser-image-v1"
    )
    mismatch = await request(f, "student", path, json={**reference, "ordinal": 1})
    assert mismatch.status == 409
    # A domain receipt must not let another intent bypass its immutable context.
    other = await ImageUploadService(f.factory, storage).prepare(
        record(f, grant["uploadId"])["account_id"],
        "student",
        {
            **description(),
            "purpose": "written",
            "context": {"problemId": "other-problem"},
        },
    )
    other_key = record(f, other["uploadId"])["object_key"]
    storage.objects[other_key] = PHOTO
    rejected = await request(
        f, "student", path, json={**reference, "uploadId": other["uploadId"]}
    )
    assert rejected.status == 409
    assert (await rejected.json())["error"]["code"] == "image_upload_context_mismatch"
    assert len(storage.heads) == 1
    assert record(f, other["uploadId"])["state"] == "pending"

"""Attachment bytes, public links and scoped upload APIs (rich-file-attachments.md)."""

from __future__ import annotations

import hashlib

import pytest
from aiohttp import FormData, MultipartWriter

from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from helpers.object_storage import (
    LocalObjectStorage,
    ObjectStorageOperationError,
    StoragePathError,
)
from helpers.pwa.rich_files import store_uploaded_rich_file
from models.pwa.rich_document import InvalidRichDocument, validate_rich_document
from models.pwa.rich_files import (
    MAX_RICH_FILE_BYTES,
    RICH_FILE_MIME_TYPES,
    InvalidRichFile,
    is_local_rich_file_url,
    local_rich_file_url,
    rich_file_key,
    rich_file_name,
)
from pwa_tests.integration import test_content_http_api as support


content_http = support.content_http
DIGEST = "a" * 64


class FileStorage:
    def __init__(self, *, public=True, fail=False):
        self.objects = []
        self.public = public
        self.fail = fail

    async def put(self, key, data, content_type):
        if self.fail:
            raise ObjectStorageOperationError(
                "put",
                provider_error_type="Unavailable",
                provider_code=None,
                http_status=503,
            )
        self.objects.append((key, data, content_type))

    def public_url(self, key):
        from urllib.parse import quote

        return f"https://cdn.example.test/{quote(key)}" if self.public else None


@pytest.mark.parametrize("extension,mime_type", RICH_FILE_MIME_TYPES.items())
async def test_preserves_bytes_and_uses_server_mime(extension, mime_type):
    storage = FileStorage()
    data = b"opaque original document bytes"
    result = await store_uploaded_rich_file(
        data, f"Материалы [1].{extension.upper()}", storage=storage
    )
    key, actual, actual_type = storage.objects[0]
    assert actual == data
    assert actual_type == mime_type
    assert key == rich_file_key(hashlib.sha256(data).hexdigest(), result["filename"])
    assert result["byteSize"] == len(data)
    assert result["url"].startswith("https://cdn.example.test/rich-files/sha256/")
    assert "%D0%9C" in result["url"]
    assert "%5B1%5D" in result["url"]


@pytest.mark.parametrize(
    "data,name", [(b"", "empty.pdf"), (b"x", "program.exe"), (b"x", "a" * 256 + ".pdf")]
)
async def test_invalid_upload_does_not_write(data, name):
    storage = FileStorage()
    with pytest.raises(InvalidRichFile):
        await store_uploaded_rich_file(data, name, storage=storage)
    assert storage.objects == []


async def test_exact_size_limit():
    storage = FileStorage()
    data = b"x" * MAX_RICH_FILE_BYTES
    await store_uploaded_rich_file(data, "large.zip", storage=storage)
    with pytest.raises(InvalidRichFile):
        await store_uploaded_rich_file(data + b"x", "large.zip", storage=storage)
    assert len(storage.objects) == 1


def test_filename_basename_and_url_policy():
    assert rich_file_name("../../Материалы\x00.pdf") == "Материалы.pdf"
    assert rich_file_name("C:\\files\\table.CSV") == "table.CSV"
    url = local_rich_file_url(DIGEST, "Материалы [1] (a).pdf")
    assert is_local_rich_file_url(url)
    document = {
        "schemaVersion": 1,
        "blocks": [
            {
                "type": "paragraph",
                "children": [
                    {
                        "type": "link",
                        "href": url,
                        "children": [{"type": "text", "text": "Документ"}],
                    }
                ],
            }
        ],
        "media": [],
    }
    assert validate_rich_document(document) == document
    for invalid in [
        url + "?x=1",
        url + "#part",
        "/pwa-rich-files/abc/a.pdf",
        f"/pwa-rich-files/{DIGEST}/%2e%2e%2Fa.pdf",
        f"/pwa-rich-files/{DIGEST}/file.exe",
        "//evil.test/a.pdf",
        "/other/a.pdf",
    ]:
        assert not is_local_rich_file_url(invalid)
        document["blocks"][0]["children"][0]["href"] = invalid
        with pytest.raises(InvalidRichDocument):
            validate_rich_document(document)


def form(data=b"original PDF", filename="Условия [1].pdf", *, extra=False):
    payload = FormData(quote_fields=False)
    payload.add_field("file", data, filename=filename, content_type="text/html")
    if extra:
        payload.add_field("extra", "unexpected")
    return payload


@pytest.mark.parametrize("lesson", [False, True])
async def test_authenticated_upload_and_public_filesystem_download(
    content_http, tmp_path, lesson
):
    storage = LocalObjectStorage(tmp_path / "files")
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    path = (
        f"/staff/api/v1/group-lessons/{content_http.group_lesson_a}/blocks/files/uploads"
        if lesson
        else "/staff/api/v1/rich-media/files/uploads"
    )
    response = await content_http.client.post(
        path,
        data=form(),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 201, await response.text()
    uploaded = (await response.json())["file"]
    assert uploaded["mimeType"] == "application/pdf"
    assert uploaded["filename"] == "Условия [1].pdf"
    # Public download does not require a product session.
    download = await content_http.client.get(uploaded["url"])
    assert download.status == 200, await download.text()
    assert await download.read() == b"original PDF"
    assert download.headers["X-Content-Type-Options"] == "nosniff"
    assert download.headers["Content-Type"] == "application/pdf"


@pytest.mark.parametrize(
    "filename,data,extra",
    [("bad.exe", b"x", False), ("empty.pdf", b"", False), ("ok.pdf", b"x", True)],
)
async def test_http_rejects_invalid_before_storage(content_http, filename, data, extra):
    storage = FileStorage()
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    response = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(data, filename, extra=extra),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 422, await response.text()
    assert storage.objects == []


async def test_http_size_limit_and_storage_failure(content_http):
    storage = FileStorage(fail=True)
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    response = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(b"x" * (MAX_RICH_FILE_BYTES + 1)),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 413, await response.text()
    failed = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert failed.status == 503, await failed.text()
    assert (await failed.json())["error"]["code"] == "rich_files_unavailable"


async def test_http_accepts_exact_size_limit(content_http):
    storage = FileStorage()
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    data = b"x" * MAX_RICH_FILE_BYTES
    response = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(data, "large.zip"),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 201, await response.text()
    assert (await response.json())["file"]["byteSize"] == MAX_RICH_FILE_BYTES
    assert storage.objects[0][1] == data


async def test_http_rejects_nested_multipart_without_writing(content_http):
    storage = FileStorage()
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    nested = MultipartWriter()
    nested.append(b"file")
    payload = MultipartWriter("form-data")
    part = payload.append(nested)
    part.set_content_disposition("form-data", name="file", filename="nested.zip")
    response = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=payload,
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 422, await response.text()
    assert storage.objects == []


@pytest.mark.parametrize(
    "error", [OSError("disk full"), StoragePathError("unsafe root")]
)
async def test_filesystem_upload_failure_is_reported_as_unavailable(
    content_http, tmp_path, error
):
    class UnavailableFilesystem(LocalObjectStorage):
        async def put(self, key, data, content_type):
            raise error

    storage = UnavailableFilesystem(tmp_path / "files")
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    response = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(),
        headers=support._headers(unsafe=True),
        cookies=support._cookie(content_http, "admin"),
    )
    assert response.status == 503, await response.text()
    assert (await response.json())["error"]["code"] == "rich_files_unavailable"
    assert list(storage.root.iterdir()) == []


async def test_permissions_are_checked_before_writing(content_http):
    storage = FileStorage()
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    for path in [
        "/staff/api/v1/rich-media/files/uploads",
        f"/staff/api/v1/group-lessons/{content_http.group_lesson_b}/blocks/files/uploads",
    ]:
        response = await content_http.client.post(
            path,
            data=form(),
            headers=support._headers(unsafe=True),
            cookies=support._cookie(content_http, "teacher"),
        )
        assert response.status == 403, await response.text()
    no_session = await content_http.client.post(
        "/staff/api/v1/rich-media/files/uploads",
        data=form(),
        headers=support._headers(unsafe=True),
    )
    assert no_session.status == 401, await no_session.text()
    assert storage.objects == []


async def test_local_route_rejects_traversal_and_symlinks(content_http, tmp_path):
    storage = LocalObjectStorage(tmp_path / "files")
    content_http.client.app[PWA_CONTENT_OBJECT_STORAGE] = storage
    key = rich_file_key(DIGEST, "secret.pdf")
    location = tmp_path / "files" / key
    location.parent.mkdir(parents=True)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"must not be served")
    location.symlink_to(outside)
    for path in [
        f"/pwa-rich-files/{DIGEST}/secret.pdf",
        f"/pwa-rich-files/{DIGEST}/%2e%2e%2Foutside.pdf",
    ]:
        response = await content_http.client.get(path)
        assert response.status == 404, await response.text()

"""Async object-storage adapters for PWA content and submission media.

Browser uploads remain proxied by aiohttp.  This module is the server-side
boundary and never generates write credentials or presigned upload URLs.  See
``vmshpwa/docs/object-storage.md`` and ``helpers.pwa.storage_config``.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import os
import re
import secrets
import stat
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import quote, urlsplit, urlunsplit

from helpers.pwa.storage_config import StorageConfig, StorageConfigurationError


_MAX_KEY_BYTES = 1024
_CONTENT_NAMESPACE_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_EXTENSION_RE = re.compile(r"[a-z0-9][a-z0-9.+-]{0,15}")
_CONTENT_TYPE_RE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")
_BEGET_ENDPOINT_RE = re.compile(r"s3\.[a-z0-9-]+\.storage\.beget\.cloud")
_SAFE_PROVIDER_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{0,63}")
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class StoragePathError(ValueError):
    """The supplied key or filesystem layout could escape its storage root."""


class ObjectStorageOperationError(RuntimeError):
    """Redacted provider failure safe for ordinary logging and Sentry."""

    def __init__(
        self,
        operation: str,
        *,
        provider_error_type: str,
        provider_code: str | None,
        http_status: int | None,
    ) -> None:
        self.operation = operation
        self.provider_error_type = provider_error_type
        self.provider_code = provider_code
        self.http_status = http_status
        details = [provider_error_type]
        if provider_code is not None:
            details.append(provider_code)
        if http_status is not None:
            details.append(f"HTTP-{http_status}")
        self.safe_detail = "/".join(details)
        super().__init__(f"Object storage {operation} failed ({self.safe_detail})")


@runtime_checkable
class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def public_url(self, key: str) -> str | None: ...


def canonical_object_key(key: str) -> str:
    """Validate a provider-independent, canonical relative object key."""

    if not isinstance(key, str) or not key or "\x00" in key or "\\" in key:
        raise StoragePathError("Object key must be a non-empty POSIX relative path")
    try:
        encoded_key = key.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise StoragePathError("Object key must be valid UTF-8") from exc
    if len(encoded_key) > _MAX_KEY_BYTES:
        raise StoragePathError("Object key exceeds the 1024-byte S3 limit")
    parts = key.split("/")
    if key.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise StoragePathError("Object key must be a canonical relative path")
    if any(
        any(unicodedata.category(character) == "Cc" for character in part)
        for part in parts
    ):
        raise StoragePathError("Object key cannot contain control characters")
    return key


def content_addressed_key(namespace: str, data: bytes, extension: str) -> str:
    """Build a stable SHA-256 key used by reusable generated/content assets."""

    if not _CONTENT_NAMESPACE_RE.fullmatch(namespace):
        raise StoragePathError("Content namespace is invalid")
    normalized_extension = extension.removeprefix(".").casefold()
    if not _EXTENSION_RE.fullmatch(normalized_extension):
        raise StoragePathError("Content extension is invalid")
    digest = hashlib.sha256(data).hexdigest()
    return (
        f"{namespace}/sha256/{digest[:2]}/{digest[2:4]}/{digest}.{normalized_extension}"
    )


def _validate_content_type(content_type: str) -> str:
    value = content_type.strip() if isinstance(content_type, str) else ""
    media_type = value.partition(";")[0].strip()
    if (
        len(value) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or not _CONTENT_TYPE_RE.fullmatch(media_type)
    ):
        raise ValueError("content_type must be a valid MIME header value")
    return value


def _raise_path_error(action: str, error: OSError) -> StoragePathError:
    return StoragePathError(f"Unsafe filesystem layout while {action} object")


def _redacted_provider_error(
    operation: str, error: Exception
) -> ObjectStorageOperationError:
    """Extract only standardized code/status; discard provider messages and URLs."""

    response = getattr(error, "response", None)
    provider_code: str | None = None
    http_status: int | None = None
    if isinstance(response, dict):
        error_payload = response.get("Error")
        if isinstance(error_payload, dict):
            candidate = error_payload.get("Code")
            if isinstance(candidate, str) and _SAFE_PROVIDER_CODE_RE.fullmatch(
                candidate
            ):
                provider_code = candidate
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict):
            candidate = metadata.get("HTTPStatusCode")
            if isinstance(candidate, int) and 100 <= candidate <= 599:
                http_status = candidate
    return ObjectStorageOperationError(
        operation,
        provider_error_type=type(error).__name__,
        provider_code=provider_code,
        http_status=http_status,
    )


class LocalObjectStorage:
    """Hermetic filesystem storage with openat/no-follow and atomic replacement."""

    def __init__(self, root: str | Path):
        if not _NOFOLLOW or not getattr(os, "O_DIRECTORY", 0):
            raise RuntimeError(
                "Filesystem object storage requires O_NOFOLLOW/O_DIRECTORY"
            )
        supplied_root = Path(root)
        if supplied_root.is_symlink():
            raise StoragePathError("Filesystem storage root cannot be a symlink")
        supplied_root.mkdir(parents=True, exist_ok=True)
        if supplied_root.is_symlink():
            raise StoragePathError("Filesystem storage root cannot be a symlink")
        self.root = supplied_root.resolve(strict=True)
        descriptor = self._open_root_fd()
        os.close(descriptor)

    def _open_root_fd(self) -> int:
        try:
            return os.open(self.root, _DIRECTORY_FLAGS | _NOFOLLOW)
        except OSError as exc:
            raise _raise_path_error("opening storage root for", exc) from exc

    @contextmanager
    def _parent_directory(self, key: str, *, create: bool) -> Iterator[tuple[int, str]]:
        parts = canonical_object_key(key).split("/")
        descriptor = self._open_root_fd()
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o750, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    except OSError as exc:
                        raise _raise_path_error("creating parent for", exc) from exc
                try:
                    next_descriptor = os.open(
                        part,
                        _DIRECTORY_FLAGS | _NOFOLLOW,
                        dir_fd=descriptor,
                    )
                except OSError as exc:
                    if isinstance(exc, FileNotFoundError):
                        raise
                    raise _raise_path_error("opening parent for", exc) from exc
                os.close(descriptor)
                descriptor = next_descriptor
            yield descriptor, parts[-1]
        finally:
            os.close(descriptor)

    @staticmethod
    def _reject_existing_symlink(parent_fd: int, name: str) -> None:
        try:
            target_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise _raise_path_error("checking", exc) from exc
        if stat.S_ISLNK(target_stat.st_mode):
            raise StoragePathError("Object target cannot be a symlink")
        if not stat.S_ISREG(target_stat.st_mode):
            raise StoragePathError("Object target must be a regular file")

    @staticmethod
    def _write_all(file_descriptor: int, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(file_descriptor, view)
            if written <= 0:
                raise OSError("short object-storage write")
            view = view[written:]

    def _put_sync(self, key: str, data: bytes) -> None:
        with self._parent_directory(key, create=True) as (parent_fd, name):
            self._reject_existing_symlink(parent_fd, name)
            temporary_name = f".vmsh-object-{secrets.token_hex(12)}.tmp"
            descriptor: int | None = None
            try:
                descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                    0o640,
                    dir_fd=parent_fd,
                )
                self._write_all(descriptor, data)
                os.fsync(descriptor)
                os.close(descriptor)
                descriptor = None
                # The destination check is intentionally repeated immediately
                # before the directory-fd rename. The fd-anchored operation
                # prevents a parent symlink swap from escaping the media root.
                self._reject_existing_symlink(parent_fd, name)
                os.replace(
                    temporary_name,
                    name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                os.fsync(parent_fd)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass

    def _get_sync(self, key: str) -> bytes:
        with self._parent_directory(key, create=False) as (parent_fd, name):
            self._reject_existing_symlink(parent_fd, name)
            try:
                descriptor = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent_fd)
            except OSError as exc:
                if isinstance(exc, FileNotFoundError):
                    raise
                raise _raise_path_error("reading", exc) from exc
            try:
                chunks: list[bytes] = []
                while chunk := os.read(descriptor, 128 * 1024):
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(descriptor)

    def _delete_sync(self, key: str) -> None:
        try:
            with self._parent_directory(key, create=False) as (parent_fd, name):
                self._reject_existing_symlink(parent_fd, name)
                try:
                    os.unlink(name, dir_fd=parent_fd)
                except FileNotFoundError:
                    return
                os.fsync(parent_fd)
        except FileNotFoundError:
            return

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        canonical_object_key(key)
        _validate_content_type(content_type)
        if not isinstance(data, bytes):
            raise TypeError("Object data must be bytes")
        await asyncio.to_thread(self._put_sync, key, data)

    async def get(self, key: str) -> bytes:
        canonical_object_key(key)
        return await asyncio.to_thread(self._get_sync, key)

    async def delete(self, key: str) -> None:
        canonical_object_key(key)
        await asyncio.to_thread(self._delete_sync, key)

    def public_url(self, key: str) -> None:
        canonical_object_key(key)
        return None


FilesystemObjectStorage = LocalObjectStorage


class S3ObjectStorage:
    """S3-compatible server-side adapter with explicit credentials and region."""

    def __init__(self, config: StorageConfig, *, session=None):
        if not isinstance(config, StorageConfig) or config.adapter != "s3":
            raise ValueError("S3ObjectStorage requires an S3 StorageConfig")
        self.config = config
        if session is None:
            import aioboto3

            session = aioboto3.Session()
        self._session = session

    def __repr__(self) -> str:
        return f"S3ObjectStorage(config={self.config!r})"

    def _key(self, key: str) -> str:
        safe_key = canonical_object_key(key)
        # S3's 1024-byte limit applies to the complete provider key, including
        # the runtime prefix—not merely to the domain-level relative key.
        provider_key = (
            f"{self.config.prefix}/{safe_key}" if self.config.prefix else safe_key
        )
        return canonical_object_key(provider_key)

    def _client(self):
        from aiobotocore.config import AioConfig

        return self._session.client(
            "s3",
            endpoint_url=self.config.endpoint_url,
            region_name=self.config.region,
            aws_access_key_id=self.config.access_key,
            aws_secret_access_key=self.config.secret_key,
            config=AioConfig(
                signature_version="s3v4",
                retries={"mode": "standard", "max_attempts": 3},
                s3={"addressing_style": "virtual"},
                # Modern botocore otherwise adds optional flexible checksums
                # that some S3-compatible providers reject. Required protocol
                # checksums and SigV4 payload signing remain enabled.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        object_key = self._key(key)
        mime_type = _validate_content_type(content_type)
        if not isinstance(data, bytes):
            raise TypeError("Object data must be bytes")
        provider_failure: ObjectStorageOperationError | None = None
        try:
            async with self._client() as client:
                await client.put_object(
                    Bucket=self.config.bucket_name,
                    Key=object_key,
                    Body=data,
                    ContentType=mime_type,
                )
        except Exception as exc:
            provider_failure = _redacted_provider_error("put", exc)
        if provider_failure is not None:
            # Raise outside the provider exception handler so even hidden
            # ``__context__`` cannot retain a URL-bearing SDK exception.
            raise provider_failure

    async def get(self, key: str) -> bytes:
        object_key = self._key(key)
        provider_failure: ObjectStorageOperationError | None = None
        try:
            async with self._client() as client:
                response = await client.get_object(
                    Bucket=self.config.bucket_name,
                    Key=object_key,
                )
                body = response["Body"]
                try:
                    return await body.read()
                finally:
                    close_result = body.close()
                    if inspect.isawaitable(close_result):
                        await close_result
        except Exception as exc:
            provider_failure = _redacted_provider_error("get", exc)
        if provider_failure is not None:
            raise provider_failure
        raise RuntimeError("unreachable object-storage get state")

    async def delete(self, key: str) -> None:
        object_key = self._key(key)
        provider_failure: ObjectStorageOperationError | None = None
        try:
            async with self._client() as client:
                await client.delete_object(
                    Bucket=self.config.bucket_name,
                    Key=object_key,
                )
        except Exception as exc:
            provider_failure = _redacted_provider_error("delete", exc)
        if provider_failure is not None:
            raise provider_failure

    def public_url(self, key: str) -> str:
        object_key = self._key(key)
        endpoint = urlsplit(self.config.endpoint_url or "")
        if self.config.public_base_url:
            base = urlsplit(self.config.public_base_url)
            netloc = base.netloc
        elif endpoint.hostname == f"{self.config.region}.your-objectstorage.com":
            # Hetzner documents public reads as
            # https://<bucket>.<location>.your-objectstorage.com/<key>.
            # An explicit public_base_url remains available for a CDN/CNAME.
            netloc = f"{self.config.bucket_name}.{endpoint.netloc}"
        elif endpoint.hostname and _BEGET_ENDPOINT_RE.fullmatch(endpoint.hostname):
            # Beget documents both path-style and virtual-hosted public URLs.
            # The latter maps directly to our DNS-style bucket validation and
            # keeps the provider prefix outside the object key.
            netloc = f"{self.config.bucket_name}.{endpoint.netloc}"
        else:
            # A generic S3 endpoint does not define its public virtual-host or
            # CDN shape. Guessing can leak a full key to an unrelated host.
            raise StorageConfigurationError(
                "Public GET for this S3 endpoint requires explicit s3_public_base_url"
            )
        encoded_key = quote(object_key, safe="/-._~")
        return urlunsplit(("https", netloc, f"/{encoded_key}", "", ""))


def create_object_storage(config: StorageConfig, *, session=None) -> ObjectStorage:
    if config.adapter == "filesystem":
        if config.filesystem_root is None:
            raise StorageConfigurationError(
                "Filesystem storage requires an explicit media root"
            )
        return LocalObjectStorage(config.filesystem_root)
    if config.adapter == "s3":
        return S3ObjectStorage(config, session=session)
    raise StorageConfigurationError(f"Unknown object-storage adapter: {config.adapter}")

"""Profile-aware object-storage configuration without legacy side effects.

This module deliberately does not import :mod:`helpers.config`: importing that
module selects the Telegram/Google legacy contour.  PWA storage profiles need a
small allowlisted loader which can be used by maintenance and integration
commands without initializing either adapter.  The governing contract is
``vmshpwa/dev/development-plan/00-engineering-contract.md``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, cast
from urllib.parse import urlsplit, urlunsplit


DEFAULT_S3_REGION = "us-east-1"
FILESYSTEM_RUNTIME_PROFILES = frozenset({"pwa-human", "pwa-agent", "pwa-e2e"})
S3_TEST_RUNTIME_PROFILE = "pwa-s3-integration"
S3_PRODUCTION_RUNTIME_PROFILE = "pwa-production"

_SECRET_PATHS = {
    "test": Path("creds_test/vmsh_bot_config_test.json"),
    "production": Path("creds_prod/vmsh_bot_config_prod.json"),
}
_S3_FIELD_NAMES = frozenset(
    {
        "s3_url",
        "s3_bucket_name",
        "s3_region",
        "s3_access_key",
        "s3_secret_key",
        "s3_prefix",
        "s3_public_base_url",
    }
)
_REQUIRED_S3_FIELDS = (
    "s3_url",
    "s3_bucket_name",
    "s3_access_key",
    "s3_secret_key",
)
_RUN_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_REGION_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
_BEGET_ENDPOINT_RE = re.compile(r"s3\.(?P<region>[a-z0-9-]+)\.storage\.beget\.cloud")
_HETZNER_ENDPOINT_RE = re.compile(r"(?P<region>[a-z0-9-]+)\.your-objectstorage\.com")
_DIRECTORY_FLAGS = (
    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0)
_MAX_SECRET_FILE_BYTES = 1024 * 1024


class StorageConfigurationError(ValueError):
    """Raised before storage I/O when a profile is unsafe or incomplete."""


def _https_origin(value: str, *, field_name: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise StorageConfigurationError(
            f"{field_name} must be an HTTPS origin without credentials, path, "
            "query, or fragment"
        )
    return urlunsplit(("https", parsed.netloc, "", "", ""))


def _safe_prefix(value: str) -> str:
    prefix = value.strip()
    if not prefix:
        return ""
    if (
        prefix.startswith("/")
        or prefix.endswith("/")
        or "\\" in prefix
        or any(ord(character) < 32 or ord(character) == 127 for character in prefix)
        or any(part in {"", ".", ".."} for part in prefix.split("/"))
    ):
        raise StorageConfigurationError(
            "s3_prefix must be a canonical relative key prefix"
        )
    if len(prefix.encode("utf-8")) > 900:
        raise StorageConfigurationError("s3_prefix is too long")
    return prefix


def _safe_bucket(value: str) -> str:
    bucket = value.strip()
    # The adapter deliberately uses virtual-host addressing over HTTPS. Dotted
    # and IP-shaped bucket names require provider-specific TLS/path-style
    # handling, so fail closed instead of producing a hostname outside the
    # documented Hetzner/Beget topology.
    if not _BUCKET_RE.fullmatch(bucket) or "." in bucket:
        raise StorageConfigurationError(
            "s3_bucket_name is not safe for HTTPS virtual-host addressing"
        )
    return bucket


def _default_region_for_endpoint(endpoint_url: str) -> str:
    """Return a documented provider region or the legacy generic default.

    Existing test credentials predate the explicit ``s3_region`` field. Beget's
    endpoint embeds the signing region and its current documentation requires
    ``ru1``. Unknown S3-compatible providers retain the old ``us-east-1``
    compatibility default rather than acquiring an unreviewed hostname rule.
    """

    hostname = urlsplit(endpoint_url).hostname or ""
    for pattern in (_BEGET_ENDPOINT_RE, _HETZNER_ENDPOINT_RE):
        match = pattern.fullmatch(hostname)
        if match:
            return match.group("region")
    return DEFAULT_S3_REGION


def _secret_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True, repr=False)
class StorageConfig:
    """Validated filesystem or S3 settings with a deliberately redacted repr."""

    adapter: Literal["filesystem", "s3"]
    filesystem_root: Path | None = None
    endpoint_url: str | None = None
    bucket_name: str | None = None
    region: str | None = None
    access_key: str | None = field(default=None, repr=False)
    secret_key: str | None = field(default=None, repr=False)
    prefix: str = ""
    public_base_url: str | None = None
    secret_source: Literal["none", "test", "production"] = "none"

    def __post_init__(self) -> None:
        """Enforce invariants even when callers bypass the named constructors."""

        if self.adapter == "filesystem":
            if not isinstance(self.filesystem_root, Path):
                raise StorageConfigurationError(
                    "Filesystem storage requires a pathlib.Path media root"
                )
            forbidden = (
                self.endpoint_url,
                self.bucket_name,
                self.region,
                self.access_key,
                self.secret_key,
                self.public_base_url,
            )
            if (
                any(value is not None for value in forbidden)
                or self.prefix
                or self.secret_source != "none"
            ):
                raise StorageConfigurationError(
                    "Filesystem storage cannot carry S3 settings"
                )
            return

        if self.adapter != "s3":
            raise StorageConfigurationError(
                f"Unknown object-storage adapter: {self.adapter}"
            )
        if self.filesystem_root is not None:
            raise StorageConfigurationError("S3 storage cannot use a filesystem root")
        if self.secret_source not in {"test", "production"}:
            raise StorageConfigurationError(
                "S3 storage must declare test or production secret source"
            )

        required = {
            "s3_url": self.endpoint_url,
            "s3_bucket_name": self.bucket_name,
            "s3_region": self.region,
            "s3_access_key": self.access_key,
            "s3_secret_key": self.secret_key,
        }
        missing = [
            name
            for name, value in required.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise StorageConfigurationError(
                "S3 configuration is incomplete; missing: " + ", ".join(missing)
            )

        if not isinstance(self.prefix, str):
            raise StorageConfigurationError("s3_prefix must be a string")
        if self.public_base_url is not None and not isinstance(
            self.public_base_url, str
        ):
            raise StorageConfigurationError("s3_public_base_url must be a string")
        endpoint_url = cast(str, self.endpoint_url)
        bucket_name = cast(str, self.bucket_name)
        region = cast(str, self.region)
        access_key = cast(str, self.access_key)
        secret_key = cast(str, self.secret_key)
        if _https_origin(endpoint_url, field_name="s3_url") != endpoint_url:
            raise StorageConfigurationError("s3_url must already be normalized")
        if _safe_bucket(bucket_name) != bucket_name:
            raise StorageConfigurationError("s3_bucket_name must already be normalized")
        if not _REGION_RE.fullmatch(region):
            raise StorageConfigurationError("s3_region is invalid")
        if access_key.strip() != access_key:
            raise StorageConfigurationError("s3_access_key must not have outer spaces")
        if secret_key.strip() != secret_key:
            raise StorageConfigurationError("s3_secret_key must not have outer spaces")
        if _safe_prefix(self.prefix) != self.prefix:
            raise StorageConfigurationError("s3_prefix must already be normalized")
        if self.public_base_url is not None and (
            _https_origin(self.public_base_url, field_name="s3_public_base_url")
            != self.public_base_url
        ):
            raise StorageConfigurationError(
                "s3_public_base_url must already be normalized"
            )

    @classmethod
    def filesystem(cls, root: str | Path) -> StorageConfig:
        if isinstance(root, str) and not root.strip():
            raise StorageConfigurationError("filesystem media root is required")
        path = Path(root)
        return cls(adapter="filesystem", filesystem_root=path)

    @classmethod
    def s3(
        cls,
        *,
        endpoint_url: str,
        bucket_name: str,
        region: str,
        access_key: str,
        secret_key: str,
        prefix: str,
        public_base_url: str | None = None,
        secret_source: Literal["test", "production"],
    ) -> StorageConfig:
        missing = [
            name
            for name, value in (
                ("s3_url", endpoint_url),
                ("s3_bucket_name", bucket_name),
                ("s3_region", region),
                ("s3_access_key", access_key),
                ("s3_secret_key", secret_key),
            )
            if not isinstance(value, str) or not value.strip()
        ]
        if missing:
            raise StorageConfigurationError(
                "S3 configuration is incomplete; missing: " + ", ".join(missing)
            )
        endpoint = _https_origin(endpoint_url, field_name="s3_url")
        normalized_region = region.strip()
        if not _REGION_RE.fullmatch(normalized_region):
            raise StorageConfigurationError("s3_region is invalid")
        public_origin = (
            _https_origin(public_base_url, field_name="s3_public_base_url")
            if public_base_url
            else None
        )
        return cls(
            adapter="s3",
            endpoint_url=endpoint,
            bucket_name=_safe_bucket(bucket_name),
            region=normalized_region,
            access_key=access_key.strip(),
            secret_key=secret_key.strip(),
            prefix=_safe_prefix(prefix),
            public_base_url=public_origin,
            secret_source=secret_source,
        )

    def safe_report(self) -> dict[str, str | bool | None]:
        """Return operational metadata without credentials, bucket, prefix, or URL."""

        if self.adapter == "filesystem":
            return {
                "adapter": "filesystem",
                "externalNetwork": False,
                "secretSource": "none",
            }
        if self.endpoint_url is None or self.bucket_name is None:
            raise StorageConfigurationError("Invalid S3 storage configuration")
        endpoint_host = urlsplit(self.endpoint_url).hostname
        public_host = (
            urlsplit(self.public_base_url).hostname if self.public_base_url else None
        )
        prefix_scope = (
            "integration"
            if self.prefix == "integration" or self.prefix.startswith("integration/")
            else ("configured" if self.prefix else "bucket-root")
        )
        return {
            "adapter": "s3",
            "endpointHost": endpoint_host,
            "bucketFingerprint": _secret_fingerprint(self.bucket_name),
            "region": self.region,
            "prefixScope": prefix_scope,
            "publicHost": public_host,
            "externalNetwork": True,
            "secretSource": self.secret_source,
        }

    def __repr__(self) -> str:
        try:
            report = self.safe_report()
        except StorageConfigurationError:
            return "StorageConfig(invalid=True)"
        fields = ", ".join(f"{name}={value!r}" for name, value in report.items())
        return f"StorageConfig({fields})"


def _read_secret_overlay(
    source: Literal["test", "production"], *, repository_root: Path
) -> dict[str, object]:
    """Read only the S3 allowlist from one fixed test/production config path."""

    try:
        relative_path = _SECRET_PATHS[source]
    except KeyError as exc:
        raise StorageConfigurationError(
            f"Unknown storage secret source: {source}"
        ) from exc

    try:
        canonical_root = repository_root.resolve(strict=True)
    except OSError as exc:
        raise StorageConfigurationError(
            "Storage repository root does not exist"
        ) from exc
    if not _NOFOLLOW or not getattr(os, "O_DIRECTORY", 0):
        raise StorageConfigurationError(
            "Storage credential loading requires no-follow directory descriptors"
        )

    descriptors: list[int] = []
    try:
        parent_fd = os.open(canonical_root, _DIRECTORY_FLAGS | _NOFOLLOW)
        descriptors.append(parent_fd)
        for part in relative_path.parts[:-1]:
            parent_fd = os.open(
                part,
                _DIRECTORY_FLAGS | _NOFOLLOW,
                dir_fd=parent_fd,
            )
            descriptors.append(parent_fd)
        file_fd = os.open(
            relative_path.parts[-1],
            _FILE_FLAGS | _NOFOLLOW,
            dir_fd=parent_fd,
        )
        descriptors.append(file_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise StorageConfigurationError(
                "Storage credential source must be one regular, non-aliased file"
            )
        if before.st_size > _MAX_SECRET_FILE_BYTES:
            raise StorageConfigurationError("Storage credential file is too large")

        chunks: list[bytes] = []
        offset = 0
        while offset <= _MAX_SECRET_FILE_BYTES:
            chunk = os.pread(file_fd, 64 * 1024, offset)
            if not chunk:
                break
            chunks.append(chunk)
            offset += len(chunk)
        after = os.fstat(file_fd)
        path_after = os.stat(
            relative_path.parts[-1],
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        path_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_nlink,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if (
            before_identity != after_identity
            or after_identity != path_identity
            or offset != after.st_size
        ):
            raise StorageConfigurationError(
                "Storage credential source changed while it was being read"
            )
        if offset > _MAX_SECRET_FILE_BYTES:
            raise StorageConfigurationError("Storage credential file is too large")
        document = json.loads(b"".join(chunks).decode("utf-8"))
    except StorageConfigurationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageConfigurationError(
            f"Cannot load {source} storage credential file through symlink-safe path"
        ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    if not isinstance(document, dict):
        raise StorageConfigurationError(
            "Storage credential file must contain an object"
        )
    # The parser necessarily decodes the JSON document, but callers receive only
    # these fields.  In particular no Telegram/Google value enters runtime config.
    return {name: document[name] for name in _S3_FIELD_NAMES if name in document}


def _string_field(overlay: Mapping[str, object], name: str) -> str:
    value = overlay.get(name)
    return value.strip() if isinstance(value, str) else ""


def _s3_from_overlay(
    overlay: Mapping[str, object],
    *,
    source: Literal["test", "production"],
    forced_prefix: str | None = None,
) -> StorageConfig:
    missing = [name for name in _REQUIRED_S3_FIELDS if not _string_field(overlay, name)]
    if missing:
        raise StorageConfigurationError(
            "S3 configuration is incomplete; missing: " + ", ".join(missing)
        )
    prefix = (
        forced_prefix
        if forced_prefix is not None
        else _string_field(overlay, "s3_prefix")
    )
    endpoint_url = _string_field(overlay, "s3_url")
    region = _string_field(overlay, "s3_region") or _default_region_for_endpoint(
        endpoint_url
    )
    return StorageConfig.s3(
        endpoint_url=endpoint_url,
        bucket_name=_string_field(overlay, "s3_bucket_name"),
        region=region,
        access_key=_string_field(overlay, "s3_access_key"),
        secret_key=_string_field(overlay, "s3_secret_key"),
        prefix=prefix,
        public_base_url=_string_field(overlay, "s3_public_base_url") or None,
        secret_source=source,
    )


def load_storage_config(
    *,
    runtime_profile: str,
    media_root: str | Path,
    repository_root: str | Path,
    integration_run_id: str | None = None,
) -> StorageConfig:
    """Select the sole allowed storage source for a complete runtime profile."""

    root = Path(repository_root)
    if runtime_profile in FILESYSTEM_RUNTIME_PROFILES:
        return StorageConfig.filesystem(media_root)
    if runtime_profile == S3_TEST_RUNTIME_PROFILE:
        if integration_run_id is None or not _RUN_ID_RE.fullmatch(integration_run_id):
            raise StorageConfigurationError(
                "S3 integration requires a lowercase safe integration run id"
            )
        overlay = _read_secret_overlay("test", repository_root=root)
        return _s3_from_overlay(
            overlay,
            source="test",
            forced_prefix=f"integration/{integration_run_id}",
        )
    if runtime_profile == S3_PRODUCTION_RUNTIME_PROFILE:
        if integration_run_id is not None:
            raise StorageConfigurationError(
                "Production storage cannot use an integration run id"
            )
        overlay = _read_secret_overlay("production", repository_root=root)
        config = _s3_from_overlay(overlay, source="production")
        if config.prefix == "integration" or config.prefix.startswith("integration/"):
            raise StorageConfigurationError(
                "Production storage cannot use the integration prefix"
            )
        return config
    raise StorageConfigurationError(
        f"Unknown object-storage runtime profile: {runtime_profile}"
    )

"""Descriptor-based reads for local preflight source files.

The helper rejects final-component symlinks and hard links, compares ``lstat``
with ``fstat``, and hashes bytes through the opened descriptor.  On platforms
with ``O_NOFOLLOW_ANY`` it also asks the kernel to reject symlinks in every path
component; elsewhere ``O_NOFOLLOW`` protects only the final component.
"""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class SafeSourceError(RuntimeError):
    """Raised when a local source cannot be read with the required guarantees."""


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    device: int
    inode: int
    link_count: int
    size: int
    modified_ns: int
    changed_ns: int
    sha256: str


def nofollow_capability() -> str:
    """Describe the kernel path-following protection used by ``secure_open``."""

    if getattr(os, "O_NOFOLLOW_ANY", 0):
        return "O_NOFOLLOW_ANY"
    if getattr(os, "O_NOFOLLOW", 0):
        return "O_NOFOLLOW(final-component)"
    return "lstat/fstat-only"


def _validate_regular_single_link(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise SafeSourceError("Expected a regular source file")
    if metadata.st_nlink != 1:
        raise SafeSourceError("Source files must not be hard-linked aliases")


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


@contextmanager
def secure_open(path: Path) -> Iterator[int]:
    """Open one regular, single-link source and keep its descriptor alive."""

    source_path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow_any = getattr(os, "O_NOFOLLOW_ANY", 0)
    flags |= nofollow_any or getattr(os, "O_NOFOLLOW", 0)
    try:
        path_before = source_path.lstat()
        if stat.S_ISLNK(path_before.st_mode):
            raise SafeSourceError("Source files must not be symlinks")
        _validate_regular_single_link(path_before)
        descriptor = os.open(source_path, flags)
    except OSError as error:
        raise SafeSourceError("Could not securely open source file") from error

    try:
        opened = os.fstat(descriptor)
        _validate_regular_single_link(opened)
        if _identity(path_before) != _identity(opened):
            raise SafeSourceError("Source path changed while it was being opened")
        yield descriptor
    finally:
        os.close(descriptor)


def _read_descriptor(
    descriptor: int, *, keep_content: bool
) -> tuple[SourceFingerprint, bytes]:
    """Read and hash one descriptor, optionally retaining its bytes."""

    try:
        before = os.fstat(descriptor)
        _validate_regular_single_link(before)
        chunks: list[bytes] | None = [] if keep_content else None
        digest = hashlib.sha256()
        offset = 0
        while True:
            chunk = os.pread(descriptor, 1024 * 1024, offset)
            if not chunk:
                break
            if chunks is not None:
                chunks.append(chunk)
            digest.update(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        _validate_regular_single_link(after)
    except OSError as error:
        raise SafeSourceError("Could not read source descriptor") from error

    before_metadata = (
        before.st_dev,
        before.st_ino,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_metadata = (
        after.st_dev,
        after.st_ino,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_metadata != after_metadata or offset != after.st_size:
        raise SafeSourceError("Source descriptor changed while it was being read")

    return (
        SourceFingerprint(*after_metadata, sha256=digest.hexdigest()),
        b"".join(chunks) if chunks is not None else b"",
    )


def read_and_fingerprint(descriptor: int) -> tuple[SourceFingerprint, bytes]:
    """Read, retain and hash all bytes through one checked descriptor."""

    return _read_descriptor(descriptor, keep_content=True)


def fingerprint(descriptor: int) -> SourceFingerprint:
    """Re-hash one checked descriptor without retaining another byte copy."""

    result, _content = _read_descriptor(descriptor, keep_content=False)
    return result


def verify_path_matches(path: Path, fingerprint: SourceFingerprint) -> None:
    """Verify that a path still names the descriptor-fingerprinted inode."""

    try:
        metadata = Path(path).lstat()
    except OSError as error:
        raise SafeSourceError("Source path disappeared after opening") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise SafeSourceError("Source path became a symlink")
    _validate_regular_single_link(metadata)
    observed = (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )
    expected = (
        fingerprint.device,
        fingerprint.inode,
        fingerprint.link_count,
        fingerprint.size,
        fingerprint.modified_ns,
        fingerprint.changed_ns,
    )
    if observed != expected:
        raise SafeSourceError("Source path no longer matches the opened descriptor")

"""Process-lifetime coordination for replacing or migrating a PWA SQLite DB."""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import TracebackType

import fcntl


class DatabaseLifecycleBusyError(RuntimeError):
    """The database is running or undergoing exclusive maintenance."""


class DatabaseLifecycleLockMode(str, Enum):
    RUNTIME = "runtime"
    MAINTENANCE = "maintenance"


def _canonical_database_path(database_path: str | Path) -> Path:
    lexical_path = Path(database_path).absolute()
    if lexical_path.is_symlink():
        raise RuntimeError(
            f"SQLite database path must not be a symlink: {lexical_path}"
        )
    try:
        metadata = lexical_path.stat(follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(
                f"SQLite database path must be a regular file: {lexical_path}"
            )
        if metadata.st_nlink != 1:
            # SQLite derives journal/WAL names from the pathname. Two hard-link
            # aliases can therefore bypass both SQLite and application locks.
            # Primary source and decision: ADR 0002.
            raise RuntimeError(
                "SQLite database must have exactly one hard link: "
                f"{lexical_path}"
            )
    return lexical_path.resolve(strict=False)


def lifecycle_lock_path(database_path: str | Path) -> Path:
    """Return the stable sidecar used to coordinate a database pathname.

    The lock is deliberately separate from SQLite's own file locks: SQLite
    cannot protect an application-level ``os.replace`` of its pathname.  The
    lock file itself is never replaced or removed, so all cooperating workers
    keep referring to the same inode.

    Decision: ``adr/0002-pwa-sqlite-concurrency-and-migrations.md``.
    """

    canonical_database_path = _canonical_database_path(database_path)
    return canonical_database_path.with_name(
        f".{canonical_database_path.name}.vmshpwa-lifecycle.lock"
    )


@dataclass(slots=True)
class DatabaseLifecycleLock:
    """A fail-fast shared runtime or exclusive maintenance advisory lock."""

    database_path: str | Path
    mode: DatabaseLifecycleLockMode
    _descriptor: int | None = field(default=None, init=False, repr=False)

    @property
    def lock_path(self) -> Path:
        return lifecycle_lock_path(self.database_path)

    @property
    def acquired(self) -> bool:
        return self._descriptor is not None

    def acquire(self) -> DatabaseLifecycleLock:
        if self._descriptor is not None:
            raise RuntimeError("SQLite lifecycle lock is already acquired")

        path = self.lock_path
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError(
                "SQLite lifecycle lock requires POSIX O_NOFOLLOW support"
            )
        flags |= os.O_NOFOLLOW

        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise RuntimeError(
                    f"SQLite lifecycle lock must not be a symlink: {path}"
                ) from exc
            raise

        try:
            metadata = os.fstat(descriptor)
            os.set_inheritable(descriptor, False)
            if metadata.st_uid != os.geteuid():
                raise RuntimeError(
                    "SQLite lifecycle lock must be owned by the service identity: "
                    f"{path}"
                )
            os.fchmod(descriptor, 0o600)
            named_metadata = path.stat(follow_symlinks=False)
            if (metadata.st_dev, metadata.st_ino) != (
                named_metadata.st_dev,
                named_metadata.st_ino,
            ):
                raise RuntimeError(
                    f"SQLite lifecycle lock pathname changed while opening: {path}"
                )
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise RuntimeError(
                    "SQLite lifecycle lock must be a single-link regular file: "
                    f"{path}"
                )
            # Recheck DB identity after opening the stable lock file. This
            # catches a final-component symlink/hard-link alias introduced in
            # the small window between path derivation and flock acquisition.
            if lifecycle_lock_path(self.database_path) != path:
                raise RuntimeError(
                    "SQLite database identity changed while acquiring lifecycle lock"
                )
            operation = (
                fcntl.LOCK_SH
                if self.mode is DatabaseLifecycleLockMode.RUNTIME
                else fcntl.LOCK_EX
            )
            try:
                fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in {
                    errno.EACCES,
                    errno.EAGAIN,
                    errno.EWOULDBLOCK,
                }:
                    raise
                owner = (
                    "a maintenance command"
                    if self.mode is DatabaseLifecycleLockMode.RUNTIME
                    else "one or more PWA runtime workers"
                )
                raise DatabaseLifecycleBusyError(
                    f"SQLite lifecycle lock is held by {owner}; retry after it stops: "
                    f"{path}"
                ) from exc
        except BaseException:
            os.close(descriptor)
            raise

        self._descriptor = descriptor
        return self

    def release(self) -> None:
        descriptor = self._descriptor
        if descriptor is None:
            return
        self._descriptor = None
        # Do not issue LOCK_UN explicitly. ``flock`` belongs to the open-file
        # description, which may have been inherited across fork; unlocking an
        # inherited duplicate could release the parent's lock. Runtime acquires
        # only after Gunicorn forks, CLOEXEC prevents exec inheritance, and
        # close-only release keeps a lock until the final duplicate is closed.
        # Decision: ADR 0002 and test_runtime_lifecycle_lock.py.
        os.close(descriptor)

    def __enter__(self) -> DatabaseLifecycleLock:
        return self.acquire()

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.release()


def runtime_database_lock(database_path: str | Path) -> DatabaseLifecycleLock:
    return DatabaseLifecycleLock(database_path, DatabaseLifecycleLockMode.RUNTIME)


def maintenance_database_lock(database_path: str | Path) -> DatabaseLifecycleLock:
    return DatabaseLifecycleLock(database_path, DatabaseLifecycleLockMode.MAINTENANCE)

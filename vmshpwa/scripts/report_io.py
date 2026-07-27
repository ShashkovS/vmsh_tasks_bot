"""Crash-resistant single-file writes for generated aggregate reports.

Each target is replaced atomically on its own filesystem after the temporary
file has been flushed.  The parent directory is flushed after ``os.replace`` so
the new directory entry is durable.  A pair of report files is intentionally
not presented as a transaction; the corresponding ``check`` command detects a
partial or stale pair.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class AtomicReportWriteError(RuntimeError):
    """Raised when a generated report could not be durably replaced."""


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace one UTF-8 text file and fsync file plus directory."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    replaced = False
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o644)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, target)
        replaced = True
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(target.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        if temporary_path is not None and not replaced:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise AtomicReportWriteError(
            f"Could not durably replace generated report {target}"
        ) from error

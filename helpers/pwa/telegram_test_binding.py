"""Owner-local immutable binding for the dedicated Telegram test channel.

The live test uses a two-step trust flow: a read-only Bot API capability probe
stores the reviewed canonical identity here, then a later write-enabled smoke
loads the destination only from this SQLite file. Environment variables never
select a destination for the send/edit/delete step.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

from helpers.pwa.telegram_test_harness import (
    EXPECTED_TEST_BOT_USERNAME,
    EXPECTED_TEST_CHANNEL_TITLE,
    VerifiedTelegramBinding,
)
from vmshpwa.scripts.safe_source import (
    SafeSourceError,
    read_and_fingerprint,
    secure_open,
    verify_path_matches,
)


class TelegramTestBindingError(RuntimeError):
    """The local test-channel trust record is missing, unsafe or inconsistent."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_telegram_test_binding (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    chat_id INTEGER NOT NULL CHECK (chat_id < 0),
    chat_title TEXT NOT NULL,
    bot_id INTEGER NOT NULL CHECK (bot_id > 0),
    bot_username TEXT NOT NULL,
    verified_at TEXT NOT NULL
) STRICT;
"""
_MAX_BINDING_DATABASE_BYTES = 1024 * 1024


def _validate_binding(binding: VerifiedTelegramBinding) -> None:
    if (
        not isinstance(binding.chat_id, int)
        or isinstance(binding.chat_id, bool)
        or not -(2**63) <= binding.chat_id < 0
        or binding.chat_title != EXPECTED_TEST_CHANNEL_TITLE
        or not isinstance(binding.bot_id, int)
        or isinstance(binding.bot_id, bool)
        or not 0 < binding.bot_id < 2**63
        or binding.bot_username != EXPECTED_TEST_BOT_USERNAME
    ):
        raise TelegramTestBindingError(
            "Telegram test binding identity does not match the dedicated target"
        )


def _prepare_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError as error:
        raise TelegramTestBindingError(
            "Cannot protect the local Telegram binding directory"
        ) from error


def _reject_unsafe_existing_path(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or metadata.st_size > _MAX_BINDING_DATABASE_BYTES
    ):
        raise TelegramTestBindingError(
            "Local Telegram binding must be an owner-only regular file"
        )


def save_verified_binding(
    path: Path,
    binding: VerifiedTelegramBinding,
) -> None:
    """Create the trust record once; a different identity fails closed."""

    _validate_binding(binding)
    target = Path(path)
    _prepare_parent(target)
    _reject_unsafe_existing_path(target)
    if not target.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
        except FileExistsError:
            _reject_unsafe_existing_path(target)
        except OSError as error:
            raise TelegramTestBindingError(
                "Cannot create the local Telegram binding database"
            ) from error
        else:
            os.close(descriptor)
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute(_SCHEMA)
        os.chmod(target, 0o600)
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT chat_id, chat_title, bot_id, bot_username
            FROM verified_telegram_test_binding
            WHERE singleton = 1
            """
        ).fetchone()
        candidate = (
            binding.chat_id,
            binding.chat_title,
            binding.bot_id,
            binding.bot_username,
        )
        if row is not None and tuple(row) != candidate:
            connection.rollback()
            raise TelegramTestBindingError(
                "A different Telegram test binding is already trusted"
            )
        verified_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        connection.execute(
            """
            INSERT INTO verified_telegram_test_binding (
                singleton, chat_id, chat_title, bot_id, bot_username, verified_at
            ) VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(singleton) DO UPDATE SET verified_at = excluded.verified_at
            """,
            (*candidate, verified_at),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def load_verified_binding(path: Path) -> VerifiedTelegramBinding:
    """Load the sole immutable destination used by a write-enabled smoke."""

    target = Path(path)
    _reject_unsafe_existing_path(target)
    if not target.exists():
        raise TelegramTestBindingError(
            "No trusted Telegram test binding; run the read-only bind step first"
        )
    if any(
        target.with_name(target.name + suffix).exists()
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise TelegramTestBindingError(
            "Local Telegram test binding must be a quiescent SQLite file"
        )
    try:
        with secure_open(target) as descriptor:
            fingerprint, content = read_and_fingerprint(descriptor)
        verify_path_matches(target, fingerprint)
    except SafeSourceError as error:
        raise TelegramTestBindingError(
            "Local Telegram test binding changed or is unsafe"
        ) from error

    connection = sqlite3.connect(":memory:", autocommit=True)
    try:
        deserialize = getattr(connection, "deserialize", None)
        if not callable(deserialize):
            raise TelegramTestBindingError(
                "SQLite deserialize is required for the Telegram test binding"
            )
        deserialize(content)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        row = connection.execute(
            """
            SELECT chat_id, chat_title, bot_id, bot_username
            FROM verified_telegram_test_binding
            WHERE singleton = 1
            """
        ).fetchone()
    except sqlite3.Error as error:
        raise TelegramTestBindingError(
            "Local Telegram test binding database is invalid"
        ) from error
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
    if row is None:
        raise TelegramTestBindingError("Local Telegram test binding is empty")
    chat_id, chat_title, bot_id, bot_username = row
    if (
        not isinstance(chat_id, int)
        or isinstance(chat_id, bool)
        or chat_id >= 0
        or not isinstance(chat_title, str)
        or not chat_title
        or not isinstance(bot_id, int)
        or isinstance(bot_id, bool)
        or bot_id <= 0
        or not isinstance(bot_username, str)
        or not bot_username
    ):
        raise TelegramTestBindingError("Local Telegram test binding row is invalid")
    binding = VerifiedTelegramBinding(
        chat_id=chat_id,
        chat_title=chat_title,
        bot_id=bot_id,
        bot_username=bot_username,
    )
    _validate_binding(binding)
    return binding

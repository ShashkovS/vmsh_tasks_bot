"""Strictly opt-in live capability smoke for the dedicated Telegram test channel.

The command never starts polling/webhooks and never imports helpers.config. It
reads one allowlisted key from the ignored test config only after explicit
operator gates. A read-only bind step persists the verified identity first; the
later write-enabled smoke can select its destination only from that local DB.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import stat
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from helpers.pwa.telegram_test_harness import (
    EXPECTED_TEST_BOT_USERNAME,
    EXPECTED_TEST_CHANNEL_TITLE,
    TelegramCapabilityError,
    TelegramLifecycleError,
    VerifiedTelegramBinding,
    run_synthetic_message_lifecycle,
    verify_test_channel_binding,
)
from helpers.pwa.telegram_test_binding import (
    TelegramTestBindingError,
    load_verified_binding,
    save_verified_binding,
)
from vmshpwa.scripts.report_io import atomic_write_text

ROOT = Path(__file__).resolve().parents[2]
TEST_CONFIG_PATH = ROOT / "creds_test" / "vmsh_bot_config_test.json"
REPORT_ROOT = ROOT / ".runtime" / "vmshpwa" / "telegram-smoke"
BINDING_DATABASE_PATH = REPORT_ROOT / "bindings.sqlite3"
LIVE_ENVIRONMENT_FLAG = "VMSH_RUN_TELEGRAM_LIVE_SMOKE"
CHANNEL_ID_ENVIRONMENT_KEY = "VMSH_TELEGRAM_TEST_CHANNEL_ID"
CONFIRMATION = "vmsh179devbot-channel-synthetic"
_TOKEN_SHAPE = re.compile(r"^[1-9][0-9]{4,15}:[A-Za-z0-9_-]{20,128}$")
_MAX_TEST_CONFIG_BYTES = 256 * 1024


class LiveTelegramGuardError(RuntimeError):
    """Raised before network access when an opt-in or credential guard fails."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send/edit/delete one synthetic message in the dedicated test channel"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="acknowledge that this command performs Telegram network writes",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--bind-channel",
        action="store_true",
        help="verify and persist a destination without sending a message",
    )
    action.add_argument(
        "--run-smoke",
        action="store_true",
        help="send/edit/delete using only the persisted destination",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"must be exactly {CONFIRMATION!r}",
    )
    return parser


def validate_live_opt_in(
    *,
    live: bool,
    confirmation: str,
    bind_channel: bool,
    run_smoke: bool,
) -> None:
    """Fail closed before credential loading or Bot API construction."""

    if not live:
        raise LiveTelegramGuardError("The --live acknowledgement is required")
    if confirmation != CONFIRMATION:
        raise LiveTelegramGuardError("The dedicated test-channel confirmation is wrong")
    if os.environ.get(LIVE_ENVIRONMENT_FLAG) != "1":
        raise LiveTelegramGuardError(
            f"Set {LIVE_ENVIRONMENT_FLAG}=1 for this one opt-in invocation"
        )
    if os.environ.get("PROD", "").casefold() == "true":
        raise LiveTelegramGuardError(
            "Live test capability is disabled in production mode"
        )

    if bind_channel == run_smoke:
        raise LiveTelegramGuardError(
            "Select exactly one of --bind-channel or --run-smoke"
        )
    if run_smoke and CHANNEL_ID_ENVIRONMENT_KEY in os.environ:
        raise LiveTelegramGuardError(
            "The write-enabled smoke refuses an environment destination"
        )


def requested_chat_id_from_environment() -> int:
    """Return a canonical ID only for the read-only bind step."""

    raw_chat_id = os.environ.get(CHANNEL_ID_ENVIRONMENT_KEY, "")
    try:
        chat_id = int(raw_chat_id)
    except ValueError as error:
        raise LiveTelegramGuardError(
            f"{CHANNEL_ID_ENVIRONMENT_KEY} must contain the canonical Bot API chat ID"
        ) from error
    # Telegram Bot API channel IDs are signed 64-bit values. Requiring a negative
    # canonical ID rejects the positive UI fragment without inventing a -100 form.
    if chat_id >= 0 or chat_id < -(2**63):
        raise LiveTelegramGuardError(
            f"{CHANNEL_ID_ENVIRONMENT_KEY} is not a canonical signed channel ID"
        )
    return chat_id


def load_allowlisted_test_bot_token() -> str:
    """Read only telegram_bot_token from the fixed ignored test config."""

    path = TEST_CONFIG_PATH
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        no_follow = getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0)
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode):
            raise LiveTelegramGuardError("Test credential file must not be a symlink")
        descriptor = os.open(path, flags | no_follow)
        file_stat = os.fstat(descriptor)
        # inode comparison protects platforms without O_NOFOLLOW from replacing the
        # checked path with a symlink between lstat and open.
        if (before.st_dev, before.st_ino) != (file_stat.st_dev, file_stat.st_ino):
            raise LiveTelegramGuardError("Test credential file changed while opening")
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_nlink != 1
            or file_stat.st_size > _MAX_TEST_CONFIG_BYTES
        ):
            raise LiveTelegramGuardError(
                "Dedicated test credential file is not a small regular file"
            )
        content = bytearray()
        while len(content) <= _MAX_TEST_CONFIG_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, _MAX_TEST_CONFIG_BYTES + 1 - len(content)),
            )
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > _MAX_TEST_CONFIG_BYTES:
            raise LiveTelegramGuardError("Dedicated test credential file is too large")
        after = os.fstat(descriptor)
        path_after = path.lstat()
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        path_after_identity = (
            path_after.st_dev,
            path_after.st_ino,
            path_after.st_size,
            path_after.st_mtime_ns,
            path_after.st_ctime_ns,
        )
        if (
            before_identity != after_identity
            or after_identity != path_after_identity
            or len(content) != after.st_size
        ):
            raise LiveTelegramGuardError(
                "Test credential file changed while it was being read"
            )
    except OSError as error:
        raise LiveTelegramGuardError(
            "Dedicated test credential file is unavailable"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        payload = json.loads(bytes(content).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LiveTelegramGuardError(
            "Dedicated test credential file is invalid"
        ) from error
    if not isinstance(payload, dict):
        raise LiveTelegramGuardError(
            "Dedicated test credential file must contain an object"
        )
    token = payload.get("telegram_bot_token")
    if not isinstance(token, str) or not _TOKEN_SHAPE.fullmatch(token):
        raise LiveTelegramGuardError("Dedicated test bot token is missing or malformed")
    return token


def _safe_report(
    *,
    run_id: str,
    status: str,
    error_code: str | None = None,
    action: str = "smoke",
    binding: VerifiedTelegramBinding | None = None,
    lifecycle=None,
) -> dict:
    report = {
        "schemaVersion": 2,
        "runId": run_id,
        "action": action,
        "attemptedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "syntheticOnly": True,
        "expectedBotUsername": f"@{EXPECTED_TEST_BOT_USERNAME}",
        "expectedChannelTitle": EXPECTED_TEST_CHANNEL_TITLE,
        "status": status,
        "errorCode": error_code,
    }
    if binding is not None:
        binding_payload = asdict(binding)
        binding_payload["bot_username"] = f"@{binding_payload['bot_username']}"
        report["binding"] = binding_payload
    if lifecycle is not None:
        lifecycle_payload = asdict(lifecycle)
        lifecycle_payload["binding"]["bot_username"] = (
            f"@{lifecycle_payload['binding']['bot_username']}"
        )
        report["lifecycle"] = lifecycle_payload
    return report


def _write_report(run_id: str, report: dict) -> Path:
    path = REPORT_ROOT / f"{run_id}.json"
    atomic_write_text(
        path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        # Canonical private-channel/message IDs are operational metadata rather
        # than credentials, but the local live proof still gets owner-only mode.
        mode=0o600,
    )
    return path


async def _execute_bind(token: str, chat_id: int) -> VerifiedTelegramBinding:
    # Import only after every network and credential guard has passed.
    from aiogram import Bot

    bot = Bot(token=token)
    try:
        binding = await verify_test_channel_binding(bot, chat_id)
        return binding
    finally:
        await bot.session.close()


async def _execute_smoke(
    token: str,
    trusted_binding: VerifiedTelegramBinding,
    run_id: str,
):
    # Import only after the local binding and all side-effect gates passed.
    from aiogram import Bot

    bot = Bot(token=token)
    try:
        observed_binding = await verify_test_channel_binding(
            bot, trusted_binding.chat_id
        )
        if observed_binding != trusted_binding:
            raise TelegramCapabilityError(
                "Telegram test identity differs from the trusted local binding"
            )
        return await run_synthetic_message_lifecycle(
            bot, trusted_binding, run_id=run_id
        )
    finally:
        await bot.session.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_id = f"tg-{uuid.uuid4().hex[:20]}"
    try:
        validate_live_opt_in(
            live=args.live,
            confirmation=args.confirm,
            bind_channel=args.bind_channel,
            run_smoke=args.run_smoke,
        )
        trusted_binding = (
            load_verified_binding(BINDING_DATABASE_PATH) if args.run_smoke else None
        )
        requested_chat_id = (
            requested_chat_id_from_environment() if args.bind_channel else None
        )
        token = load_allowlisted_test_bot_token()
        if args.bind_channel:
            if requested_chat_id is None:
                raise LiveTelegramGuardError(
                    "The read-only bind step requires a canonical chat ID"
                )
            binding = asyncio.run(_execute_bind(token, requested_chat_id))
            save_verified_binding(BINDING_DATABASE_PATH, binding)
            report = _safe_report(
                run_id=run_id,
                action="bind",
                status="passed",
                binding=binding,
            )
            path = _write_report(run_id, report)
            print(f"Telegram test binding verified; owner-only report: {path}")
            return 0
        if trusted_binding is None:
            raise TelegramTestBindingError("Trusted Telegram binding is unavailable")
        lifecycle = asyncio.run(_execute_smoke(token, trusted_binding, run_id))
    except (LiveTelegramGuardError, TelegramTestBindingError) as error:
        # Guard failures happen before network access and intentionally create no
        # report containing operator environment details.
        print(f"Telegram live smoke refused: {error}", file=sys.stderr)
        return 2
    except TelegramLifecycleError as error:
        report = _safe_report(
            run_id=run_id,
            status="failed",
            action="smoke",
            error_code=f"lifecycle_{error.result.failure_stage or 'unknown'}",
            lifecycle=error.result,
        )
        path = _write_report(run_id, report)
        print(
            f"Telegram synthetic lifecycle failed; safe report: {path}", file=sys.stderr
        )
        return 1
    except TelegramCapabilityError:
        report = _safe_report(
            run_id=run_id,
            status="failed",
            action="bind" if args.bind_channel else "smoke",
            error_code="capability_verification_failed",
        )
        path = _write_report(run_id, report)
        print(
            f"Telegram capability verification failed; safe report: {path}",
            file=sys.stderr,
        )
        return 1
    except Exception as error:
        # Never serialize remote error strings: they may echo request details.
        report = _safe_report(
            run_id=run_id,
            status="failed",
            action="bind" if args.bind_channel else "smoke",
            error_code=f"unexpected_{type(error).__name__}",
        )
        path = _write_report(run_id, report)
        print(f"Telegram live smoke failed; safe report: {path}", file=sys.stderr)
        return 1

    report = _safe_report(
        run_id=run_id,
        status="passed",
        action="smoke",
        lifecycle=lifecycle,
    )
    path = _write_report(run_id, report)
    print(f"Telegram synthetic lifecycle passed; safe report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

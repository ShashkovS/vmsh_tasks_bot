"""Create the one initial Staff administrator for an empty installation."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from functools import partial

from db_methods.pwa import PwaConnectionFactory
from db_methods.pwa.first_admin import (
    global_admin_exists,
    insert_first_global_admin,
)
from helpers.config import Config
from helpers.consts import USER_TYPE
from models.pwa.auth import CredentialHasher


async def ensure_first_global_admin(
    factory: PwaConnectionFactory,
    runtime_config: Config,
    credential_hasher: CredentialHasher,
) -> bool:
    """Create ``admin`` once; concurrent workers safely converge on one row."""

    admin_user_type = int(USER_TYPE.ADMIN)
    exists = await factory.run_read_async(
        partial(global_admin_exists, admin_user_type=admin_user_type)
    )
    if exists:
        return False

    password = runtime_config.first_admin_password
    if not isinstance(password, str) or not password:
        raise RuntimeError(
            "An empty database requires first_admin_password in the runtime config"
        )
    if len(password) > 512:
        raise RuntimeError(
            "first_admin_password must not exceed 512 characters"
        )

    credential_hash = await asyncio.to_thread(credential_hasher.hash, password)
    occurred_at = datetime.now(UTC).isoformat(timespec="microseconds")
    return await factory.run_write_async(
        partial(
            insert_first_global_admin,
            admin_user_type=admin_user_type,
            username="admin",
            display_name="Администратор ВМШ 179",
            user_name="Администратор",
            user_surname="ВМШ 179",
            credential_hash=credential_hash,
            audit_action="auth.first_admin.created",
            audit_after_json=json.dumps(
                {
                    "audience": "staff",
                    "username": "admin",
                    "userType": admin_user_type,
                },
                separators=(",", ":"),
            ),
            occurred_at=occurred_at,
        )
    )


__all__ = ["ensure_first_global_admin"]

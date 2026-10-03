import asyncio
import sqlite3

import pytest
from argon2 import PasswordHasher
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.first_admin import ensure_first_global_admin
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import load_auth_runtime_config
from apps.pwa_api.middleware import PWA_AUTH_STATE, PwaAuthState
from models.pwa.auth import CredentialHasher


def _fast_hasher() -> CredentialHasher:
    return CredentialHasher(
        PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    )


@pytest.mark.asyncio
async def test_empty_database_gets_one_loginable_global_admin(tmp_path):
    database_path = tmp_path / "first-admin.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    password = "synthetic-first-admin-password"

    created = await ensure_first_global_admin(
        factory,
        Config(first_admin_password=password),
        _fast_hasher(),
    )

    assert created is True
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT u.type, a.audience, a.username, a.username_normalized, "
            "a.credential_kind, a.credential_hash, a.status "
            "FROM users AS u JOIN auth_accounts AS a ON a.linked_user_id = u.id "
            "WHERE u.type = ?",
            (int(USER_TYPE.ADMIN),),
        ).fetchone()
        audit = connection.execute(
            "SELECT action, object_type, after_json FROM audit_events "
            "WHERE action = 'auth.first_admin.created'"
        ).fetchone()

    assert row[:5] == (
        int(USER_TYPE.ADMIN),
        "staff",
        "admin",
        "admin",
        "password",
    )
    assert row[6] == "active"
    assert row[5] != password
    assert _fast_hasher().verify(row[5], password).valid
    assert audit is not None
    assert password not in "".join(str(value) for value in audit)


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent_across_concurrent_workers(tmp_path):
    database_path = tmp_path / "first-admin-race.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    config = Config(first_admin_password="synthetic-concurrent-password")

    outcomes = await asyncio.gather(
        ensure_first_global_admin(factory, config, _fast_hasher()),
        ensure_first_global_admin(factory, config, _fast_hasher()),
    )

    assert sorted(outcomes) == [False, True]
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM users WHERE type = ?",
            (int(USER_TYPE.ADMIN),),
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM auth_accounts WHERE audience = 'staff' "
            "AND username_normalized = 'admin'"
        ).fetchone() == (1,)

    # Once an administrator exists, the bootstrap password may be removed.
    assert (
        await ensure_first_global_admin(factory, Config(), _fast_hasher()) is False
    )


@pytest.mark.asyncio
async def test_empty_database_without_bootstrap_password_fails_closed(tmp_path):
    database_path = tmp_path / "first-admin-missing-password.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)

    with pytest.raises(RuntimeError, match="first_admin_password"):
        await ensure_first_global_admin(factory, Config(), _fast_hasher())

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM users WHERE type = ?",
            (int(USER_TYPE.ADMIN),),
        ).fetchone() == (0,)


@pytest.mark.asyncio
async def test_auth_startup_runs_first_admin_bootstrap(tmp_path, monkeypatch):
    database_path = tmp_path / "first-admin-startup.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    runtime = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="first-admin-startup",
        pwa_prototype=True,
        first_admin_password="synthetic-startup-password",
    )
    app = web.Application()
    app[RUNTIME_CONFIG] = runtime
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    app[PWA_AUTH_STATE] = PwaAuthState(
        runtime_config=load_auth_runtime_config(runtime, environment={})
    )
    monkeypatch.setattr(pwa_app, "CredentialHasher", _fast_hasher)

    await pwa_app.on_auth_startup(app)

    assert app[PWA_AUTH_STATE].service is not None
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM users WHERE type = ?",
            (int(USER_TYPE.ADMIN),),
        ).fetchone() == (1,)

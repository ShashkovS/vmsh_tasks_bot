# -*- coding: utf-8 -*-
import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Protocol

from aiohttp import web

import apps
from db_methods.pwa import (
    ProductAnalyticsConnectionFactory,
    PwaConnectionFactory,
    runtime_database_lock,
)
from db_methods.pwa.product_analytics import prune_expired_events
from helpers.config import DATABASE_MUTABLE_CONFIG_FIELDS, Config, config, logger
import db_methods as db
from helpers.features import set_features
from helpers.msg_texts import msgs
from helpers.prometheus_metrics import configure_prometheus
from helpers.pwa.app_keys import (
    ENABLED_ADAPTERS,
    PWA_DATABASE,
    PWA_ANALYTICS_DATABASE,
    RUNTIME_CONFIG,
    PwaDatabaseState,
    PwaAnalyticsDatabaseState,
)
from helpers.shutdown import wait_for_valuable_tasks
from helpers.trace import init_trace

LOCAL_APP_PORT = int(os.environ.get("VMSH_API_PORT", "8179"))


class AppAdapter(Protocol):
    """Structural boundary implemented by both Python modules and test adapters."""

    def configure(self, app: web.Application) -> None: ...


async def pwa_database_lifecycle(app: web.Application):
    """Hold the database pathname lock until aiohttp has drained handlers."""

    runtime_config = app[RUNTIME_CONFIG]
    if not runtime_config.runtime_profile.startswith("pwa-"):
        yield
        return

    state = app[PWA_DATABASE]
    lifecycle_lock = runtime_database_lock(runtime_config.db_filename)
    # The non-blocking flock is acquired synchronously so cancellation cannot
    # lose its descriptor. SQLite preflight stays off the event loop; if startup
    # is cancelled, a done callback releases the lock only after that worker
    # thread has closed every SQLite connection. See ADR 0002.
    lifecycle_lock.acquire()
    preflight_task = asyncio.create_task(
        asyncio.to_thread(PwaConnectionFactory, runtime_config.db_filename)
    )
    try:
        factory = await asyncio.shield(preflight_task)
    except BaseException:
        if preflight_task.done():
            lifecycle_lock.release()
        else:
            def release_when_preflight_finishes(completed_task):
                # Retrieve a delayed exception so cancellation does not create
                # an unobserved-task warning; keep the lock until the worker
                # has closed every SQLite descriptor.
                with suppress(BaseException):
                    completed_task.result()
                lifecycle_lock.release()

            preflight_task.add_done_callback(release_when_preflight_finishes)
        raise

    state.lifecycle_lock = lifecycle_lock
    state.factory = factory
    try:
        yield
    finally:
        state.factory = None
        state.lifecycle_lock = None
        lifecycle_lock.release()


async def pwa_analytics_lifecycle(app: web.Application):
    """Prepare and retain the independent best-effort analytics store."""

    runtime_config = app[RUNTIME_CONFIG]
    if not runtime_config.runtime_profile.startswith("pwa-"):
        yield
        return
    state = app[PWA_ANALYTICS_DATABASE]
    analytics_path = runtime_config.pwa_analytics_db_filename or str(
        Path(runtime_config.db_filename).with_name("analytics.sqlite3")
    )
    lifecycle_lock = runtime_database_lock(analytics_path)
    try:
        lifecycle_lock.acquire()
        factory = await asyncio.to_thread(
            ProductAnalyticsConnectionFactory,
            analytics_path,
        )
        # Retention is enforced both here and by the lightweight daily task in
        # the PWA adapter; failure is intentionally isolated from core startup.
        await factory.run_write_async(
            lambda connection: prune_expired_events(connection, now=datetime.now(UTC))
        )
    except asyncio.CancelledError:
        lifecycle_lock.release()
        raise
    except Exception:
        # Telemetry is explicitly fail-open: a disk or maintenance issue must
        # not take the Student, Family or Staff application down.
        logger.warning("Product analytics startup unavailable", exc_info=True)
        with suppress(Exception):
            lifecycle_lock.release()
        yield
        return
    state.lifecycle_lock = lifecycle_lock
    state.factory = factory

    async def prune_daily() -> None:
        while True:
            await asyncio.sleep(24 * 60 * 60)
            try:
                await factory.run_write_async(
                    lambda connection: prune_expired_events(
                        connection, now=datetime.now(UTC)
                    )
                )
            except Exception:
                # Product telemetry is never allowed to affect PWA availability.
                logger.warning("Daily product analytics cleanup failed", exc_info=True)

    cleanup_task = asyncio.create_task(prune_daily())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        state.factory = None
        state.lifecycle_lock = None
        lifecycle_lock.release()


async def on_startup(app):
    logger.warning("MainApp Start up!")
    runtime_config = app[RUNTIME_CONFIG]
    if runtime_config.runtime_profile.startswith("pwa-"):
        # The cleanup context above owns schema preflight and the shared lock;
        # ordinary startup never applies migrations. See ADR 0002.
        return

    # Legacy startup keeps its historical auto-migration path until the
    # Telegram cutover has its own rehearsal and rollback proof.
    db.sql.setup(runtime_config.db_filename)
    bot_settings = db.settings.get_settings()
    runtime_config.update_from_dict(
        bot_settings,
        allowed_fields=DATABASE_MUTABLE_CONFIG_FIELDS,
    )
    init_trace(runtime_config)
    set_features(runtime_config)
    ui_messages = db.settings.get_ui_messages()
    msgs.update_from_dict(ui_messages)


async def on_shutdown(app):
    """
    Graceful shutdown. This method is recommended by aiohttp docs.
    """
    logger.warning("on_shutdown")
    logger.warning("MainApp Shutting down..")
    await wait_for_valuable_tasks(logger, timeout=20)
    # Останавливаем sympy-воркера (если он был запущен)
    runtime_config = app[RUNTIME_CONFIG]
    if runtime_config.runtime_profile == "legacy":
        from helpers.checkers import worker

        worker.shutdown()
    db.sql.disconnect()
    logger.warning("MainApp Bye!")


def create_app(
    enabled_apps: Iterable[AppAdapter] | None = None,
    *,
    runtime_config: Config | None = None,
):
    """Compose aiohttp from an explicit adapter list and runtime config."""

    selected_adapters = tuple(apps.all_apps if enabled_apps is None else enabled_apps)
    selected_config = runtime_config or config
    app = web.Application()
    # Installed before adapters append their middleware, so application-level
    # metrics observe their responses and failures without changing semantics.
    configure_prometheus(app)
    app[RUNTIME_CONFIG] = selected_config
    app[ENABLED_ADAPTERS] = selected_adapters
    app[PWA_DATABASE] = PwaDatabaseState()
    app[PWA_ANALYTICS_DATABASE] = PwaAnalyticsDatabaseState()
    # aiohttp runs cleanup contexts after on_shutdown and request draining.
    # Keeping the DB lifecycle lock here prevents maintenance from replacing
    # SQLite while a graceful-shutdown handler still owns a connection.
    app.cleanup_ctx.append(pwa_database_lifecycle)
    app.cleanup_ctx.append(pwa_analytics_lifecycle)
    # Важно, что текущие on_startup и on_shutdown первые. Мы потом развернём список on_shutdown в обратном порядке
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    # Теперь настраиваем все модули
    for module in selected_adapters:
        module.configure(app)
    # Обращаем on_shutdown, чтобы приложения закрывались в правильном порядке
    app.on_shutdown[:] = app.on_shutdown[::-1]
    if __name__ != "__main__":
        if hasattr(apps, "tg_bot") and apps.tg_bot in selected_adapters:
            apps.tg_bot.setup_tgbot_webhook(app)

    return app


prepare_app = create_app
app = create_app()
if __name__ == "__main__":
    # Start aiohttp server
    async def dev_main():
        telegram_enabled = hasattr(apps, "tg_bot")
        if telegram_enabled:
            apps.tg_bot.start_bot_in_polling_mode()

        runner = web.AppRunner(app)
        polling_task = None
        try:
            await runner.setup()
            site = web.TCPSite(runner, host="127.0.0.1", port=LOCAL_APP_PORT)
            await site.start()
            logger.info(f"Веб-сервер запущен на порту {LOCAL_APP_PORT}")

            polling_task = (
                asyncio.create_task(apps.tg_bot.run_tg_bot_in_polling_mode())
                if telegram_enabled
                else None
            )
            await asyncio.Event().wait()
        finally:
            if polling_task is not None:
                polling_task.cancel()
                with suppress(asyncio.CancelledError):
                    await polling_task
            await runner.cleanup()

    try:
        asyncio.run(dev_main())
    except KeyboardInterrupt:
        pass
else:
    # Приложение будет запущено gunicorn'ом, который и будет следить за его жизнеспособностью
    # Ну всё, можно делать заключительные приготовления
    pass

"""Optional legacy adapters: docs/optional-telegram-bot.md."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from unittest.mock import Mock

import pytest

from helpers import config as config_module
from helpers.loader_from_google_spreadsheets import GoogleSheetsDisabled, SpreadsheetLoader
from models import spreadsheets


@pytest.mark.parametrize("production", [False, True])
@pytest.mark.parametrize("telegram_enabled", [False, True])
@pytest.mark.parametrize("google_enabled", [False, True])
def test_config_requires_google_credentials_only_with_sheet_key(
    tmp_path, monkeypatch, production, telegram_enabled, google_enabled
):
    monkeypatch.delenv("VMSH_RUNTIME_PROFILE", raising=False)
    monkeypatch.setenv("PROD", "true" if production else "false")
    monkeypatch.setattr(config_module, "_absolute_path", lambda path: tmp_path / path)
    profile = "prod" if production else "test"
    credentials_directory = tmp_path / f"creds_{profile}"
    credentials_directory.mkdir()
    (credentials_directory / f"vmsh_bot_config_{profile}.json").write_text(
        json.dumps({
            "config_name": "optional-integration-test",
            "db_filename": "isolated.sqlite3",
            "telegram_bot_token": "123456:synthetic" if telegram_enabled else "",
            "google_sheets_key": "synthetic-sheet" if google_enabled else "",
        }),
        encoding="utf-8",
    )

    if google_enabled:
        # Configured Sheets imports retain the missing-credentials error.
        with pytest.raises(FileNotFoundError):
            config_module._setup()
        (credentials_directory / f"vmsh_bot_sheets_creds_{profile}.json").write_text(
            json.dumps({"client_email": "synthetic@example.invalid"}),
            encoding="utf-8",
        )

    runtime = config_module._setup()
    assert bool(runtime.telegram_bot_token) == telegram_enabled
    assert bool(runtime.google_sheets_key) == google_enabled
    assert runtime.production_mode == production


@pytest.mark.parametrize("method", [
    "update_all", "update_problems", "update_students", "update_teachers",
    "update_ui_messages", "update_bot_settings", "update_groups",
])
def test_disabled_google_imports_never_read_or_write(monkeypatch, method):
    monkeypatch.setattr(spreadsheets.config, "google_sheets_key", "")
    monkeypatch.setattr(spreadsheets.config, "allow_google_update_all", True)
    loader = Mock()
    monkeypatch.setattr(spreadsheets, "google_spreadsheet_loader", loader)
    with pytest.raises(GoogleSheetsDisabled):
        getattr(spreadsheets.FromGoogleSpreadsheet, method)()
    assert loader.mock_calls == []


def test_disabled_google_bootstrap_does_not_access_database(monkeypatch):
    monkeypatch.setattr(spreadsheets.config, "google_sheets_key", "")
    teachers = Mock(side_effect=AssertionError("disabled bootstrap accessed DB"))
    monkeypatch.setattr(spreadsheets.User, "all_teachers", teachers)
    spreadsheets.update_from_google_if_db_is_empty()
    teachers.assert_not_called()


def test_unconfigured_loader_refuses_access_before_importing_google(monkeypatch):
    monkeypatch.setitem(sys.modules, "gspread", None)
    with pytest.raises(GoogleSheetsDisabled):
        SpreadsheetLoader(sheets_key="").get_all_from_spreadsheet()


def _isolated_python(source, *arguments):
    environment = os.environ.copy()
    environment["VMSH_RUNTIME_PROFILE"] = "telegram-history-test"
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), *map(str, arguments)],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_empty_token_keeps_other_legacy_apps_startable(tmp_path):
    _isolated_python("""
        import asyncio
        import sys
        from unittest.mock import AsyncMock
        from helpers.config import config
        config.runtime_profile = 'legacy'
        config.telegram_bot_token = ''
        config.db_filename = sys.argv[1]
        config.apps = 'tg_bot, game_web_app, results_app, zoom_events_parser, apis_app'

        import main
        from helpers.bot import bot, dispatcher
        assert bot is None
        assert 'apps.tg_bot' not in sys.modules
        assert 'handlers' not in sys.modules
        assert {adapter.__name__ for adapter in main.app[main.ENABLED_ADAPTERS]} == {
            'apps.game_web_app', 'apps.results_app',
            'apps.zoom_events_parser', 'apps.apis_app',
        }
        assert not any(handler.callback.__module__ == 'apps.tg_bot'
            for event in (dispatcher.startup, dispatcher.shutdown)
            for handler in event.handlers)

        # The legacy game broker is unrelated to the optional integrations.
        broker = main.apps.game_web_app.vmsh_nats
        broker.setup = AsyncMock()
        broker.subscribe = AsyncMock()
        broker.disconnect = AsyncMock()

        async def check():
            runner = main.web.AppRunner(main.app)
            await runner.setup()
            await runner.cleanup()
        asyncio.run(check())
    """, tmp_path / "legacy.sqlite3")


def test_omitting_telegram_adapter_skips_it_with_configured_token():
    _isolated_python("""
        import sys
        from helpers.config import config
        config.apps = 'zoom_events_parser'
        assert config.telegram_bot_token
        import main
        assert [adapter.__name__ for adapter in main.app[main.ENABLED_ADAPTERS]] == [
            'apps.zoom_events_parser',
        ]
        assert 'apps.tg_bot' not in sys.modules
        assert 'helpers.bot' not in sys.modules
        assert 'handlers' not in sys.modules
    """)


def test_bot_startup_and_import_command_filters_without_google_key(tmp_path):
    _isolated_python("""
        import asyncio
        import sys
        from datetime import datetime, UTC
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from helpers.config import config
        config.db_filename = sys.argv[1]
        config.apps = 'tg_bot'

        import apps
        from helpers.bot import bot, router
        from aiogram.types import Message, Chat
        from handlers import admin_handlers
        assert bot is not None
        assert apps.all_apps == [apps.tg_bot]
        assert config.google_sheets_key == ''
        apps.tg_bot.google_spreadsheet_loader.setup = Mock()
        apps.tg_bot.register_group_switch_commands = Mock()
        bot.get_me = AsyncMock(return_value=SimpleNamespace(username='synthetic_bot'))
        bot.post_logging_message = AsyncMock()

        async def check():
            await apps.tg_bot.on_startup(bot)
            apps.tg_bot.google_spreadsheet_loader.setup.assert_not_called()
            bot.get_me.assert_awaited_once()
            for command, function in (
                ('update_all', 'update_all_internal_data'),
                ('ut', 'update_teachers'), ('us', 'update_students'),
                ('update_bot_settings', 'update_bot_settings'),
                ('update_ui_messages', 'update_ui_messages'),
                ('up', 'update_problems'), ('ug', 'update_groups'),
            ):
                handler = next(item for item in router.message.handlers
                    if item.callback is getattr(admin_handlers, function))
                message = Message(message_id=1, date=datetime.now(UTC),
                    chat=Chat(id=1, type='private'), text='/' + command)
                config.google_sheets_key = ''
                accepted, _ = await handler.check(message, bot=bot)
                assert not accepted, command
                config.google_sheets_key = 'synthetic-sheet'
                accepted, _ = await handler.check(message, bot=bot)
                assert accepted, command
            apps.tg_bot.db.sql.disconnect()
        asyncio.run(check())
    """, tmp_path / "telegram.sqlite3")

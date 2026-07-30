# -*- coding: utf-8 -*-
import logging
import os
import json
import pathlib
from dataclasses import dataclass, field
from typing import Union, Optional, ContextManager

APP_LOGGER = "MathBot"
APP_PATH = pathlib.Path(__file__).parent.parent.resolve()
sentry_sdk: ContextManager = None
os.chdir(APP_PATH)

__all__ = ["APP_PATH", "logger", "config", "DEBUG", "sentry_sdk"]


def _absolute_path(path: str) -> pathlib.Path:
    path_obj = pathlib.Path(path)
    if path_obj.is_absolute():
        return path_obj
    else:
        # Используем путь от корня проекта
        return APP_PATH / path


DATABASE_MUTABLE_CONFIG_FIELDS = frozenset(
    {
        "game_mode",
        "prev_problems_mode",
        "rate_limit",
        "reg_mode",
        "result_mode",
        "save_sol_mode",
        "verdict_mode",
    }
)


def _optional_executable_from_env(name: str, default: str) -> Optional[str]:
    """Read an executable override without accepting a shell command fallback."""

    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    value = raw_value.strip()
    if not value or value.casefold() in {"none", "disabled"}:
        return None
    return value


@dataclass()
class Config:
    runtime_profile: str = "legacy"
    pwa_instance: str = ""
    pwa_media_root: str = ""
    pwa_prototype: bool = False
    config_name: str = ""
    google_sheets_key: str = ""
    google_cred_json: str = field(default="", repr=False)
    telegram_bot_token: str = field(default="", repr=False)
    webhook_host: str = ""
    webhook_path: str = ""
    webhook_port: int = -1
    production_mode: bool = False
    db_filename: str = ""
    sos_channel: Union[str, int] = ""
    exceptions_channel: Union[str, int] = ""
    sentry_dsn: Optional[str] = field(default="", repr=False)
    sentry_release: str = ""
    nats_server: Optional[str] = "nats://127.0.0.1:4222"
    pwa_vapid_public_key: str = ""
    pwa_vapid_private_key: str = field(default="", repr=False)
    pwa_vapid_subject: str = ""
    logging_level = logging.WARNING
    verdict_mode: str = "verdict_plus_minus_half"
    result_mode: str = "res_immed"
    save_sol_mode: str = "save_sol_in_tg_only"
    prev_problems_mode: str = "prev_problems_hide"
    game_mode: str = "game_hide"
    reg_mode: str = "reg_needed"
    rate_limit: str = "rate_limit_3_and_6"
    apps: str = "tg_bot, game_web_app, results_app, apis_app, zoom_events_parser"
    set_admin_secret: str = field(default="", repr=False)
    zoom_secret_token: str = field(default="", repr=False)
    conduit_import_api_token: str = field(default="", repr=False)
    synonyms_mode: str = "synonyms_join"
    trace_enabled: bool = False
    trace_log_path: str = "logs/events.jsonl"
    trace_backup_days: int = 21
    # s3 bucket
    s3_url: Optional[str] = "https://s3.ru1.storage.beget.cloud"
    s3_bucket_name: Optional[str] = None
    s3_access_key: Optional[str] = field(default=None, repr=False)
    s3_secret_key: Optional[str] = field(default=None, repr=False)
    # See vmshpwa/docs/latex-content-pipeline.md. These are executable paths,
    # never shell fragments; the worker supplies every argument itself.
    pdf2svg_path: Optional[str] = "pdf2svg"
    cwebp_path: Optional[str] = "cwebp"
    pdflatex_path: Optional[str] = "pdflatex"
    magick_path: Optional[str] = "magick"

    def update_from_dict(self, update_dict: dict, *, allowed_fields=None):
        for key, value in update_dict.items():
            if allowed_fields is not None and key not in allowed_fields:
                raise ValueError(
                    f"Runtime database cannot override config field {key!r}"
                )
            setattr(self, key, value)


def _create_logger():
    # Настраиваем
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)-8s: %(levelname)-8s %(message)s",
        datefmt="%Y-%d-%m %H:%M:%S",
    )
    logger = logging.getLogger(APP_LOGGER)
    return logger


def _setup(*, force_production=False):
    runtime_profile = os.environ.get("VMSH_RUNTIME_PROFILE", "").strip()
    if runtime_profile == "telegram-history-test":
        # Historical handler scenarios need aiogram to accept a token-shaped
        # value, but must never load credentials or contact Telegram/Google.
        return Config(
            runtime_profile=runtime_profile,
            config_name="telegram_history_test",
            db_filename=str(
                _absolute_path(".runtime/vmshpwa/telegram_history.sqlite3")
            ),
            pwa_media_root=str(_absolute_path(".runtime/vmshpwa/telegram_history")),
            apps="",
            google_sheets_key="",
            google_cred_json="",
            telegram_bot_token="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            nats_server=None,
            trace_enabled=False,
            sentry_dsn="",
        )
    if runtime_profile.startswith("pwa-"):
        production_mode = (
            force_production
            or os.environ.get("PROD") == "true"
            or runtime_profile == "pwa-production"
        )
        pwa_prototype = os.environ.get("VMSH_PWA_PROTOTYPE", "false").lower() == "true"
        if production_mode and pwa_prototype:
            raise RuntimeError(
                "Production PWA runtime cannot enable VMSH_PWA_PROTOTYPE"
            )
        config = Config(
            runtime_profile=runtime_profile,
            pwa_instance=os.environ.get(
                "VMSH_INSTANCE", runtime_profile.removeprefix("pwa-")
            ),
            pwa_prototype=pwa_prototype,
            production_mode=production_mode,
            config_name=os.environ.get(
                "VMSH_NATS_TOPIC_PREFIX", runtime_profile.replace("-", "_")
            ),
            db_filename=str(
                _absolute_path(
                    os.environ.get("VMSH_DB_FILENAME", f"db/{runtime_profile}.sqlite3")
                )
            ),
            pwa_media_root=str(
                _absolute_path(
                    os.environ.get(
                        "VMSH_MEDIA_ROOT", f".runtime/vmshpwa/{runtime_profile}"
                    )
                )
            ),
            apps="pwa_app",
            google_sheets_key="",
            google_cred_json="",
            telegram_bot_token="",
            nats_server=os.environ.get("VMSH_NATS_SERVER") or None,
            trace_enabled=False,
            sentry_dsn=os.environ.get("VMSH_SENTRY_DSN", "").strip(),
            sentry_release=os.environ.get("VMSH_SENTRY_RELEASE", "").strip(),
            pwa_vapid_public_key=os.environ.get("VMSH_VAPID_PUBLIC_KEY", "").strip(),
            pwa_vapid_private_key=os.environ.get("VMSH_VAPID_PRIVATE_KEY", "").strip(),
            pwa_vapid_subject=os.environ.get("VMSH_VAPID_SUBJECT", "").strip(),
            pdf2svg_path=_optional_executable_from_env("VMSH_PDF2SVG_PATH", "pdf2svg"),
            cwebp_path=_optional_executable_from_env("VMSH_CWEBP_PATH", "cwebp"),
            pdflatex_path=_optional_executable_from_env(
                "VMSH_PDFLATEX_PATH", "pdflatex"
            ),
            magick_path=_optional_executable_from_env("VMSH_MAGICK_PATH", "magick"),
        )
        logger.info(
            "PWA runtime profile %s uses DB %s", runtime_profile, config.db_filename
        )
        return config

    config = Config()
    logging.info(f"Current working dir: {os.getcwd()}")
    if force_production or os.environ.get("PROD", None) == "true":
        logger.info("Настройки в режиме PRODUCTION!!!")
        config.production_mode = True
        config_filename = _absolute_path("creds_prod/vmsh_bot_config_prod.json")
        config.google_cred_json = _absolute_path(
            "creds_prod/vmsh_bot_sheets_creds_prod.json"
        )
    else:
        logging.info("Настройки в режиме test")
        config.production_mode = False
        config_filename = _absolute_path("creds_test/vmsh_bot_config_test.json")
        config.google_cred_json = _absolute_path(
            "creds_test/vmsh_bot_sheets_creds_test.json"
        )

    try:
        with open(config.google_cred_json, "r") as f:
            cred = json.load(f)
        logging.info(f"Google service email: {cred['client_email']}")
    except:
        logging.critical(f"Запишите гугл-креды в {config.google_cred_json}")
        raise

    try:
        with open(config_filename, "r") as f:
            config_from_json = json.load(f)
    except:
        logging.critical(
            f"Запишите конфиг в {config_filename} в формате\n"
            '`{"telegram_bot_token": "...", "google_sheets_key": "...", "webhook_host": "host.ru", "webhook_port": 443, "db_filename": "test.db"}`'
        )
        raise

    # Определяем абсолютный путь к БД
    config_from_json["db_filename"] = _absolute_path(config_from_json["db_filename"])

    # Обновляем настройки
    config.update_from_dict(config_from_json)
    assert config.config_name != "", (
        f"{config.config_name=}, but needs to be meanfull string"
    )
    return config


def _init_sentry(dsn: str, environment: str, release: str = ""):
    # Добавляем отправку в sentry, если задан ключи
    global sentry_sdk
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.aiohttp import AioHttpIntegration
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            from helpers.pwa.sentry_safety import (
                sanitize_sentry_breadcrumb,
                sanitize_sentry_event,
            )

            logging_integration = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            )
            sentry_sdk.init(
                dsn=dsn,
                integrations=[
                    AioHttpIntegration(),
                    AsyncioIntegration(),
                    logging_integration,
                ],
                traces_sample_rate=1.0,
                environment=environment,
                release=release or None,
                send_default_pii=False,
                before_send=sanitize_sentry_event,
                before_send_transaction=sanitize_sentry_event,
                before_breadcrumb=sanitize_sentry_breadcrumb,
            )
            logging.info("Sentry started")

        except Exception:
            logging.exception("Sentry init failed")
    else:
        sentry_sdk = None


logger = _create_logger()
DEBUG = logging.DEBUG
config = _setup()
_init_sentry(config.sentry_dsn, config.config_name, config.sentry_release)
from helpers.trace import init_trace  # noqa: E402

init_trace(config)
# logger.debug(f'{config=}')

if config.production_mode:
    logger.info(("*" * 50 + "\n") * 5)
    logger.info("Production mode")
    logger.info("*" * 50)
else:
    logger.info("Dev mode")

if __name__ == "__main__":
    print(config)
    print("-" * 50)
    # Тестируем sentry
    if config.sentry_dsn:
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warn message")
        logger.error("error message")
        try:
            a = [1][2]
        except Exception:
            logger.exception("exception message")
        # Наконец-то валимся
        division_by_zero = 1 / 0

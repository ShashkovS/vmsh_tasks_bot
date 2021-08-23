# -*- coding: utf-8 -*-
import logging
import os
import json
from dataclasses import dataclass
from typing import Union, Optional

APP_LOGGER = 'MathBot'


@dataclass()
class Config:
    config_name: str = ''
    dump_filename: str = ''
    google_sheets_key: str = ''
    google_cred_json: str = ''
    telegram_bot_token: str = ''
    webhook_host: str = ''
    webhook_port: int = -1
    production_mode: bool = False
    db_filename: str = ''
    sos_channel: Union[str, int] = ''
    exceptions_channel: Union[str, int] = ''
    sentry_dsn: Optional[str] = ''


def _create_logger():
    # Настраиваем
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(name)-8s: %(levelname)-8s %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    logger = logging.getLogger(APP_LOGGER)
    return logger


def _setup(*, force_production=False):
    config = Config()
    logging.info(f'Current working dir: {os.getcwd()}')
    if force_production or os.environ.get('PROD', None) == 'true':
        logger.info('Настройки в режиме PRODUCTION!!!')
        config.production_mode = True
        config_filename = 'creds_prod/vmsh_bot_config_prod.json'
        config.google_cred_json = 'creds_prod/vmsh_bot_sheets_creds_prod.json'
    else:
        logging.info('Настройки в режиме test')
        config.production_mode = False
        config_filename = 'creds_test/vmsh_bot_config_test.json'
        config.google_cred_json = 'creds_test/vmsh_bot_sheets_creds_test.json'

    try:
        with open(config.google_cred_json, 'r') as f:
            cred = json.load(f)
        logging.info(f'Google service email: {cred["client_email"]}')
    except:
        logging.critical(f'Запишите гугл-креды в {config.google_cred_json}')
        raise

    try:
        with open(config_filename, 'r') as f:
            config_from_json = json.load(f)
    except:
        logging.critical(f'Запишите конфиг в {config_filename} в формате\n'
                         '`{"telegram_bot_token": "...", "google_sheets_key": "...", "webhook_host": "host.ru", "webhook_port": 443, "dump_filename": "_google_data_prod.pickle", "db_filename": "test.db"}`')
        raise
    config.__dict__.update(config_from_json)
    return config


def _init_sentry(dsn: str, environment: str):
    # Добавляем отправку в sentry, если задан ключи
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.aiohttp import AioHttpIntegration
            sentry_sdk.init(
                dsn=dsn,
                integrations=[AioHttpIntegration()],
                traces_sample_rate=1.0,
                environment=environment
            )
            logging.info('Sentry started')

        except:
            pass


logger = _create_logger()
DEBUG = logging.DEBUG
config = _setup()
_init_sentry(config.sentry_dsn, config.config_name)
logger.debug(f'{config=}')

if config.production_mode:
    logger.info(('*' * 50 + '\n') * 5)
    logger.info('Production mode')
    logger.info('*' * 50)
else:
    logger.info('Dev mode')

# if __name__ == '__main__':
#     # Только тестирование настроек sentry
#     print(config)
#     print('-' * 50)
#     logger.debug('debug message')
#     logger.info('info message')
#     logger.warning('warn message')
#     logger.error('error message')
#     try:
#         a = [1][2]
#     except:
#         logger.exception('exception message')
#     # Наконец-то валимся
#     division_by_zero = 1 / 0

# -*- coding: utf-8 -*-
import logging
import os
import json

logging.basicConfig(level=logging.INFO)
logging.info(f'Current working dir: {os.getcwd()}')

dump_filename = None
google_sheets_key = None
google_cred_json = None
telegram_bot_token = None
webhook_host = None
webhook_port = None
production_mode = False
db_filename = None
sos_channel = None
exceptions_channel = None


def _setup(*, force_production=False):
    global dump_filename, db_filename, google_sheets_key, google_cred_json, telegram_bot_token, webhook_host, webhook_port, production_mode, sos_channel
    global exceptions_channel

    if force_production or os.environ.get('PROD', None) == 'true':
        logging.info('Настройки в режиме PRODUCTION!!!')
        production_mode = True
        config_filename = 'creds_prod/vmsh_bot_config_prod.json'
        google_cred_json = 'creds_prod/vmsh_bot_sheets_creds_prod.json'
    else:
        logging.info('Настройки в режиме test')
        production_mode = False
        config_filename = 'creds_test/vmsh_bot_config_test.json'
        google_cred_json = 'creds_test/vmsh_bot_sheets_creds_test.json'

    try:
        with open(google_cred_json, 'r') as f:
            cred = json.load(f)
        logging.info(f'Google service email: {cred["client_email"]}')
    except:
        logging.critical(f'Запишите гугл-креды в {google_cred_json}')
        raise

    try:
        with open(config_filename, 'r') as f:
            config = json.load(f)
        telegram_bot_token = config["telegram_bot_token"]
        google_sheets_key = config["google_sheets_key"]
        webhook_host = config["webhook_host"]
        webhook_port = config["webhook_port"]
        dump_filename = config["dump_filename"]
        db_filename = config["db_filename"]
        sos_channel = config["sos_channel"]
        exceptions_channel = config["exceptions_channel"]
    except:
        logging.critical(f'Запишите конфиг в {config_filename} в формате\n'
                         '`{"telegram_bot_token": "...", "google_sheets_key": "...", "webhook_host": "host.ru", "webhook_port": 443, "dump_filename": "_google_data_prod.pickle", "db_filename": "test.db"}`')
        raise


_setup()

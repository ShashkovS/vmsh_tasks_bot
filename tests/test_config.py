# -*- coding: utf-8 -*-
from unittest import TestCase

import importlib
import os

os.chdir('..')
os.environ['PROD'] = 'no,test'
import config


class SecretsModuleAttributesTest(TestCase):
    def test_secrets(self):
        os.environ['PROD'] = 'false'
        del os.environ['PROD']
        importlib.reload(config)
        telegram_bot_token_prod = config.telegram_bot_token
        db_prod = config.db_filename
        self.assertIsNotNone(config.dump_filename)
        self.assertIsNotNone(config.google_sheets_key)
        self.assertIsNotNone(config.google_cred_json)
        self.assertIsNotNone(config.telegram_bot_token)
        self.assertIsNotNone(config.webhook_host)
        self.assertIsNotNone(config.webhook_port)
        self.assertIsNotNone(config.production_mode)
        self.assertIsNotNone(config.db_filename)

        os.environ['PROD'] = 'true'
        importlib.reload(config)
        telegram_bot_token_test = config.telegram_bot_token
        db_test = config.db_filename
        self.assertIsNotNone(config.dump_filename)
        self.assertIsNotNone(config.google_sheets_key)
        self.assertIsNotNone(config.google_cred_json)
        self.assertIsNotNone(config.telegram_bot_token)
        self.assertIsNotNone(config.webhook_host)
        self.assertIsNotNone(config.webhook_port)
        self.assertIsNotNone(config.production_mode)
        self.assertIsNotNone(config.db_filename)

        self.assertNotEqual(telegram_bot_token_test, telegram_bot_token_prod)
        self.assertNotEqual(db_prod, db_test)

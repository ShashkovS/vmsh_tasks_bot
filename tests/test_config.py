# -*- coding: utf-8 -*-
from unittest import TestCase

import importlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ['PROD'] = 'no,test'
from helpers import config


class SecretsModuleAttributesTest(TestCase):
    def test_secrets(self):
        os.environ['PROD'] = 'false'
        del os.environ['PROD']
        importlib.reload(config)
        telegram_bot_token_prod = config.config.telegram_bot_token
        db_prod = config.config.db_filename
        self.assertEqual(config.config.production_mode, False)
        self.assertIsNotNone(config.config.google_sheets_key)
        self.assertIsNotNone(config.config.google_cred_json)
        self.assertIsNotNone(config.config.telegram_bot_token)
        self.assertIsNotNone(config.config.webhook_host)
        self.assertIsNotNone(config.config.webhook_port)
        self.assertIsNotNone(config.config.db_filename)

        os.environ['PROD'] = 'true'
        prod_config = ROOT / 'creds_prod' / 'vmsh_bot_config_prod.json'
        if not prod_config.exists() or prod_config.stat().st_size == 0:
            self.skipTest("Production config is missing or empty.")
        importlib.reload(config)
        telegram_bot_token_test = config.config.telegram_bot_token
        db_test = config.config.db_filename
        self.assertEqual(config.config.production_mode, True)
        self.assertIsNotNone(config.config.google_sheets_key)
        self.assertIsNotNone(config.config.google_cred_json)
        self.assertIsNotNone(config.config.telegram_bot_token)
        self.assertIsNotNone(config.config.webhook_host)
        self.assertIsNotNone(config.config.webhook_port)
        self.assertIsNotNone(config.config.db_filename)

        self.assertNotEqual(telegram_bot_token_test, telegram_bot_token_prod)
        self.assertNotEqual(db_prod, db_test)

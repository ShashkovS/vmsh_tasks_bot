# -*- coding: utf-8 -*-
"""Legacy secret-profile checks run outside the shared adapter interpreter."""

import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class SecretsModuleAttributesTest(TestCase):
    def test_secrets(self):
        prod_config = ROOT / "creds_prod" / "vmsh_bot_config_prod.json"
        if not prod_config.exists() or prod_config.stat().st_size == 0:
            self.skipTest("Production config is missing or empty.")
        # Reloading helpers.config in the pytest worker leaks PROD and changes
        # imported Config/object identities in later PWA tests. Keep the real
        # historical checks in their own process (testing-strategy.md).
        environment = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith("VMSH_") and name != "PROD"
        }
        script = """
import importlib
import os
from helpers import config

def verify(production):
    assert config.config.production_mode is production
    for field in ('google_sheets_key', 'google_cred_json', 'telegram_bot_token',
                  'webhook_host', 'webhook_port', 'db_filename'):
        assert getattr(config.config, field) is not None, field
    return config.config.telegram_bot_token, config.config.db_filename

verify(False)
test_token, test_db = config.config.telegram_bot_token, config.config.db_filename
os.environ['PROD'] = 'true'
importlib.reload(config)
prod_token, prod_db = verify(True)
assert test_token != prod_token
assert test_db != prod_db
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

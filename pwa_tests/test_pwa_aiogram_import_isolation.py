"""Regression guard for the production PWA import boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_pwa_application_import_does_not_load_aiogram():
    probe = """
import json
import sys
import apps.pwa_app
print(json.dumps(sorted(name for name in sys.modules if name.startswith('aiogram'))))
"""
    environment = os.environ.copy()
    environment.update(
        {
            "VMSH_RUNTIME_PROFILE": "pwa-agent",
            "VMSH_PWA_PROTOTYPE": "false",
            "VMSH_NATS_SERVER": "",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == []

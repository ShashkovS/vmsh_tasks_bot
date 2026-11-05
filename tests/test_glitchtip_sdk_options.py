"""Backend error transport must not serialize handler locals or extra telemetry."""
import os
import subprocess
import sys


def test_backend_sdk_keeps_private_locals_and_traces_out_of_glitchtip():
    script = '''
import sentry_sdk
from helpers.config import _init_sentry
captured={}
sentry_sdk.init=lambda **kwargs: captured.update(kwargs)
_init_sentry('https://public@glitch.leaders.tech/2','deployment-check','release-1')
assert captured['include_local_variables'] is False
assert captured['send_default_pii'] is False
assert captured['send_client_reports'] is False
assert captured['traces_sampler']({}) == 0.0
'''
    environment = dict(os.environ, PROD='false', VMSH_RUNTIME_PROFILE='telegram-history-test')
    subprocess.run([sys.executable, '-c', script], env=environment, check=True, capture_output=True, text=True)

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# PWA tests must remain hermetic even when invoked directly instead of through
# the Make profile. Set this before any test module imports helpers.config/apps;
# otherwise import-time legacy config can load real Telegram/Google credentials.
# See vmshpwa/docs/phase-0-live-integration-harness.md.
os.environ["VMSH_RUNTIME_PROFILE"] = "pwa-e2e"
os.environ["VMSH_INSTANCE"] = "e2e-pytest"
os.environ["VMSH_DB_FILENAME"] = "db/vmshpwa_e2e.sqlite3"
os.environ["VMSH_MEDIA_ROOT"] = ".runtime/vmshpwa/e2e-pytest"
os.environ["VMSH_NATS_SERVER"] = ""
os.environ["VMSH_NATS_TOPIC_PREFIX"] = "vmshpwa_e2e_pytest"
os.environ["VMSH_PWA_PROTOTYPE"] = "true"


@pytest.fixture(scope="session", autouse=True)
def isolated_pwa_database(tmp_path_factory):
    """Give every pytest worker a migrated DB instead of persistent E2E state."""

    from db_methods.pwa import apply_schema_migrations
    from helpers.config import config

    database_path = tmp_path_factory.mktemp("pwa-runtime") / "pwa.sqlite3"
    apply_schema_migrations(database_path)
    original_database_path = config.db_filename
    config.db_filename = str(database_path)
    try:
        yield database_path
    finally:
        config.db_filename = original_database_path

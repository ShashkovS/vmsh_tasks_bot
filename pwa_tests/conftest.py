import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# aiogram 3.30 rebuilds recursive generated Bot API models during import. Load
# them before test modules create unrelated Pydantic namespaces; otherwise the
# full pytest collection can resolve the new RichBlock aliases recursively even
# though the normal application import and isolated adapter tests are valid.
import aiogram  # noqa: F401
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
os.environ["VMSH_ANALYTICS_DB_FILENAME"] = ".runtime/vmshpwa/e2e/analytics.sqlite3"
os.environ["VMSH_MEDIA_ROOT"] = ".runtime/vmshpwa/e2e-pytest"
os.environ["VMSH_NATS_SERVER"] = ""
os.environ["VMSH_NATS_TOPIC_PREFIX"] = "vmshpwa_e2e_pytest"
os.environ["VMSH_PWA_PROTOTYPE"] = "true"

# prometheus_client selects its multiprocess value implementation when metric
# objects are imported. Set one process-private temporary directory before any
# application module is collected; production sets the same variable in
# systemd before Gunicorn starts.
_PROMETHEUS_MULTIPROC_DIR = tempfile.mkdtemp(prefix="vmsh-prometheus-tests-")
os.environ["PROMETHEUS_MULTIPROC_DIR"] = _PROMETHEUS_MULTIPROC_DIR
atexit.register(shutil.rmtree, _PROMETHEUS_MULTIPROC_DIR, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def isolated_pwa_database(tmp_path_factory):
    """Give every pytest worker a migrated DB instead of persistent E2E state."""

    from db_methods.pwa import apply_schema_migrations
    from helpers.config import config

    database_path = tmp_path_factory.mktemp("pwa-runtime") / "pwa.sqlite3"
    apply_schema_migrations(database_path)
    original_database_path = config.db_filename
    original_analytics_path = config.pwa_analytics_db_filename
    config.db_filename = str(database_path)
    config.pwa_analytics_db_filename = str(database_path.with_name("analytics.sqlite3"))
    try:
        yield database_path
    finally:
        config.db_filename = original_database_path
        config.pwa_analytics_db_filename = original_analytics_path

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


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

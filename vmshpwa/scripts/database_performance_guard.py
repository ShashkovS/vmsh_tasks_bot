"""Run fail-closed query performance checks for the selected PWA database."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import maintenance_database_lock
from db_methods.pwa.performance_guard import check_database_performance
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


def guard_runtime_database(runtime_config: PwaMaintenanceConfig) -> dict[str, object]:
    """Check one explicitly selected PWA database under an exclusive lock."""

    require_pwa_maintenance_profile(runtime_config)
    database_path = Path(runtime_config.db_filename)
    with maintenance_database_lock(database_path):
        return check_database_performance(database_path)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check production-critical SQLite query plans and latency"
    )
    parser.parse_args(argv)
    require_pwa_profile_environment()
    # Keep the legacy config loader behind the same explicit profile boundary
    # as migrate_runtime.py; a typo must not select the Telegram database.
    from helpers.config import config

    print(json.dumps(guard_runtime_database(config), sort_keys=True))


if __name__ == "__main__":
    main()

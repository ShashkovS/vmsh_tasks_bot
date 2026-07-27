"""Apply PWA schema migrations as an explicit maintenance command."""

import argparse
from collections.abc import Sequence

from db_methods.pwa import apply_schema_migrations
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


def migrate_runtime(runtime_config: PwaMaintenanceConfig) -> int:
    require_pwa_maintenance_profile(runtime_config)
    state = apply_schema_migrations(runtime_config.db_filename)
    print(
        f"Migrated {runtime_config.pwa_instance}: "
        f"{runtime_config.db_filename} ({len(state.expected)} migrations)"
    )
    return len(state.expected)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Apply migrations to the explicitly selected PWA profile"
    )
    parser.parse_args(argv)
    require_pwa_profile_environment()
    # Importing helpers.config is intentionally delayed: its legacy branch
    # reads Telegram/Google files. The environment guard must run first.
    from helpers.config import config

    migrate_runtime(config)


if __name__ == "__main__":
    main()

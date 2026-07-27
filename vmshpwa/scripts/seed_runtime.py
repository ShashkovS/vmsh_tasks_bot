"""Create an isolated PWA database and record a deterministic prototype seed."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from vmshpwa.scripts.runtime_guard import (
    PwaMaintenanceConfig,
    require_pwa_maintenance_profile,
    require_pwa_profile_environment,
)


def seed_runtime(runtime_config: PwaMaintenanceConfig) -> None:
    require_pwa_maintenance_profile(runtime_config)
    if not runtime_config.pwa_media_root:
        raise RuntimeError("PWA seed requires VMSH_MEDIA_ROOT")

    media_root = Path(runtime_config.pwa_media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    apply_schema_migrations(runtime_config.db_filename)
    database = PwaConnectionFactory(runtime_config.db_filename)
    database.run_write(
        lambda connection: connection.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (
                "vmshpwa.seed",
                json.dumps(
                    {
                        "version": 1,
                        "instance": runtime_config.pwa_instance,
                        "fixture": "prototype-week",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    )
    print(f"Seeded {runtime_config.pwa_instance}: {runtime_config.db_filename}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Seed the explicitly selected isolated PWA profile"
    )
    parser.parse_args(argv)
    require_pwa_profile_environment()
    # See migrate_runtime.py: never import the legacy config loader before the
    # explicit profile guard has succeeded.
    from helpers.config import config

    seed_runtime(config)


if __name__ == "__main__":
    main()

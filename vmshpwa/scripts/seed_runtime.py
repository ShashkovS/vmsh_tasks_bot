"""Create an isolated PWA database and record a deterministic prototype seed."""

import json
from pathlib import Path

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from helpers.config import config


def main() -> None:
    media_root = Path(config.pwa_media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    apply_schema_migrations(config.db_filename)
    database = PwaConnectionFactory(config.db_filename)
    database.run_write(
        lambda connection: connection.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (
                "vmshpwa.seed",
                json.dumps(
                    {
                        "version": 1,
                        "instance": config.pwa_instance,
                        "fixture": "prototype-week",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    )
    print(f"Seeded {config.pwa_instance}: {config.db_filename}")


if __name__ == "__main__":
    main()

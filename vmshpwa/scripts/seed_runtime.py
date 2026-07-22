"""Create an isolated PWA database and record a deterministic prototype seed."""

import json
from pathlib import Path

import db_methods as db
from helpers.config import config


def main() -> None:
    media_root = Path(config.pwa_media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    db.sql.setup(config.db_filename)
    try:
        db.sql.kv["vmshpwa.seed"] = json.dumps(
            {
                "version": 1,
                "instance": config.pwa_instance,
                "fixture": "prototype-week",
            },
            ensure_ascii=False,
        )
    finally:
        db.sql.disconnect()
    print(f"Seeded {config.pwa_instance}: {config.db_filename}")


if __name__ == "__main__":
    main()

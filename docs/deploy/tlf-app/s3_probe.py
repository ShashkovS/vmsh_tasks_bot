"""Owner-authorized production capability probe; one disposable synthetic object.

This is a deployment check, not the isolated test-bucket test harness. README.md.
"""

import asyncio
import json
import secrets
from dataclasses import replace
from pathlib import Path

from helpers.object_storage import create_object_storage
from helpers.pwa.storage_config import load_storage_config
from vmshpwa.scripts.storage_smoke import run_storage_smoke, StorageSmokeError


async def main():
    config = load_storage_config(
        runtime_profile="pwa-production",
        media_root="unused",
        repository_root=Path.cwd(),
    )
    run = "deployment-" + secrets.token_hex(8)
    config = replace(config, prefix=f"deployment-smoke/{run}")
    try:
        report = await run_storage_smoke(create_object_storage(config), run_id=run)
        print(json.dumps(report))
    except StorageSmokeError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    asyncio.run(main())

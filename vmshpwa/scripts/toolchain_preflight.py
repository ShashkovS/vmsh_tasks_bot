"""Print a redacted converter capability report for an explicit PWA profile."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from helpers.pwa.toolchain import probe_toolchain, toolchain_ready
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment


async def toolchain_preflight(runtime_config: object) -> tuple[dict[str, object], bool]:
    probes = await probe_toolchain(runtime_config)
    ready = toolchain_ready(probes)
    return (
        {
            "profile": getattr(runtime_config, "runtime_profile"),
            "ready": ready,
            "tools": [probe.public_dict() for probe in probes],
        },
        ready,
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Probe the converter toolchain selected by a PWA profile"
    )
    parser.parse_args(argv)
    require_pwa_profile_environment()
    # The guard deliberately precedes this import; see runtime-isolation.md.
    from helpers.config import config

    report, ready = asyncio.run(toolchain_preflight(config))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if not ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

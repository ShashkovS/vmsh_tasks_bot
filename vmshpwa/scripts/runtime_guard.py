"""Fail-closed checks shared by PWA maintenance entrypoints."""

import os
from collections.abc import Mapping
from typing import Protocol


class PwaMaintenanceConfig(Protocol):
    runtime_profile: str
    pwa_instance: str
    db_filename: str
    pwa_media_root: str


def require_pwa_profile_environment(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Reject an unscoped process before importing the legacy config loader."""

    source = os.environ if environ is None else environ
    runtime_profile = source.get("VMSH_RUNTIME_PROFILE", "").strip()
    if not runtime_profile.startswith("pwa-"):
        raise RuntimeError(
            "PWA maintenance requires an explicit VMSH_RUNTIME_PROFILE=pwa-*"
        )
    return runtime_profile


def require_pwa_maintenance_profile(
    runtime_config: PwaMaintenanceConfig,
) -> None:
    """Prevent an unscoped command from falling back to legacy credentials/DB."""

    # The historical config loader defaults to the Telegram contour. A typo in
    # a maintenance command must therefore fail before any filesystem or DB
    # write. See vmshpwa/docs/runtime-isolation.md.
    if not runtime_config.runtime_profile.startswith("pwa-"):
        raise RuntimeError(
            "PWA maintenance requires an explicit VMSH_RUNTIME_PROFILE=pwa-*"
        )
    if not runtime_config.pwa_instance:
        raise RuntimeError("PWA maintenance requires a non-empty VMSH_INSTANCE")
    if not runtime_config.db_filename:
        raise RuntimeError("PWA maintenance requires VMSH_DB_FILENAME")

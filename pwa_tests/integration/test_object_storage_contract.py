"""Hermetic integration checks for the phase-0 storage profile boundary."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from helpers.object_storage import ObjectStorage, create_object_storage
from helpers.pwa.storage_config import load_storage_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_storage_config_import_does_not_initialize_legacy_adapters():
    probe = """
import json
import sys
import helpers.pwa.storage_config
blocked = sorted(
    name for name in sys.modules
    if name == 'helpers.config'
    or name.startswith('aiogram')
    or name.startswith('google')
    or name.startswith('gspread')
)
print(json.dumps(blocked))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == []


@pytest.mark.asyncio
async def test_agent_and_e2e_filesystem_profiles_are_storage_isolated(tmp_path):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    agent_config = load_storage_config(
        runtime_profile="pwa-agent",
        media_root=tmp_path / "runtime" / "agent",
        repository_root=repository_root,
    )
    e2e_config = load_storage_config(
        runtime_profile="pwa-e2e",
        media_root=tmp_path / "runtime" / "e2e",
        repository_root=repository_root,
    )
    agent_storage = create_object_storage(agent_config)
    e2e_storage = create_object_storage(e2e_config)
    assert isinstance(agent_storage, ObjectStorage)
    assert isinstance(e2e_storage, ObjectStorage)

    key = "content/shared-logical-name.svg"
    await asyncio.gather(
        agent_storage.put(key, b"agent", "image/svg+xml"),
        e2e_storage.put(key, b"e2e", "image/svg+xml"),
    )

    assert await agent_storage.get(key) == b"agent"
    assert await e2e_storage.get(key) == b"e2e"
    await agent_storage.delete(key)
    assert await e2e_storage.get(key) == b"e2e"


@pytest.mark.asyncio
async def test_independent_filesystem_adapter_instances_share_only_their_root(tmp_path):
    root = tmp_path / "media"
    writer = create_object_storage(
        load_storage_config(
            runtime_profile="pwa-agent",
            media_root=root,
            repository_root=tmp_path,
        )
    )
    reader = create_object_storage(
        load_storage_config(
            runtime_profile="pwa-agent",
            media_root=root,
            repository_root=tmp_path,
        )
    )

    await writer.put("submission/draft.webp", b"version-1", "image/webp")
    assert await reader.get("submission/draft.webp") == b"version-1"
    await writer.put("submission/draft.webp", b"version-2", "image/webp")
    assert await reader.get("submission/draft.webp") == b"version-2"

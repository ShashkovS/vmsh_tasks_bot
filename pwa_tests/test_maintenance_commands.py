import os
import subprocess
import sys
from pathlib import Path

import pytest

from db_methods.pwa import DatabaseLifecycleBusyError, runtime_database_lock
from helpers.config import Config
from vmshpwa.scripts.migrate_runtime import main as migrate_main
from vmshpwa.scripts.migrate_runtime import migrate_runtime
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_runtime import main as seed_main
from vmshpwa.scripts.seed_runtime import seed_runtime
from vmshpwa.scripts.toolchain_preflight import main as toolchain_main
from vmshpwa.scripts.toolchain_smoke import main as toolchain_smoke_main


def test_maintenance_commands_refuse_legacy_profile_before_write(tmp_path):
    database_path = tmp_path / "must-not-exist.sqlite3"
    runtime = Config(
        runtime_profile="legacy",
        pwa_instance="",
        db_filename=str(database_path),
        pwa_media_root=str(tmp_path / "media"),
    )

    with pytest.raises(RuntimeError, match="explicit VMSH_RUNTIME_PROFILE"):
        migrate_runtime(runtime)
    with pytest.raises(RuntimeError, match="explicit VMSH_RUNTIME_PROFILE"):
        seed_runtime(runtime)
    assert not database_path.exists()
    assert not (tmp_path / "media").exists()


@pytest.mark.parametrize(
    "command_main", [migrate_main, seed_main, toolchain_main, toolchain_smoke_main]
)
def test_maintenance_cli_rejects_unknown_database_argument(command_main, tmp_path):
    with pytest.raises(SystemExit) as error:
        command_main(["--database", str(tmp_path / "wrong.sqlite3")])

    assert error.value.code == 2
    assert not (tmp_path / "wrong.sqlite3").exists()


def test_environment_guard_runs_without_loading_legacy_config():
    with pytest.raises(RuntimeError, match="explicit VMSH_RUNTIME_PROFILE"):
        require_pwa_profile_environment({})

    assert (
        require_pwa_profile_environment({"VMSH_RUNTIME_PROFILE": "pwa-agent"})
        == "pwa-agent"
    )


@pytest.mark.parametrize(
    "module",
    [
        "vmshpwa.scripts.migrate_runtime",
        "vmshpwa.scripts.seed_runtime",
        "vmshpwa.scripts.toolchain_preflight",
        "vmshpwa.scripts.toolchain_smoke",
    ],
)
def test_unscoped_cli_fails_before_legacy_credential_loader(module):
    environment = os.environ.copy()
    environment.pop("VMSH_RUNTIME_PROFILE", None)
    environment.pop("PROD", None)

    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "explicit VMSH_RUNTIME_PROFILE=pwa-*" in result.stderr
    assert "гугл-креды" not in result.stderr


def test_seed_uses_only_explicit_pwa_paths(tmp_path):
    database_root = tmp_path / "db"
    media_root = tmp_path / "media"
    database_path = database_root / "vmshpwa_agent.sqlite3"
    runtime = Config(
        runtime_profile="pwa-agent",
        pwa_instance="agent",
        db_filename=str(database_path),
        pwa_media_root=str(media_root / "agent"),
    )

    seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert database_path.is_file()
    assert (media_root / "agent").is_dir()
    assert Path(database_path).stat().st_size > 0


def test_migrate_refuses_to_run_while_pwa_runtime_holds_database(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    runtime = Config(
        runtime_profile="pwa-agent",
        pwa_instance="agent",
        db_filename=str(database_path),
        pwa_media_root=str(tmp_path / "media"),
    )

    with runtime_database_lock(database_path):
        with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
            migrate_runtime(runtime)

    assert not database_path.exists()

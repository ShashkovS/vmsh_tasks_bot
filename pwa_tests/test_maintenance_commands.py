import os
import subprocess
import sys
from pathlib import Path

import pytest

from helpers.config import Config
from vmshpwa.scripts.migrate_runtime import main as migrate_main
from vmshpwa.scripts.migrate_runtime import migrate_runtime
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_runtime import main as seed_main
from vmshpwa.scripts.seed_runtime import seed_runtime


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


@pytest.mark.parametrize("command_main", [migrate_main, seed_main])
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
    database_path = tmp_path / "runtime.sqlite3"
    media_root = tmp_path / "media"
    runtime = Config(
        runtime_profile="pwa-agent",
        pwa_instance="agent-test",
        db_filename=str(database_path),
        pwa_media_root=str(media_root),
    )

    seed_runtime(runtime)

    assert database_path.is_file()
    assert media_root.is_dir()
    assert Path(database_path).stat().st_size > 0

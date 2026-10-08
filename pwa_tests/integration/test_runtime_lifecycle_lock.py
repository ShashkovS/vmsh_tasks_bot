import os
import subprocess
import sys
from pathlib import Path

import pytest

from db_methods.pwa import (
    DatabaseLifecycleBusyError,
    lifecycle_lock_path,
    maintenance_database_lock,
    runtime_database_lock,
)


def test_multiple_runtime_workers_share_lock_but_maintenance_fails_fast(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"

    with runtime_database_lock(database_path) as first_runtime:
        with runtime_database_lock(database_path) as second_runtime:
            assert first_runtime.acquired
            assert second_runtime.acquired
            with pytest.raises(
                DatabaseLifecycleBusyError, match="runtime workers"
            ):
                maintenance_database_lock(database_path).acquire()

    with maintenance_database_lock(database_path) as maintenance:
        assert maintenance.acquired


def test_runtime_workers_in_separate_processes_share_the_same_lock(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    child_script = """
import sys
from db_methods.pwa import runtime_database_lock

with runtime_database_lock(sys.argv[1]):
    print('LOCKED', flush=True)
    sys.stdin.readline()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_script, str(database_path)],
        cwd=Path(__file__).resolve().parents[2],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "LOCKED"
        with runtime_database_lock(database_path):
            with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
                maintenance_database_lock(database_path).acquire()
            assert child.stdin is not None
            child.stdin.write("\n")
            child.stdin.flush()
            stdout, stderr = child.communicate(timeout=5)
            assert child.returncode == 0, stdout + stderr
            # Releasing one worker is insufficient while the second shared
            # holder is still serving requests.
            with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
                maintenance_database_lock(database_path).acquire()
    finally:
        if child.poll() is None and child.stdin is not None:
            child.stdin.write("\n")
            child.stdin.flush()
            child.communicate(timeout=5)


def test_exclusive_maintenance_prevents_runtime_start(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"

    with maintenance_database_lock(database_path):
        with pytest.raises(
            DatabaseLifecycleBusyError, match="maintenance command"
        ):
            runtime_database_lock(database_path).acquire()

    with runtime_database_lock(database_path) as runtime:
        assert runtime.acquired


def test_lock_release_is_idempotent(tmp_path):
    lock = runtime_database_lock(tmp_path / "runtime.sqlite3")
    lock.acquire()

    lock.release()
    lock.release()

    assert not lock.acquired


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Unix fork semantics required")
def test_child_close_does_not_unlock_parent_inherited_description(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    script = """
import os
import sys
from db_methods.pwa import (
    DatabaseLifecycleBusyError,
    maintenance_database_lock,
    runtime_database_lock,
)

held = runtime_database_lock(sys.argv[1]).acquire()
child_pid = os.fork()
if child_pid == 0:
    held.release()
    os._exit(0)
os.waitpid(child_pid, 0)
try:
    maintenance_database_lock(sys.argv[1]).acquire()
except DatabaseLifecycleBusyError:
    pass
else:
    raise SystemExit('child close unlocked parent flock')
held.release()
with maintenance_database_lock(sys.argv[1]):
    pass
print('PASS')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(database_path)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    assert result.stdout.strip() == "PASS"


def test_stale_lock_file_is_reused_after_holder_process_exits(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    script = """
import os
import sys
from db_methods.pwa import runtime_database_lock

runtime_database_lock(sys.argv[1]).acquire()
print('LOCKED', flush=True)
os._exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(database_path)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    assert result.stdout.strip() == "LOCKED"
    assert lifecycle_lock_path(database_path).is_file()
    with maintenance_database_lock(database_path) as maintenance:
        assert maintenance.acquired


def test_database_final_symlink_and_hard_link_alias_are_rejected(tmp_path):
    original = tmp_path / "original.sqlite3"
    original.touch()
    symlink = tmp_path / "symlink.sqlite3"
    symlink.symlink_to(original)

    with pytest.raises(RuntimeError, match="database path must not be a symlink"):
        runtime_database_lock(symlink).acquire()

    hard_link = tmp_path / "hard-link.sqlite3"
    hard_link.hardlink_to(original)
    with pytest.raises(RuntimeError, match="exactly one hard link"):
        runtime_database_lock(original).acquire()
    with pytest.raises(RuntimeError, match="exactly one hard link"):
        maintenance_database_lock(hard_link).acquire()


def test_lock_path_is_stable_and_not_the_replaceable_database_inode(tmp_path):
    relative_database = tmp_path / "nested" / ".." / "runtime.sqlite3"
    lock_path = lifecycle_lock_path(relative_database)

    assert lock_path == tmp_path / ".runtime.sqlite3.vmshpwa-lifecycle.lock"
    assert lock_path != relative_database.resolve(strict=False)


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="POSIX O_NOFOLLOW required")
def test_lock_refuses_symlink_alias(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    real_lock = tmp_path / "real.lock"
    real_lock.touch()
    lifecycle_lock_path(database_path).symlink_to(real_lock)

    with pytest.raises(RuntimeError, match="must not be a symlink"):
        runtime_database_lock(database_path).acquire()


def test_lock_refuses_hard_link_alias(tmp_path):
    database_path = tmp_path / "runtime.sqlite3"
    lock_path = lifecycle_lock_path(database_path)
    lock_path.touch(mode=0o600)
    (tmp_path / "lock-alias").hardlink_to(lock_path)

    with pytest.raises(RuntimeError, match="single-link regular file"):
        runtime_database_lock(database_path).acquire()

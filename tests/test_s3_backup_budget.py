"""S3 backup budget must preserve existing versions; docs/deploy/s3-backup."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    's3_backup', Path(__file__).parents[1] / 'docs/deploy/s3-backup/backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def item(size=1024, modified='2026-11-17T00:00:00Z'):
    return {'Path': 'content/example', 'Size': size, 'ModTime': modified}


def test_same_size_overwrite_requires_budget():
    _, count = backup.budget([item(modified='2026-11-17T00:00:00Z')], [item(modified='2026-11-16T00:00:00Z')], 0, 20*10**9)
    assert count == 1


def test_unchanged_and_deleted_source_objects_need_no_copy():
    _, count = backup.budget([item()], [item(), dict(item(), Path='deleted')], 0, 20*10**9)
    assert count == 0


def test_insufficient_budget_stops_before_copy():
    with pytest.raises(RuntimeError, match='existing backup preserved'):
        backup.budget([item(100_000_000)], [], backup.LIMIT-100_000_000, 20*10**9)


def test_os_disk_reserve_stops_copy():
    with pytest.raises(RuntimeError, match='reserve insufficient'):
        backup.budget([item()], [], 0, 2*1024**3)


def test_equal_timestamps_with_different_offsets_are_unchanged():
    _, count = backup.budget(
        [item(modified='2026-11-17T00:00:00.000000000Z')],
        [item(modified='2026-11-17T03:00:00.000000000+03:00')], 0, 20*10**9)
    assert count == 0

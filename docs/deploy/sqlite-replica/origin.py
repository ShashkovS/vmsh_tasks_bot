#!/usr/bin/python3
"""Forced SSH origin for the two DBs; see README.md and runtime_lock.py/ADR 0002."""
import fcntl
import os
from pathlib import Path
import shlex
import stat
import subprocess

ROOT = Path('/web/vmsh_tasks_bot')
BINARY = str(ROOT/'sqlite-replica/sqlite3_rsync')
DATABASES = {
    str(ROOT/'vmsh_tasks_bot/db/production_v2.db'): 'main.sqlite3',
    str(ROOT/'vmsh_tasks_bot/db/analytics.sqlite3'): 'analytics.sqlite3',
}


def source_for(command):
    args = shlex.split(command)
    if args and args[-1] == '2>/dev/null':
        args.pop()
    if (len(args) != 4 or args[:2] != [BINARY, '--origin']
            or DATABASES.get(args[2]) != args[3]):
        raise ValueError('Only approved SQLite origins are permitted')
    return Path(args[2])


def main():
    source = source_for(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    if source.is_symlink() or source.stat().st_nlink != 1:
        raise RuntimeError('Invalid database path')
    lock = source.with_name('.'+source.name+'.vmshpwa-lifecycle.lock')
    descriptor = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(descriptor)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                or meta.st_uid != source.stat().st_uid):
            raise RuntimeError('Invalid database lifecycle lock')
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        raise SystemExit(subprocess.call([BINARY, '--origin', str(source), DATABASES[str(source)]]))
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()

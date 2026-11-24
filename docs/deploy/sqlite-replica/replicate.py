#!/usr/bin/python3
"""Ten-minute main/analytics replica on prep; operation and recovery: README.md."""
from datetime import datetime, UTC
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

BASE = Path('/web/vmsh_tasks_bot/sqlite-replica')
STATE = Path('/var/lib/vmsh-sqlite-replica')
SOURCES = {'main': 'production_v2.db', 'analytics': 'analytics.sqlite3'}


def main():
    os.umask(0o077)
    with (STATE/'job.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = STATE/'status.json'
        status = json.loads(path.read_text()) if path.exists() else {}
        results = {}
        try:
            for name, source in SOURCES.items():
                started = time.monotonic()
                target = STATE/(name+'.sqlite3')
                command = [str(BASE/'sqlite3_rsync'),
                           'sqlite-origin:/web/vmsh_tasks_bot/vmsh_tasks_bot/db/'+source,
                           str(target), '--exe', str(BASE/'sqlite3_rsync'),
                           '--ssh', str(BASE/'ssh.sh'), '-v']
                result = subprocess.run(command, capture_output=True, text=True, timeout=480)
                if result.returncode:
                    raise RuntimeError(name+': '+(result.stderr+result.stdout)[-2000:])
                with sqlite3.connect(target.as_uri()+'?mode=ro', uri=True) as db:
                    if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                        raise RuntimeError(name+': SQLite quick_check failed')
                results[name] = {'snapshotStarted': datetime.fromtimestamp(time.time()-(time.monotonic()-started), UTC).isoformat(),
                                 'completed': datetime.now(UTC).isoformat(),
                                 'elapsedSeconds': round(time.monotonic()-started, 2),
                                 'bytes': target.stat().st_size, 'quickCheck': 'ok',
                                 'transfer': result.stdout.strip()}
            status.update(lastSuccess=datetime.now(UTC).isoformat(), error=None, databases=results)
        except Exception as error:
            status.update(lastFailure=datetime.now(UTC).isoformat(), error=str(error), partialResults=results)
            raise
        finally:
            temp = path.with_suffix('.new')
            temp.write_text(json.dumps(status, indent=2)+'\n'); temp.replace(path)
        print(json.dumps(status))


if __name__ == '__main__':
    main()

"""Incremental, encrypted S3 pull with retained deletions/versions; README.md."""
from datetime import datetime, UTC
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

STATE = Path('/var/lib/vmsh-s3-backup')
CONFIG = Path('/etc/vmsh-s3-backup/rclone.conf')
BIN = '/usr/local/lib/vmsh-s3-backup/rclone'
SOURCE = 'source:vmsh-static-19080553'
CURRENT = 'backup:current'
LIMIT = 10_000_000_000


def budget(source, destination, used, free):
    """Conservative encrypted allocation for changed files, including temp slack."""
    target = {x['Path']: x for x in destination}
    pending = []
    for x in source:
        old = target.get(x['Path'])
        if (old and old['Size'] == x['Size']
                and datetime.fromisoformat(old['ModTime']) == datetime.fromisoformat(x['ModTime'])):
            continue
        pending.append(x)
    largest = max((x['Size'] for x in source), default=0)
    allocation = sum(math.ceil((x['Size'] + math.ceil(x['Size']/65536)*16 + 32)/4096)*4096
                     + 4096*(x['Path'].count('/')+1) for x in pending)
    # Parallel transfers can overrun a transfer counter by a few whole files.
    slack = max(64*1024**2, 4*(largest+8192))
    available = min(LIMIT-used, free-2*1024**3)
    if allocation+slack > available:
        raise RuntimeError('10 GB budget/free-space reserve insufficient; existing backup preserved')
    return max(1, int((available-slack)*0.9)), len(pending)


def disk_bytes(path):
    return sum(p.lstat().st_blocks*512 for p in [path, *path.rglob('*')])


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--verify', action='store_true', help='force full downloaded byte comparison')
    args = parser.parse_args()
    os.umask(0o077)
    with (STATE/'job.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        path = STATE/'status.json'
        status = json.loads(path.read_text()) if path.exists() else {}
        now = datetime.now(UTC)
        stamp = now.strftime('%Y%m%dT%H%M%S%fZ')
        log = STATE/'logs'/(stamp+'.log')
        common = [BIN, '--config', str(CONFIG), '--use-server-modtime', '--no-gzip-encoding',
                  '--s3-use-accept-encoding-gzip=false', '--checkers', '8',
                  '--transfers', '4', '--contimeout', '15s', '--timeout', '60s',
                  '--retries', '3', '--low-level-retries', '5']
        def run(action, *options, allow_missing=False):
            r = subprocess.run(common+[action, *options],capture_output=True)
            if allow_missing and r.returncode == 3:
                return b'[]'
            if r.returncode:
                with log.open('ab') as f:f.write(r.stderr)
                raise RuntimeError(f'rclone {action} failed (exit {r.returncode}); see private log')
            return r.stdout
        try:
            source = json.loads(run('lsjson', SOURCE, '--recursive', '--files-only', '--no-mimetype'))
            data = run('lsjson', CURRENT, '--recursive', '--files-only', '--no-mimetype', allow_missing=True)
            destination = json.loads(data) if data else []
            used = disk_bytes(STATE)
            transfer_limit, pending = budget(source, destination, used, shutil.disk_usage(STATE).free)
            run('copy', SOURCE, CURRENT, '--backup-dir', 'backup:versions/'+stamp,
                '--max-transfer', str(transfer_limit), '--cutoff-mode', 'cautious',
                '--log-file', str(log), '--log-level', 'INFO', '--stats', '30s')
            verify = args.verify or not status.get('lastFullVerify') or (
                now-datetime.fromisoformat(status['lastFullVerify'])).days >= 30
            if verify:
                run('check', SOURCE, CURRENT, '--download', '--one-way',
                    '--log-file', str(log), '--log-level', 'INFO')
                status['lastFullVerify'] = datetime.now(UTC).isoformat()
            after = disk_bytes(STATE)
            if after > LIMIT:
                raise RuntimeError('Backup exceeded 10 GB budget; no saved objects deleted')
            status.update(lastSuccess=datetime.now(UTC).isoformat(), error=None,
                          sourceObjects=len(source), sourceBytes=sum(x['Size'] for x in source),
                          changedCandidates=pending, allocatedBytes=after, budgetBytes=LIMIT,
                          encrypted=True, deletionsRetained=True, overwriteVersionsRetained=True)
        except Exception as e:
            status.update(error=str(e), lastFailure=datetime.now(UTC).isoformat())
            raise
        finally:
            temp = path.with_suffix('.new');temp.write_text(json.dumps(status,indent=2)+'\n');temp.replace(path)
            # Small diagnostics only; object/version data is never pruned here.
            for old in sorted((STATE/'logs').glob('*.log'))[:-32]:old.unlink()
        print(json.dumps(status))


if __name__ == '__main__':
    main()

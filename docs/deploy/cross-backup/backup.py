#!/usr/bin/env python3
"""Encrypted daily host archives. Requirement and operating contract: README.md."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import fnmatch
import glob
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_CONFIG = Path('/etc/vmsh-cross-backup/config.json')
NAME = re.compile(r'^(vmsh|prep)-(\d{8}T\d{6}Z)-([a-f0-9]{12})\.tar\.7z$')
SHA = re.compile(r'^[a-f0-9]{64}$')
RESERVE = 2 * 1024**3
MAX_UPLOAD = 4 * 1024**3
# prep has a complete compiler SDK under /etc; it is software, not configuration.
DEFAULT_EXCLUDES = ['etc/swift-*-RELEASE-*']


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + '.new')
    with temporary.open('w') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def checksum(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise RuntimeError('Expected a regular file')


def archive_date(name: str, site: str | None = None) -> datetime:
    match = NAME.fullmatch(name)
    if not match or (site is not None and match[1] != site):
        raise ValueError('Invalid archive name or origin')
    return datetime.strptime(match[2], '%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)


def retained(names: list[str], now: datetime) -> set[str]:
    """14 calendar days + latest per month in 24 months, always retaining latest."""
    if not names:
        return set()
    ordered = sorted(names, key=lambda name: (archive_date(name), name))
    keep = {ordered[-1]}
    day_cutoff = now.date() - timedelta(days=13)
    month_cutoff = now.year * 12 + now.month - 1 - 23
    months: dict[int, str] = {}
    for name in ordered:
        created = archive_date(name)
        if created.date() >= day_cutoff:
            keep.add(name)
        month = created.year * 12 + created.month - 1
        if month >= month_cutoff:
            months[month] = name
    return keep | set(months.values())


@contextlib.contextmanager
def lock(path: Path, timeout: float = 0):
    with path.open('a') as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(0.1, remaining))
        yield


def password(path: Path) -> str:
    regular(path)
    if path.stat().st_mode & 0o077:
        raise RuntimeError('Password file must have private permissions')
    value = path.read_text().rstrip('\n')
    if len(value) < 20 or '\n' in value or '\r' in value:
        raise RuntimeError('Password must be a single line of at least 20 characters')
    return value


def sevenzip(config: dict, arguments: list[str], secret: str, cwd=None, output=None) -> None:
    # Bare -p prompts only on creation; encrypted-header t/x prompt without -p.
    # Keep the password out of argv, inherited environment, output and errors.
    result = subprocess.run(
        [config['sevenzip'], *arguments], input=secret + '\n', text=True,
        stdout=output if output is not None else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, cwd=cwd, check=False,
        timeout=3600,
    )
    if result.returncode:
        raise RuntimeError('7zip operation failed')


def snapshot(source: Path, destination: Path) -> dict:
    regular(source)
    if source.stat().st_nlink != 1:
        raise RuntimeError('Database must not have hard-link aliases')
    source = source.resolve()
    # Same sidecar and shared flock as db_methods/pwa/runtime_lock.py (ADR 0002).
    # Root capture never chmods/unlinks the service-owned lifecycle sidecar.
    sidecar = source.with_name('.' + source.name + '.vmshpwa-lifecycle.lock')
    descriptor = os.open(sidecar, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != source.stat().st_uid):
            raise RuntimeError('Invalid database lifecycle lock')
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with (contextlib.closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src,
              contextlib.closing(sqlite3.connect(destination)) as dst):
            src.backup(dst, pages=256, sleep=0.05)
        with sqlite3.connect(destination) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('SQLite snapshot failed integrity check')
    finally:
        os.close(descriptor)
    return {'source': str(source), 'sha256': checksum(destination)}


def config_paths(config: dict) -> list[Path]:
    """Include real config targets, not just pointers into /web (TLF runbook)."""
    roots = [Path(path) for path in config['config_paths']]
    if config.get('discover_credentials', True):
        roots.append(Path(__file__).resolve().parent)
        roots.append(Path('/var/spool/cron'))
        for pattern in ('/root/.ssh', '/root/.config', '/root/*credentials*',
                        '/root/*secrets*', '/home/*/.ssh', '/home/*/.config', '/web/*/.ssh',
                        '/web/*/creds_prod', '/web/*/*/creds_prod',
                        '/web/*/.env', '/web/*/*/.env'):
            roots.extend(Path(path) for path in glob.glob(pattern))
    found: set[Path] = set()
    queue = [path for path in roots if path.exists() or path.is_symlink()]
    while queue:
        path = queue.pop()
        if path in found:
            continue
        found.add(path)
        if path.is_symlink():
            target = path.resolve()
            # /dev/null is a masked systemd unit, not a backup payload.
            if target.exists() and (target.is_file() or target.is_dir()):
                queue.append(target)
        elif path.is_dir():
            # Follow external links only in config trees, not /etc/alternatives.
            if any(part in ('nginx', 'systemd', 'letsencrypt', 'prometheus',
                            'grafana', 'nats', 'deploy', 'tls') for part in path.parts):
                queue.extend(path.iterdir())
            elif str(path) == '/etc':
                queue.extend(path / name for name in
                             ('nginx', 'systemd', 'letsencrypt', 'prometheus',
                              'grafana', 'nats') if (path / name).exists())
        if path.is_file() and path.suffix in ('.service', '.socket', '.timer', '.conf'):
            # systemd permits backslash continuations in ExecStart/EnvironmentFile.
            content = re.sub(r'\\\n\s*', ' ', path.read_text())
            for line in content.splitlines():
                if line.strip().startswith('EnvironmentFile='):
                    for entry in shlex.split(line.split('=', 1)[1]):
                        candidate = Path(entry.lstrip('-'))
                        if candidate.is_absolute() and candidate.exists():
                            queue.append(candidate)
                elif line.strip().startswith(('ExecStart=', 'ExecStartPre=', 'ExecReload=')):
                    for entry in shlex.split(line.split('=', 1)[1]):
                        candidate = Path(entry.split('=', 1)[-1])
                        if (candidate.is_absolute() and candidate.is_file()
                                and candidate.suffix in ('.conf', '.json', '.yaml',
                                                         '.yml', '.ini', '.env', '.sh')):
                            queue.append(candidate)
    # Avoid recursive duplicate entries while retaining external symlink targets.
    selected: list[Path] = []
    for path in sorted(found, key=lambda p: (len(p.parts), str(p))):
        if not any(parent in path.parents and not parent.is_symlink()
                   for parent in selected):
            selected.append(path)
    return selected


def excluded(path: Path, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(str(candidate).lstrip('/'), pattern)
               for candidate in (path, *path.parents) for pattern in patterns)


def config_size(paths: list[Path], patterns: list[str]) -> int:
    """Conservative tar workspace estimate without following symlinks."""
    total = 0
    for path in paths:
        if excluded(path, patterns) or path.is_symlink():
            continue
        if path.is_file():
            total += path.stat().st_size + 1024
        elif path.is_dir():
            for root, directories, files in os.walk(path):
                directories[:] = [name for name in directories
                                  if not excluded(Path(root) / name, patterns)]
                for name in files:
                    candidate = Path(root) / name
                    if not excluded(candidate, patterns) and not candidate.is_symlink():
                        total += candidate.stat().st_size + 1024
    return total


def restore(config: dict, archive: Path, target: Path, secret_file: Path) -> dict:
    regular(archive)
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    secret = password(secret_file)
    sevenzip(config, ['t', str(archive)], secret)
    payload = target / 'payload.tar'
    # Extract one member to an already opened regular file. Archive-controlled
    # paths/symlinks can never select the root process's output destination.
    with payload.open('xb') as stream:
        sevenzip(config, ['x', '-so', str(archive), 'payload.tar'], secret, output=stream)
    regular(payload)
    # Leave host configs in tar for deliberate recovery. Never materialize their
    # absolute symlinks or restore ownership/configuration into a running host.
    with tarfile.open(payload) as tar:
        manifest_member = tar.getmember('manifest.json')
        if not manifest_member.isfile():
            raise RuntimeError('Invalid archive manifest')
        manifest = json.load(tar.extractfile(manifest_member))
        (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (target / 'db').mkdir(mode=0o700)
        for label in ('main', 'analytics'):
            member = tar.getmember(f'db/{label}.sqlite3')
            if not member.isfile():
                raise RuntimeError('Invalid database archive member')
            restored = target / member.name
            with restored.open('wb') as stream:
                shutil.copyfileobj(tar.extractfile(member), stream)
            if checksum(restored) != manifest['databases'][label]['sha256']:
                raise RuntimeError('Restored database hash mismatch')
            with sqlite3.connect(restored) as db:
                if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise RuntimeError('Restored SQLite integrity failed')
    return manifest


def capture(config: dict) -> Path:
    state = Path(config['state'])
    secret = password(Path(config['password_file']))
    paths = config_paths(config)
    exclusions = config.get('exclude_config_patterns', DEFAULT_EXCLUDES)
    host_bytes = config_size(paths, exclusions)
    estimate = sum(Path(path).stat().st_size for path in config['databases'].values())
    # Snapshot + tar + extracted tar + restored DB + compressed candidate.
    if shutil.disk_usage(state).free < RESERVE + 5 * estimate + 3 * host_bytes + 64 * 1024**2:
        raise RuntimeError('Insufficient free space for safe capture')
    created = datetime.now(UTC)
    name = f"{config['site']}-{created:%Y%m%dT%H%M%SZ}-{secrets.token_hex(6)}.tar.7z"
    with tempfile.TemporaryDirectory(prefix='.work-', dir=state) as directory:
        work = Path(directory)
        (work / 'db').mkdir(mode=0o700)
        manifest = {'site': config['site'], 'createdAt': created.isoformat(),
                    'databases': {}, 'configPaths': [],
                    'configExclusions': exclusions, 'estimatedConfigBytes': host_bytes,
                    'backupToolSha256': checksum(Path(__file__).resolve())}
        for label, source in config['databases'].items():
            manifest['databases'][label] = snapshot(Path(source), work / 'db' / f'{label}.sqlite3')
        manifest['configPaths'] = [str(path) for path in paths]
        revision = subprocess.run(['git', '-C', config['code'], 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, check=False)
        manifest['revision'] = revision.stdout.strip() if not revision.returncode else None
        for tool, arguments, field in (
            ('dpkg-query', ['-W', '-f=${binary:Package}\t${Version}\n'], 'packages'),
            ('systemctl', ['list-unit-files', '--no-pager', '--no-legend'], 'unitFiles'),
        ):
            if shutil.which(tool):
                result = subprocess.run([tool, *arguments], capture_output=True, text=True,
                                        check=False)
                if result.returncode == 0:
                    manifest[field] = result.stdout.splitlines()
        atomic_json(work / 'manifest.json', manifest)
        listing = work / 'paths.list'
        listing.write_bytes(b''.join(str(path).lstrip('/').encode() + b'\0' for path in paths))
        result = subprocess.run([
            config['tar'], '--create', '--file', str(work / 'payload.tar'),
            '--acls', '--xattrs', '--numeric-owner', '--transform=flags=r;s,^,host/,',
            *['--exclude=' + pattern for pattern in exclusions],
            '--directory=/', '--null', '--verbatim-files-from', '--files-from', str(listing),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError('Host configuration tar capture failed')
        result = subprocess.run([
            config['tar'], '--append', '--file', str(work / 'payload.tar'),
            '--acls', '--xattrs', '--numeric-owner', '--directory=' + str(work),
            'db', 'manifest.json',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError('Database tar capture failed')
        candidate = work / name
        sevenzip(config, ['a', '-t7z', '-mhe=on', '-m0=LZMA2', '-mx=5',
                         '-mmt=2', '-p', str(candidate), 'payload.tar'], secret, work)
        restored = work / 'restore'
        restore(config, candidate, restored, Path(config['password_file']))
        destination = state / 'outgoing' / name
        os.replace(candidate, destination)
        os.chmod(destination, 0o600)
        atomic_json(destination.with_suffix(destination.suffix + '.json'),
                    {'sha256': checksum(destination), 'size': destination.stat().st_size})
        return destination


def inventory(directory: Path, site: str) -> dict:
    result = {}
    for path in sorted(directory.glob(site + '-*.tar.7z')):
        archive_date(path.name, site)
        regular(path)
        receipt = path.with_suffix(path.suffix + '.json')
        regular(receipt)
        record = json.loads(receipt.read_text())
        if record != {'sha256': checksum(path), 'size': path.stat().st_size}:
            raise RuntimeError('Archive receipt mismatch')
        result[path.name] = record
    return result


def prune(directory: Path, site: str) -> None:
    entries = inventory(directory, site)
    keep = retained(list(entries), datetime.now(UTC))
    for name in entries.keys() - keep:
        (directory / name).unlink()
        (directory / (name + '.json')).unlink()


def ssh_command(config: dict, command: str) -> list[str]:
    return ['ssh', '-F', config['ssh_config'], '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=15', 'crossbackup-peer', command]


def sync(config: dict) -> None:
    state = Path(config['state'])
    result = subprocess.run(ssh_command(config, 'inventory'), capture_output=True,
                            text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError('Peer SSH inventory failed; archives preserved')
    remote = json.loads(result.stdout)
    local = inventory(state / 'outgoing', config['site'])
    for name, record in local.items():
        if remote.get(name) == record:
            continue
        if name in remote:
            raise RuntimeError('Peer archive hash differs; refusing overwrite')
        command = f"put {name} {record['size']} {record['sha256']}"
        with (state / 'outgoing' / name).open('rb') as stream:
            sent = subprocess.run(ssh_command(config, command), stdin=stream,
                                  capture_output=True, timeout=3600, check=False)
        if sent.returncode or json.loads(sent.stdout) != record:
            raise RuntimeError('Cross-transfer failed; archives preserved')
    prune(state / 'outgoing', config['site'])
    # The receiving host owns retention. The sending SSH key has no delete API.
    incoming = state / 'incoming'
    with lock(incoming / '.receive.lock', timeout=120):
        prune(incoming, config['peer_site'])
    if config.get('legacy_timer'):
        timer = config['legacy_timer']
        # README.md, Operation: retiring a linked legacy unit can remove its
        # unit-file link. Later hourly syncs accept an absent, stopped unit even
        # if systemd still remembers its historical failed state.
        result = subprocess.run(['systemctl', 'show', timer, '-p', 'LoadState',
                                 '-p', 'ActiveState'], check=True, capture_output=True, text=True)
        properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if not (properties.get('LoadState') == 'not-found'
                and properties.get('ActiveState') in {'inactive', 'failed'}):
            subprocess.run(['systemctl', 'disable', '--now', timer],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def receive(directory: Path, site: str, command: str, stream) -> dict:
    tokens = shlex.split(command)
    # README.md, Operation: peer inventory/receive, pruning and verification
    # serialize; simultaneous hourly syncs wait through short lock contention.
    with lock(directory / '.receive.lock', timeout=120):
        # An interrupted SSH session may leave a private partial upload after
        # SIGKILL. With this lock held, no live upload can still own these names.
        for stale in directory.glob('.upload-*'):
            if not stale.is_dir():
                stale.unlink()
        if tokens == ['inventory']:
            return inventory(directory, site)
        if len(tokens) != 4 or tokens[0] != 'put':
            raise ValueError('Unsupported receiving command')
        _, name, length, digest = tokens
        created = archive_date(name, site)
        if created > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError('Future archive rejected')
        size = int(length)
        if not 0 < size <= MAX_UPLOAD or not SHA.fullmatch(digest):
            raise ValueError('Invalid size or digest')
        if shutil.disk_usage(directory).free < RESERVE + size:
            raise RuntimeError('Receiver free space reserve reached')
        with tempfile.NamedTemporaryFile(prefix='.upload-', dir=directory) as temporary:
            remaining = size
            hasher = hashlib.sha256()
            while remaining:
                chunk = stream.read(min(1024**2, remaining))
                if not chunk:
                    raise RuntimeError('Incomplete upload')
                temporary.write(chunk)
                hasher.update(chunk)
                remaining -= len(chunk)
            if stream.read(1) or hasher.hexdigest() != digest:
                raise RuntimeError('Upload size or checksum mismatch')
            record = {'size': size, 'sha256': digest}
            destination = directory / name
            if destination.exists() or destination.is_symlink():
                regular(destination)
                if checksum(destination) != digest:
                    raise RuntimeError('Refusing to overwrite existing archive')
                atomic_json(destination.with_suffix(destination.suffix + '.json'), record)
            else:
                temporary.flush()
                os.fsync(temporary.fileno())
                # Publish the receipt first: a crash before archive publication
                # leaves only an ignored receipt, never an incomplete inventory.
                atomic_json(destination.with_suffix(destination.suffix + '.json'), record)
                # Hard link publishes complete bytes atomically without an
                # overwrite; the temporary name is removed on context exit.
                os.link(temporary.name, destination)
            return record


def verify(config: dict) -> None:
    state = Path(config['state'])
    for subdir, site, key in (
        ('outgoing', config['site'], Path(config['password_file'])),
        ('incoming', config['peer_site'], Path(config['peer_password_file'])),
    ):
        with lock(state / 'incoming' / '.receive.lock', timeout=120):
            entries = inventory(state / subdir, site)
            if not entries:
                raise RuntimeError('No complete archive available for verification')
            latest = max(entries, key=archive_date)
            with tempfile.TemporaryDirectory(prefix='.verify-', dir=state) as work:
                restore(config, state / subdir / latest, Path(work) / 'restored', key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'sync', 'verify', 'receive', 'restore'])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--incoming', type=Path)
    parser.add_argument('--site', choices=['vmsh', 'prep'])
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--password-file', type=Path)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    def interrupted(_number, _frame):
        raise InterruptedError('Backup process interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.action == 'receive':
            if not args.incoming or not args.site:
                parser.error('receive needs --incoming and --site')
            signal.signal(signal.SIGALRM, interrupted)
            signal.alarm(3600)
            print(json.dumps(receive(args.incoming, args.site,
                                     os.environ.get('SSH_ORIGINAL_COMMAND', ''), sys.stdin.buffer)))
            return
        config = json.loads(args.config.read_text())
        if args.action == 'restore':
            if not all((args.archive, args.password_file, args.target)):
                parser.error('restore needs archive, password-file and target')
            restore(config, args.archive.resolve(), args.target.resolve(), args.password_file)
            print('Archive and SQLite restore verified; host configs remain in payload.tar')
            return
        state = Path(config['state'])
        with lock(state / '.job.lock'):
            # Only this tool owns these private temporary directories; the job
            # lock proves no capture/verify is still using them after a crash.
            for pattern in ('.work-*', '.verify-*'):
                for stale in state.glob(pattern):
                    if stale.is_dir() and not stale.is_symlink():
                        shutil.rmtree(stale)
            status_path = state / 'status.json'
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            try:
                if args.action == 'backup':
                    archive = capture(config)
                    status['lastLocalSuccess'] = datetime.now(UTC).isoformat()
                    status['lastArchive'] = archive.name
                    atomic_json(status_path, status)
                if args.action in ('backup', 'sync'):
                    sync(config)
                    status['lastCrossSuccess'] = datetime.now(UTC).isoformat()
                else:
                    verify(config)
                    status['lastVerificationSuccess'] = datetime.now(UTC).isoformat()
                status['error'] = None
            except Exception as error:
                status['error'] = str(error)
                status['lastFailure'] = datetime.now(UTC).isoformat()
                raise
            finally:
                atomic_json(status_path, status)
        print(json.dumps(status))
    except Exception as error:  # noqa: BLE001 — CLI boundary sanitizes subprocess errors.
        # subprocess outputs are intentionally suppressed: may contain secrets.
        print(f'Cross-backup failed: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

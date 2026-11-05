#!/usr/bin/env python3
"""Root installation / restricted peer authorization. See README.md."""

from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import secrets
import shutil
import subprocess
from pathlib import Path

CONFIG = Path('/etc/vmsh-cross-backup')
STATE = Path('/var/lib/vmsh-cross-backup')
TOOLS = Path('/usr/local/lib/vmsh-cross-backup')
BASE = Path('/web/vmsh_tasks_bot')
SYSTEMD = Path('/etc/systemd/system')
UNITS = ('vmsh-cross-backup', 'vmsh-cross-backup-sync', 'vmsh-cross-backup-verify')
SITES = {
    'vmsh': ('prep', '188.245.158.162', 'production_v2.db', '00:15'),
    'prep': ('vmsh', '217.114.6.190', 'production_prep.db', '01:15'),
}
RECEIVER = 'vmsh_crossbackup'


def write(path: Path, value: str, mode=0o600) -> None:
    path.write_text(value)
    path.chmod(mode)


def refresh_links() -> None:
    """Expose every installed location from BASE; see README.md, Discoverability."""
    index = BASE / 'cross-backup'
    links = {
        'config': CONFIG, 'tools': TOOLS, 'state': STATE,
        'outgoing': STATE / 'outgoing', 'incoming': STATE / 'incoming',
        'receiver': STATE / 'receiver', 'status.json': STATE / 'status.json',
        'README.md': TOOLS / 'README.md',
    }
    for name in UNITS:
        for extension in ('.service', '.timer'):
            links[f'systemd/{name}{extension}'] = SYSTEMD / (name + extension)
        links[f'systemd/enabled/{name}.timer'] = (
            SYSTEMD / 'timers.target.wants' / (name + '.timer')
        )
    # Include the persistent installation/proof directory from the first prep run.
    for release in Path('/root').glob('vmsh-cross-backup-release-*'):
        links[f'installations/{release.name}'] = release
    directories = {index}
    for relative in links:
        parent = index
        for part in Path(relative).parent.parts:
            parent /= part
            directories.add(parent)
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        if directory.is_symlink():
            raise RuntimeError(f'Refusing a symlinked index directory: {directory}')
        directory.mkdir(mode=0o755, exist_ok=True)
        if directory.stat().st_uid != os.geteuid():
            raise RuntimeError(f'Index directory has a different owner: {directory}')
        directory.chmod(0o755)
    # Preflight conflicts so an existing operator file/link is never replaced.
    for relative, target in links.items():
        path = index / relative
        if path.is_symlink():
            if path.readlink() != target:
                raise RuntimeError(f'Index link points elsewhere: {path}')
        elif path.exists():
            raise RuntimeError(f'Index path already exists: {path}')
    for relative, target in links.items():
        path = index / relative
        if not path.is_symlink():
            path.symlink_to(target)
    print(f'System object links: {index}')


def authorize(path: Path) -> None:
    config = json.loads((CONFIG / 'config.json').read_text())
    key = path.read_text().strip()
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]+)?', key):
        raise RuntimeError('Expected one ed25519 public key, without options')
    subprocess.run(['ssh-keygen', '-l', '-f', str(path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    forced = (f'/usr/bin/python3 {TOOLS}/backup.py receive '
              f'--incoming {STATE}/incoming --site {config["peer_site"]}')
    # Only the matching origin's archive uploads/inventory are callable.
    value = f'restrict,command="{forced}" {key}\n'
    authorized = STATE / 'receiver/.ssh/authorized_keys'
    if authorized.exists() and authorized.read_text() != value:
        raise RuntimeError('Peer key already configured; review before replacing it')
    write(authorized, value)
    account = pwd.getpwnam(RECEIVER)
    os.chown(authorized, account.pw_uid, account.pw_gid)
    print('Restricted peer public key installed')


def unit(action: str) -> str:
    return f'''[Unit]
Description=VMSH cross-backup {action} (docs/deploy/cross-backup/README.md)
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
User=root
ExecStart=/usr/bin/python3 {TOOLS}/backup.py {action}
UMask=0077
TimeoutStartSec=2h
Nice=10
IOSchedulingClass=idle
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={STATE} {BASE}/vmsh_tasks_bot/db
'''


def install(site: str, secret_file: Path | None) -> None:
    peer, address, database, schedule = SITES[site]
    sevenzip = shutil.which('7zz') or shutil.which('7z')
    tar = shutil.which('tar')
    if not sevenzip or not tar:
        raise RuntimeError('7zip and GNU tar are required')
    version = subprocess.check_output([tar, '--version'], text=True)
    if 'GNU tar' not in version:
        raise RuntimeError('GNU tar with ACL/xattr support is required')
    code = BASE / 'vmsh_tasks_bot'
    for name in (database, 'analytics.sqlite3'):
        if not (code / 'db' / name).is_file():
            raise RuntimeError('Configured database does not exist')
    source = Path(__file__).resolve().parent
    for path in (CONFIG, TOOLS):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The receiver can traverse to its home, but cannot read root-owned state.
    STATE.mkdir(mode=0o711, parents=True, exist_ok=True)
    STATE.chmod(0o711)
    (STATE / 'outgoing').mkdir(mode=0o700, exist_ok=True)
    (STATE / 'receiver/.ssh').mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        account = pwd.getpwnam(RECEIVER)
        if account.pw_dir != str(STATE / 'receiver'):
            raise RuntimeError('Existing receiver account has a different home')
    except KeyError:
        subprocess.run(['useradd', '--system', '--user-group', '--home-dir',
                        str(STATE / 'receiver'), '--no-create-home',
                        '--shell', '/bin/sh', RECEIVER], check=True)
        # Public-key-only SSH requires an unlocked account on some distributions.
        # '*' is an unusable password, not a valid password login credential.
        subprocess.run(['usermod', '--password', '*', RECEIVER], check=True)
        account = pwd.getpwnam(RECEIVER)
    for path in (STATE / 'receiver', STATE / 'receiver/.ssh'):
        path.chmod(0o700)
        os.chown(path, account.pw_uid, account.pw_gid)
    incoming = STATE / 'incoming'
    incoming.mkdir(mode=0o700, exist_ok=True)
    os.chown(incoming, account.pw_uid, account.pw_gid)
    receive_lock = incoming / '.receive.lock'
    if not receive_lock.exists():
        receive_lock.touch(mode=0o600)
        os.chown(receive_lock, account.pw_uid, account.pw_gid)
    # The receiving command and parents must be readable/traversable to the user.
    TOOLS.chmod(0o755)
    for filename in ('backup.py', 'install.py', 'README.md'):
        destination = TOOLS / filename
        if filename == 'README.md' and not (source / filename).exists():
            continue
        if source / filename != destination:
            shutil.copyfile(source / filename, destination)
        destination.chmod(0o644 if filename == 'README.md' else 0o755)
    legacy = source.parent / 'tlf-app/backup.py'
    if legacy.exists():
        shutil.copyfile(legacy, TOOLS / 'legacy-backup.py')
    else:
        legacy = TOOLS / 'legacy-backup.py'
    if site == 'prep':
        if not legacy.exists():
            raise RuntimeError('Preserving legacy archives requires legacy-backup.py')
        shutil.copyfile(legacy, BASE / 'deploy/bin/backup.py')
        (BASE / 'deploy/bin/backup.py').chmod(0o755)
    key = CONFIG / 'id_ed25519'
    if not key.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key),
                        '-C', f'{site}-crossbackup'], check=True)
    archive_password = CONFIG / 'archive-password'
    if not archive_password.exists():
        value = secret_file.read_text().rstrip('\n') if secret_file else secrets.token_urlsafe(48)
        if len(value) < 20 or '\n' in value or '\r' in value:
            raise RuntimeError('Archive password must be one line, at least 20 characters')
        write(archive_password, value + '\n')
    elif secret_file and secret_file.read_text() != archive_password.read_text():
        raise RuntimeError('Refusing to replace an existing archive password')
    known_hosts = CONFIG / 'known_hosts'
    if not known_hosts.exists():
        write(known_hosts, '')
    write(CONFIG / 'ssh_config', f'''Host crossbackup-peer
    HostName {address}
    User {RECEIVER}
    Port 22179
    IdentityFile {key}
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    UserKnownHostsFile {known_hosts}
    BatchMode yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
''')
    configuration = {
        'site': site, 'peer_site': peer, 'state': str(STATE), 'code': str(code),
        'databases': {'main': str(code / 'db' / database),
                      'analytics': str(code / 'db/analytics.sqlite3')},
        'password_file': str(archive_password),
        'peer_password_file': str(CONFIG / 'peer-archive-password'),
        'ssh_config': str(CONFIG / 'ssh_config'), 'sevenzip': sevenzip, 'tar': tar,
        'config_paths': ['/etc', str(code / 'creds_prod'),
                         str(BASE / 'deploy/config'), str(BASE / 'deploy/secrets'),
                         str(BASE / 'deploy/bin'),
                         str(BASE / 'vmshpwa/runtime/vmshpwa.env'),
                         str(BASE / 'monitoring/secrets'), str(BASE / 'tls')],
        'legacy_timer': 'vmsh-backup.timer' if site == 'prep' else None,
    }
    old = CONFIG / 'config.json'
    if old.exists() and json.loads(old.read_text()) != configuration:
        raise RuntimeError('Existing backup config differs; review before replacing it')
    write(old, json.dumps(configuration, indent=2) + '\n')
    for action, suffix, calendar in (
        ('backup', '', f'*-*-* {schedule}:00 UTC'),
        ('sync', '-sync', '*-*-* *:45:00 UTC'),
        ('verify', '-verify', '*-*-01 03:15:00 UTC'),
    ):
        name = 'vmsh-cross-backup' + suffix
        write(SYSTEMD / (name + '.service'), unit(action), 0o644)
        write(SYSTEMD / (name + '.timer'), f'''[Unit]
Description=VMSH cross-backup {action} schedule
[Timer]
OnCalendar={calendar}
Persistent=true
Unit={name}.service
[Install]
WantedBy=timers.target
''', 0o644)
    subprocess.run(['systemd-analyze', 'verify',
                    *[str(SYSTEMD / (name + extension))
                      for name in UNITS
                      for extension in ('.service', '.timer')]], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'vmsh-cross-backup.timer',
                    'vmsh-cross-backup-sync.timer', 'vmsh-cross-backup-verify.timer'], check=True)
    refresh_links()
    print('Installed. Exchange peer public keys, trusted host keys and recovery passwords.')
    print('Local public key:', key.with_suffix('.pub').read_text().strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', choices=SITES)
    parser.add_argument('--password-file', type=Path)
    parser.add_argument('--authorize-peer-key', type=Path)
    parser.add_argument('--refresh-links', action='store_true',
                        help='Add discoverability links without running a backup or changing units')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run the installer as root')
    os.umask(0o077)
    if args.refresh_links:
        refresh_links()
    elif args.authorize_peer_key:
        authorize(args.authorize_peer_key)
    elif args.site:
        install(args.site, args.password_file)
    else:
        parser.error('Specify --site, --authorize-peer-key or --refresh-links')


if __name__ == '__main__':
    main()

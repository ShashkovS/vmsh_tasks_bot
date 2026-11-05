"""Cross-backup failure/restore contract: docs/deploy/cross-backup/README.md."""

import fcntl
import hashlib
import importlib.util
import io
import shutil
import sqlite3
import subprocess
import tarfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'cross_backup', ROOT / 'docs/deploy/cross-backup/backup.py'
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


def name(date, site='vmsh', suffix='abcdef012345'):
    return f'{site}-{date}T001500Z-{suffix}.tar.7z'


@pytest.fixture
def fixture_config(tmp_path):
    state = tmp_path / 'state'
    for subdir in ('outgoing', 'incoming'):
        (state / subdir).mkdir(parents=True)
    password = tmp_path / 'password'
    password.write_text('isolated-test-password-for-backup\n')
    password.chmod(0o600)
    databases = {}
    for label in ('main', 'analytics'):
        database = tmp_path / f'{label}.sqlite3'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE content(value TEXT)')
            db.execute('INSERT INTO content VALUES (?)', (label,))
        database.with_name('.' + database.name + '.vmshpwa-lifecycle.lock').touch()
        databases[label] = str(database)
    host = tmp_path / 'host'
    host.mkdir()
    (host / 'secret').write_text('synthetic-config-secret')
    (host / 'secret').chmod(0o600)
    external = tmp_path / 'external.conf'
    external.write_text('real config behind nginx symlink')
    (host / 'symlink').symlink_to(external)
    return {
        'site': 'vmsh', 'peer_site': 'prep', 'state': str(state), 'code': str(tmp_path),
        'databases': databases, 'password_file': str(password),
        'peer_password_file': str(password), 'config_paths': [str(host), str(external)],
        'discover_credentials': False,
        'sevenzip': shutil.which('7zz') or shutil.which('7z'),
        'tar': shutil.which('gtar') or shutil.which('tar'),
    }


def test_calendar_retention_and_latest_safety():
    now = datetime(2026, 10, 10, tzinfo=UTC)
    names = [name('20241001'), name('20241101'), name('20241130'),
             name('20260926'), name('20260927'), name('20260928'),
             name('20260930'), name('20261001'), name('20261010')]
    keep = backup.retained(names, now)
    assert name('20241001') not in keep
    assert name('20241101') not in keep
    assert name('20241130') in keep
    assert name('20260926') not in keep
    assert name('20260927') in keep
    assert name('20260928') in keep
    assert name('20261010') in keep
    assert backup.retained([name('20200101')], now) == {name('20200101')}


def test_wal_snapshot_contains_committed_writes(tmp_path):
    source = tmp_path / 'main.db'
    connection = sqlite3.connect(source)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE events(value TEXT)')
    connection.execute('INSERT INTO events VALUES ("committed in WAL")')
    connection.commit()
    source.with_name('.main.db.vmshpwa-lifecycle.lock').touch()
    target = tmp_path / 'restored.db'
    backup.snapshot(source, target)
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT value FROM events').fetchone() == ('committed in WAL',)
    connection.close()


def test_migration_lock_and_missing_db_fail_without_snapshot(tmp_path):
    source = tmp_path / 'main.db'
    with pytest.raises(FileNotFoundError):
        backup.snapshot(source, tmp_path / 'target.db')
    assert not source.exists()
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE content(value TEXT)')
    lock = source.with_name('.main.db.vmshpwa-lifecycle.lock')
    lock.touch()
    with lock.open() as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            backup.snapshot(source, tmp_path / 'target.db')
    assert not (tmp_path / 'target.db').exists()


@pytest.mark.parametrize('command', [
    'rm -rf /', 'put ../../escape 1 ' + 'a' * 64,
    'put ' + name('20261010', site='prep') + ' 1 ' + 'a' * 64,
    'put ' + name('20991010') + ' 1 ' + 'a' * 64,
    'put ' + name('20261010') + ' -1 ' + 'a' * 64,
])
def test_receiver_rejects_commands_and_wrong_origin(tmp_path, command):
    with pytest.raises(ValueError):
        backup.receive(tmp_path, 'vmsh', command, io.BytesIO(b'x'))
    assert not list(tmp_path.glob('*.tar.7z'))


def test_receiver_atomicity_idempotence_and_no_overwrite(tmp_path):
    archive = name('20261009')
    data = b'encrypted fixture bytes'
    digest = hashlib.sha256(data).hexdigest()
    command = f'put {archive} {len(data)} {digest}'
    with pytest.raises(RuntimeError, match='Incomplete'):
        backup.receive(tmp_path, 'vmsh', command, io.BytesIO(data[:-1]))
    assert not list(tmp_path.glob('*.tar.7z'))
    assert not list(tmp_path.glob('.upload-*'))
    expected = {'size': len(data), 'sha256': digest}
    assert backup.receive(tmp_path, 'vmsh', command, io.BytesIO(data)) == expected
    assert backup.receive(tmp_path, 'vmsh', command, io.BytesIO(data)) == expected
    assert backup.receive(tmp_path, 'vmsh', 'inventory', io.BytesIO()) == {archive: expected}
    other = b'changed fixture data'
    command = f'put {archive} {len(other)} {hashlib.sha256(other).hexdigest()}'
    with pytest.raises(RuntimeError, match='overwrite'):
        backup.receive(tmp_path, 'vmsh', command, io.BytesIO(other))
    assert (tmp_path / archive).read_bytes() == data


def test_receiver_detects_disk_corruption(tmp_path):
    archive = name('20261009')
    data = b'fixture'
    backup.receive(tmp_path, 'vmsh',
                   f'put {archive} {len(data)} {hashlib.sha256(data).hexdigest()}', io.BytesIO(data))
    (tmp_path / archive).write_bytes(b'corrupted')
    with pytest.raises(RuntimeError, match='receipt mismatch'):
        backup.inventory(tmp_path, 'vmsh')


def test_failed_sync_preserves_all_local_history(fixture_config, monkeypatch):
    outgoing = Path(fixture_config['state']) / 'outgoing'
    old = outgoing / name('20200101')
    old.write_bytes(b'old archive')
    monkeypatch.setattr(backup.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a, 255, stdout='', stderr='unavailable'))
    fixture_config['ssh_config'] = '/fixture/ssh_config'
    with pytest.raises(RuntimeError, match='preserved'):
        backup.sync(fixture_config)
    assert old.read_bytes() == b'old archive'


@pytest.mark.parametrize('load_state,active_state,disable_expected', [
    ('not-found', 'inactive', False),
    ('not-found', 'failed', False),
    ('loaded', 'active', True),
])
def test_repeated_sync_accepts_retired_legacy_timer(
    fixture_config, monkeypatch, load_state, active_state, disable_expected,
):
    fixture_config.update(ssh_config='/fixture/ssh_config', legacy_timer='vmsh-backup.timer')
    disabled = []

    def run(command, **kwargs):
        if command[0] == 'ssh':
            return subprocess.CompletedProcess(command, 0, stdout='{}')
        if command[:2] == ['systemctl', 'show']:
            return subprocess.CompletedProcess(
                command, 0, stdout=f'LoadState={load_state}\nActiveState={active_state}\n',
            )
        assert command == ['systemctl', 'disable', '--now', 'vmsh-backup.timer']
        if load_state == 'not-found':
            raise subprocess.CalledProcessError(1, command)
        disabled.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(backup.subprocess, 'run', run)
    backup.sync(fixture_config)
    backup.sync(fixture_config)
    assert bool(disabled) == disable_expected


def test_receiver_lock_waits_for_concurrent_inventory_and_has_a_deadline(tmp_path):
    path = tmp_path / '.receive.lock'
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError), backup.lock(path):
            pass
        with pytest.raises(BlockingIOError), backup.lock(path, timeout=0.01):
            pass
        release = threading.Timer(0.05, fcntl.flock, args=(stream, fcntl.LOCK_UN))
        release.start()
        try:
            with backup.lock(path, timeout=2):
                pass
        finally:
            release.join()


def test_capture_and_real_encrypted_restore(fixture_config, tmp_path):
    if not fixture_config['sevenzip'] or 'GNU tar' not in subprocess.check_output(
        [fixture_config['tar'], '--version'], text=True
    ):
        pytest.skip('Real 7zip and GNU tar required')
    archive = backup.capture(fixture_config)
    assert archive.is_file()
    # Headers cannot be listed with an empty password; no secret in argv.
    result = subprocess.run([fixture_config['sevenzip'], 'l', '-p', str(archive)],
                            capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert 'synthetic-config-secret' not in result.stdout
    target = tmp_path / 'restored'
    backup.restore(fixture_config, archive, target, Path(fixture_config['password_file']))
    with tarfile.open(target / 'payload.tar') as tar:
        config_name = 'host/' + str(tmp_path / 'host/secret').lstrip('/')
        member = tar.getmember(config_name)
        assert member.mode == 0o600
        assert tar.extractfile(member).read() == b'synthetic-config-secret'
        link = tar.getmember('host/' + str(tmp_path / 'host/symlink').lstrip('/'))
        assert link.issym()
        assert link.linkname == str(tmp_path / 'external.conf')
        assert tar.extractfile('host/' + str(tmp_path / 'external.conf').lstrip('/')).read()
    assert not (target / 'host').exists()  # No absolute config symlink extraction.
    with sqlite3.connect(target / 'db/main.sqlite3') as db:
        assert db.execute('SELECT value FROM content').fetchone() == ('main',)


def test_low_disk_does_not_publish(fixture_config, monkeypatch):
    monkeypatch.setattr(backup.shutil, 'disk_usage', lambda path:
                        shutil._ntuple_diskusage(100, 90, 10))
    with pytest.raises(RuntimeError, match='free space'):
        backup.capture(fixture_config)
    assert not list((Path(fixture_config['state']) / 'outgoing').iterdir())


def test_wrong_password_rejects_restore(fixture_config, tmp_path):
    if not fixture_config['sevenzip']:
        pytest.skip('7zip required')
    archive = backup.capture(fixture_config)
    wrong = tmp_path / 'wrong-password'
    wrong.write_text('different-fixture-password-for-backup\n')
    wrong.chmod(0o600)
    with pytest.raises(RuntimeError, match='7zip operation failed'):
        backup.restore(fixture_config, archive, tmp_path / 'bad-restore', wrong)


def test_corrupt_database_does_not_publish(fixture_config):
    Path(fixture_config['databases']['analytics']).write_bytes(b'corrupt SQLite')
    with pytest.raises(sqlite3.DatabaseError):
        backup.capture(fixture_config)
    assert not list((Path(fixture_config['state']) / 'outgoing').iterdir())


def test_config_symlink_and_unit_environment_are_collected(tmp_path):
    nginx = tmp_path / 'nginx'
    nginx.mkdir()
    unit = tmp_path / 'external.service'
    env = tmp_path / 'secret.env'
    env.write_text('fixture-only')
    unit.write_text(f'[Service]\nEnvironmentFile=-{env}\n')
    (nginx / 'service').symlink_to(unit)
    paths = backup.config_paths({'config_paths': [str(nginx)], 'discover_credentials': False})
    assert nginx in paths
    assert unit in paths
    assert env in paths


def test_multiline_systemd_config_paths(tmp_path):
    unit = tmp_path / 'external.service'
    secret = tmp_path / 'secret.env'
    nats_config = tmp_path / 'nats.conf'
    secret.write_text('fixture-only')
    nats_config.write_text('fixture-only')
    unit.write_text('[Service]\nEnvironmentFile=\\\n    ' + str(secret) + '\n'
                    'ExecStart=/usr/bin/nats-server \\\n    --config=' + str(nats_config) + '\n')
    paths = backup.config_paths({'config_paths': [str(unit)], 'discover_credentials': False})
    assert secret in paths
    assert nats_config in paths


def test_sdk_exclusion_keeps_real_configuration(fixture_config, tmp_path):
    root = tmp_path / 'host'
    sdk = root / 'swift-fixture-RELEASE-ubuntu/usr'
    sdk.mkdir(parents=True)
    (sdk / 'compiler').write_bytes(b'not configuration')
    pattern = str(root / 'swift-*-RELEASE-*').lstrip('/')
    fixture_config['exclude_config_patterns'] = [pattern]
    assert backup.excluded(sdk / 'compiler', [pattern])
    estimated = backup.config_size([root], [pattern])
    assert estimated == (root / 'secret').stat().st_size + 1024
    archive = backup.capture(fixture_config)
    target = tmp_path / 'restored-without-sdk'
    backup.restore(fixture_config, archive, target, Path(fixture_config['password_file']))
    with tarfile.open(target / 'payload.tar') as tar:
        assert not any('swift-fixture' in member.name for member in tar)

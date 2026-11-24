"""Production configuration and private release artifacts, using fake credentials."""
import io
import gzip
import hashlib
import json
import random
import threading
import urllib.error
import zipfile
from types import SimpleNamespace

import pytest

from vmshpwa.scripts.production_frontend_build import (
    AUDIENCES, artifact_bundle, configure, private_json, validate_portal,
)


def portal():
    return dict(organization='vmsh', portal_origin='https://vmsh.shashkovs.ru',
                project='vmshpwa', frontend_dsn='https://public@glitch.leaders.tech/1',
                backend_dsn='https://public@glitch.leaders.tech/2', token='a' * 64)


def test_switch_preserves_credentials_and_future_builds_use_canonical_dsn(tmp_path):
    path = tmp_path / 'creds_prod/vmsh_bot_config_prod.json'
    original = dict(sentry_dsn='https://old@old.example/9', secret='preserve-this',
                    pwa_public_origins_json={'student': ['https://vmsh.shashkovs.ru']})
    private_json(path, original)
    private_json(tmp_path / '.runtime/glitchtip-portal.pending.json', portal())
    config, metadata = configure(tmp_path, 'release-1')
    assert config['secret'] == original['secret']
    assert config['sentry_dsn'] == portal()['backend_dsn']
    assert config['frontend_sentry_dsn'] == portal()['frontend_dsn']
    assert json.loads(path.with_name(path.name + '.before-glitchtip').read_text()) == original
    assert not (tmp_path / '.runtime/glitchtip-portal.pending.json').exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    config, next_metadata = configure(tmp_path, 'release-2')
    assert config['sentry_release'] == 'release-2'
    assert metadata == next_metadata


def test_wrong_portal_cannot_mutate_configuration(tmp_path):
    path = tmp_path / 'creds_prod/vmsh_bot_config_prod.json'
    original = dict(sentry_dsn='old', pwa_public_origins_json={'student': ['https://prep.leaders.tech']})
    private_json(path, original)
    private_json(tmp_path / '.runtime/glitchtip-portal.pending.json', portal())
    with pytest.raises(ValueError, match='Canonical portal'):
        configure(tmp_path, 'release-1')
    assert json.loads(path.read_text()) == original


@pytest.mark.parametrize('change', [dict(frontend_dsn='https://public@glitch.leaders.tech/3'),
                                    dict(backend_dsn='https://public@other.example/2'),
                                    dict(project='tlfpwa')])
def test_project_keys_cannot_cross_organizations(change):
    with pytest.raises(ValueError):
        validate_portal(dict(portal(), **change))


def test_private_maps_match_original_js_without_mutating_bytes(tmp_path):
    for audience in AUDIENCES:
        directory = tmp_path / 'vmshpwa/apps' / audience / 'dist/assets'
        directory.mkdir(parents=True)
        (directory / 'bundle-hash.js').write_text('throw new Error("synthetic")')
        (directory / 'bundle-hash.js.map').write_text('{"version":3}')
    bundle, manifest, maps = artifact_bundle(tmp_path, 'release-1', 'vmsh')
    assert len(maps) == 4
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for audience in AUDIENCES:
            name = audience + '/assets/bundle-hash.js'
            assert archive.read(name) == b'throw new Error("synthetic")'
            assert manifest['files'][name]['headers']['sourcemap'] == 'bundle-hash.js.map'
            assert manifest['files'][name]['url'] == '~/' + name
            assert maps[0].is_file()  # Assembly alone must not remove upload inputs.


def test_release_files_follow_lowercase_asgi_pagination_header(monkeypatch):
    from vmshpwa.scripts import production_frontend_build as build
    calls = []

    def fake_api(metadata, endpoint, headers):
        calls.append(endpoint)
        if len(calls) == 1:
            headers['link'] = '<https://glitch.leaders.tech/api/0/organizations/vmsh/releases/r/files/?cursor=next>; rel="next"; results="true"'
            return [{'name': 'first.js'}]
        headers['link'] = '<https://glitch.leaders.tech/api/0/organizations/vmsh/releases/r/files/>; rel="next"; results="false"'
        return [{'name': 'last.js.map'}]

    monkeypatch.setattr(build, 'api', fake_api)
    assert build.release_files(portal(), 'organizations/vmsh/releases/r/files/') == [
        {'name': 'first.js'}, {'name': 'last.js.map'},
    ]
    assert len(calls) == 2


def test_split_bundles_preserves_every_source_pair_and_manifest(tmp_path):
    from vmshpwa.scripts import production_frontend_build as build
    for audience in AUDIENCES:
        directory = tmp_path / 'vmshpwa/apps' / audience / 'dist/assets'
        directory.mkdir(parents=True)
        for index in range(3):
            data = random.Random(index).randbytes(20000)
            (directory / f'bundle-{index}.js').write_bytes(data)
            (directory / f'bundle-{index}.js.map').write_bytes(data[::-1])
    bundle, manifest, _ = artifact_bundle(tmp_path, 'release-1', 'vmsh')
    parts = list(build.split_artifact_bundles(bundle, manifest, max_bytes=90000))
    assert len(parts) > 1
    recovered = {}
    with zipfile.ZipFile(io.BytesIO(bundle)) as original:
        for value, selected in parts:
            assert len(value) <= 90000
            with zipfile.ZipFile(io.BytesIO(value)) as archive:
                assert json.loads(archive.read('manifest.json')) == selected
                for name, entry in selected['files'].items():
                    assert name not in recovered
                    assert archive.read(name) == original.read(name)
                    if entry['type'] == 'minified_source':
                        assert name + '.map' in selected['files']
                    recovered[name] = entry
    assert recovered == manifest['files']


def test_upload_respects_small_requests_and_advertised_concurrency(tmp_path, monkeypatch):
    from vmshpwa.scripts import production_frontend_build as build
    for index, audience in enumerate(AUDIENCES):
        directory = tmp_path / 'vmshpwa/apps' / audience / 'dist/assets'
        directory.mkdir(parents=True)
        (directory / f'bundle-{index}.js').write_bytes(random.Random(index).randbytes(400000))
        (directory / f'bundle-{index}.js.map').write_bytes(random.Random(index + 4).randbytes(400000))
    bundle, manifest, maps = artifact_bundle(tmp_path, 'release-1', 'vmsh')
    chunks, recovered, assembly_sizes = {}, {}, []
    lock = threading.Lock()
    active = 0
    maximum = 0

    def fake_api(metadata, endpoint, value=None, content_type='application/json', headers=None):
        nonlocal active, maximum
        assert metadata == portal()
        if endpoint.endswith('/releases/'):
            return {}
        if endpoint.endswith('/chunk-upload/') and value is None:
            return {'compression': ['gzip'], 'accept': ['release_files'],
                    'chunkSize': 32 * 1024 * 1024, 'concurrency': 1}
        if endpoint.endswith('/chunk-upload/'):
            assert len(value) < 9 * 1024
            with lock:
                active += 1
                maximum = max(maximum, active)
            raw = gzip.decompress(value.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0])
            checksum = hashlib.sha1(raw).hexdigest()
            assert checksum.encode() in value.split(b'\r\n\r\n', 1)[0]
            with lock:
                chunks[checksum] = raw
                active -= 1
            return {}
        if endpoint.endswith('/artifactbundle/assemble/'):
            assembly_sizes.append(len(json.dumps(value).encode()))
            assert assembly_sizes[-1] <= 12 * 1024
            assembled = b''.join(chunks[item] for item in value['chunks'])
            assert hashlib.sha1(assembled).hexdigest() == value['checksum']
            with zipfile.ZipFile(io.BytesIO(assembled)) as archive:
                selected = json.loads(archive.read('manifest.json'))
                assert selected['release'] == 'release-1'
                for name in selected['files']:
                    assert name not in recovered
                    recovered[name] = archive.read(name)
            return {'missingChunks': [], 'state': 'created'}
        assert endpoint.endswith('/files/?limit=10')
        return [{'name': name.rsplit('/', 1)[-1]} for name in recovered]

    monkeypatch.setattr(build, 'api', fake_api)
    build.upload(portal(), 'release-1', bundle, manifest)
    assert maximum == 1
    assert len(assembly_sizes) > 1
    assert set(recovered) == set(manifest['files'])
    assert all(path.is_file() for path in maps)


def test_api_retries_transport_failures_and_decodes_gzip(monkeypatch):
    from vmshpwa.scripts import production_frontend_build as build
    calls, sleeps = [], []

    def open_request(request, timeout):
        calls.append(request)
        assert timeout == 20
        assert request.get_header('Accept-encoding') == 'gzip'
        if len(calls) < 3:
            raise urllib.error.URLError('private underlying detail')
        response = io.BytesIO(gzip.compress(b'{"accepted":true}'))
        response.headers = {'Content-Encoding': 'gzip', 'Link': 'next'}
        return response

    monkeypatch.setattr(build.urllib.request, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    monkeypatch.setattr(build.time, 'sleep', sleeps.append)
    headers = {}
    assert build.api(portal(), 'organizations/vmsh/chunk-upload/', headers=headers) == {'accepted': True}
    assert headers['link'] == 'next'
    assert sleeps == [1, 2]
    assert len(calls) == 3


@pytest.mark.parametrize('status,attempts', [(403, 1), (429, 3), (503, 3)])
def test_api_permanent_and_transient_http_failures_are_bounded_and_private(monkeypatch, status, attempts):
    from vmshpwa.scripts import production_frontend_build as build
    calls = []

    def fail(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, status, 'private body and credential', {}, None)

    monkeypatch.setattr(build.urllib.request, 'build_opener', lambda *args: SimpleNamespace(open=fail))
    monkeypatch.setattr(build.time, 'sleep', lambda seconds: None)
    with pytest.raises(RuntimeError) as raised:
        build.api(portal(), 'organizations/vmsh/chunk-upload/')
    assert str(raised.value) == f'GlitchTip upload HTTP {status}'
    assert len(calls) == attempts


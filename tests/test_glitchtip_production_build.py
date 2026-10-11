"""Production configuration and private release artifacts, using fake credentials."""
import io
import json
import zipfile

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

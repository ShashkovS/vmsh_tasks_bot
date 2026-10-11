"""Build and privately upload maps before publication; migration-20261011.md.

A staged, owner-provisioned portal file switches canonical frontend/backend DSNs.
Future deployments read canonical configuration, even when an older installed
shell wrapper still supplies its original fallback DSN. No runtime imports.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIENCES = ('landing', 'student', 'family', 'staff')
PORTALS = {
    'vmsh': ('https://vmsh.shashkovs.ru', 'vmshpwa', '1', '2'),
    'tlf': ('https://prep.leaders.tech', 'tlfpwa', '3', '4'),
}
GLITCHTIP = 'https://glitch.leaders.tech'


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    os.replace(temporary, path)


def validate_portal(value):
    origin, project, frontend_id, backend_id = PORTALS[value['organization']]
    if value['portal_origin'] != origin or value['project'] != project:
        raise ValueError('Portal/project mismatch')
    for key, project_id in [('frontend_dsn', frontend_id), ('backend_dsn', backend_id)]:
        parsed = urllib.parse.urlsplit(value[key])
        if (parsed.scheme != 'https' or parsed.hostname != 'glitch.leaders.tech'
                or not parsed.username or parsed.password or parsed.port
                or parsed.path != '/' + project_id or parsed.query or parsed.fragment):
            raise ValueError('GlitchTip DSN/project mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}', value['token']):
        raise ValueError('Invalid upload credential')
    return value


def configure(root, release):
    config_path = (root / 'creds_prod/vmsh_bot_config_prod.json').resolve()
    persistent = root / '.runtime/glitchtip-portal.json'
    pending = root / '.runtime/glitchtip-portal.pending.json'
    metadata = None
    if pending.exists():
        metadata = validate_portal(json.loads(pending.read_text()))
        config = json.loads(config_path.read_text())
        # Bind staged keys to the actual configured portal, never to a CLI guess.
        origins = config.get('pwa_public_origins_json', {})
        if isinstance(origins, str):
            origins = json.loads(origins)
        if metadata['portal_origin'] not in json.dumps(origins):
            raise ValueError('Canonical portal origin does not match staged keys')
        backup = config_path.with_name(config_path.name + '.before-glitchtip')
        if not backup.exists():
            private_json(backup, config)
        config['sentry_dsn'] = metadata['backend_dsn']
        config['frontend_sentry_dsn'] = metadata['frontend_dsn']
        config['sentry_release'] = release
        private_json(persistent, metadata)
        private_json(config_path, config)
        pending.unlink()
    elif persistent.exists():
        metadata = validate_portal(json.loads(persistent.read_text()))
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    if metadata:
        if (config.get('sentry_dsn') != metadata['backend_dsn']
                or config.get('frontend_sentry_dsn') != metadata['frontend_dsn']):
            raise ValueError('Canonical DSNs disagree with upload configuration')
        if config.get('sentry_release') != release:
            config['sentry_release'] = release
            private_json(config_path, config)
    return config, metadata


def artifact_bundle(root, release, organization):
    """Release + hashed filename lookup, without changing JS or SW cache bytes."""
    manifest = {'org': organization, 'release': release, 'files': {}}
    maps = []
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, 'w', zipfile.ZIP_DEFLATED) as archive:
        for audience in AUDIENCES:
            dist = root / 'vmshpwa/apps' / audience / 'dist'
            found = sorted(dist.rglob('*.js.map'))
            if not found:
                raise ValueError('Production sourcemaps missing for ' + audience)
            for source_map in found:
                source = source_map.with_suffix('')
                if not source.is_file():
                    raise ValueError('Sourcemap missing its JavaScript file')
                maps.append(source_map)
                for path, kind in [(source, 'minified_source'), (source_map, 'source_map')]:
                    relative = path.relative_to(dist).as_posix()
                    name = audience + '/' + relative
                    headers = {'sourcemap': source_map.name} if kind == 'minified_source' else {}
                    manifest['files'][name] = {
                        'url': '~/' + name, 'type': kind, 'headers': headers,
                    }
                    archive.write(path, name)
        archive.writestr('manifest.json', json.dumps(manifest))
    return contents.getvalue(), manifest, maps


def api(metadata, endpoint, value=None, content_type='application/json', headers=None):
    data = (json.dumps(value).encode() if isinstance(value, dict) else value)
    request = urllib.request.Request(
        GLITCHTIP + '/api/0/' + endpoint, data=data,
        headers={'Authorization': 'Bearer ' + metadata['token'],
                 'Content-Type': content_type},
    )
    # Never log HTTP bodies/credentials. No cross-host redirects for bearer tokens.
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=60) as response:
            if headers is not None:
                headers.update(response.headers)
            payload = response.read()
            return json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        raise RuntimeError('GlitchTip upload HTTP ' + str(error.code)) from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def release_files(metadata, endpoint):
    files = []
    for _ in range(100):
        headers = {}
        files.extend(api(metadata, endpoint, headers=headers))
        next_page = re.search(r'<([^>]+)>; rel="next"; results="true"', headers.get('Link', ''))
        if not next_page:
            return files
        url = urllib.parse.urlsplit(next_page[1])
        if url.scheme != 'https' or url.netloc != 'glitch.leaders.tech' or not url.path.startswith('/api/0/'):
            raise ValueError('Invalid artifact pagination URL')
        endpoint = url.path.removeprefix('/api/0/') + '?' + url.query
    raise ValueError('Too many artifact pages')


def upload(metadata, release, bundle, manifest):
    prefix = 'organizations/' + metadata['organization'] + '/'
    api(metadata, prefix + 'releases/', {'version': release, 'projects': [metadata['project']]})
    settings = api(metadata, prefix + 'chunk-upload/')
    if 'gzip' not in settings['compression'] or 'release_files' not in settings['accept']:
        raise ValueError('Server does not support release artifact uploads')
    chunks = []
    size = min(settings['chunkSize'], 32 * 1024 * 1024)
    for offset in range(0, len(bundle), size):
        chunk = bundle[offset:offset + size]
        checksum = hashlib.sha1(chunk).hexdigest()
        chunks.append(checksum)
        boundary = uuid.uuid4().hex
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; '
                   f'name="file_gzip"; filename="{checksum}"\r\n'
                   'Content-Type: application/gzip\r\n\r\n').encode()
        payload += gzip.compress(chunk) + f'\r\n--{boundary}--\r\n'.encode()
        api(metadata, prefix + 'chunk-upload/', payload, 'multipart/form-data; boundary=' + boundary)
    result = api(metadata, prefix + 'artifactbundle/assemble/', {
        'checksum': hashlib.sha1(bundle).hexdigest(), 'chunks': chunks,
        'projects': [metadata['project']], 'version': release,
    })
    if result['missingChunks'] or result['state'] not in ('created', 'ok'):
        raise ValueError('Artifact assembly rejected')
    # GlitchTip 6.2 acknowledges queueing, not assembly. Verify stored artifacts.
    expected = {Path(name).name for name in manifest['files']}
    for _ in range(60):
        stored = release_files(metadata, prefix + 'releases/' + release + '/files/?limit=100')
        if expected.issubset({item['name'] for item in stored}):
            return
        time.sleep(2)
    raise RuntimeError('Sourcemap assembly was not confirmed; release must not publish')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--media-origin', required=True)
    parser.add_argument('--fallback-dsn', default='')
    arguments = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}', arguments.release):
        parser.error('Invalid production release ID')
    config, metadata = configure(ROOT, arguments.release)
    environment = dict(os.environ, CI='true', VMSH_FRONTEND_BUILD_PROFILE='production',
                       VITE_ENABLE_MSW='false', VITE_PROTOTYPE='false',
                       VITE_PUBLIC_MEDIA_ORIGIN=arguments.media_origin,
                       VITE_SENTRY_DSN=config.get('frontend_sentry_dsn') or arguments.fallback_dsn,
                       VITE_SENTRY_RELEASE=arguments.release)
    subprocess.run(['pnpm', 'build'], cwd=ROOT / 'vmshpwa', env=environment, check=True)
    maps = list((ROOT / 'vmshpwa/apps').glob('*/dist/**/*.map'))
    if metadata:
        bundle, manifest, _ = artifact_bundle(ROOT, arguments.release, metadata['organization'])
        upload(metadata, arguments.release, bundle, manifest)
        print(json.dumps({'release': arguments.release, 'organization': metadata['organization'],
                          'privateArtifacts': len(manifest['files']), 'upload': 'verified'}))
    # Maps may never reach immutable public roots, including fallback deployments.
    for source_map in maps:
        source_map.unlink()


if __name__ == '__main__':
    main()

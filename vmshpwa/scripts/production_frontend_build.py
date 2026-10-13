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
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIENCES = ('landing', 'student', 'family', 'staff')
PORTALS = {
    'vmsh': ('https://vmsh.shashkovs.ru', 'vmshpwa', '1', '2'),
    'tlf': ('https://prep.leaders.tech', 'tlfpwa', '3', '4'),
}
GLITCHTIP = 'https://glitch.leaders.tech'
# Direct HTTPS transport limits and proof: docs/deploy/glitchtip/migration-20261011.md.
UPLOAD_CHUNK_BYTES = 8 * 1024
ARTIFACT_BUNDLE_BYTES = 1792 * 1024
RELEASE_FILES_PAGE_SIZE = 10
API_ATTEMPTS = 3


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
                 'Content-Type': content_type, 'Accept-Encoding': 'gzip'},
    )
    # Never log HTTP bodies/credentials. No cross-host redirects for bearer tokens.
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(API_ATTEMPTS):
        try:
            with opener.open(request, timeout=20) as response:
                payload = response.read()
                if response.headers.get('Content-Encoding', '').lower() == 'gzip':
                    payload = gzip.decompress(payload)
                result = json.loads(payload) if payload else None
                if headers is not None:
                    headers.update({key.lower(): value for key, value in response.headers.items()})
                return result
        except urllib.error.HTTPError as error:
            error.close()
            if error.code not in (429, 502, 503, 504) or attempt == API_ATTEMPTS - 1:
                raise RuntimeError('GlitchTip upload HTTP ' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == API_ATTEMPTS - 1:
                # No response bodies, bearer credentials or underlying exception text.
                raise RuntimeError('GlitchTip HTTPS transport failed after 3 attempts') from None
        time.sleep(2 ** attempt)


def split_artifact_bundles(bundle, manifest, max_bytes=ARTIFACT_BUNDLE_BYTES):
    """Keep both chunk bodies and assemble checksum lists below transport limits."""
    with zipfile.ZipFile(io.BytesIO(bundle)) as original:
        def encode(names):
            selected = dict(manifest, files={name: manifest['files'][name] for name in names})
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name in names:
                    archive.writestr(original.getinfo(name), original.read(name))
                archive.writestr('manifest.json', json.dumps(selected))
            value = output.getvalue()
            if len(value) > max_bytes:
                raise ValueError('One sourcemap pair exceeds the direct HTTPS bundle limit')
            return value, selected

        names = []
        estimate = 512
        for name, entry in manifest['files'].items():
            if entry['type'] != 'minified_source':
                continue
            pair = [name, name + '.map']
            # Conservative ZIP headers + uncompressed manifest allowance.
            pair_bytes = sum(original.getinfo(item).compress_size + 512 +
                             len(json.dumps(manifest['files'][item]).encode()) +
                             len(item.encode()) for item in pair)
            if names and estimate + pair_bytes > max_bytes:
                yield encode(names)
                names = []
                estimate = 512
            names.extend(pair)
            estimate += pair_bytes
        if names:
            yield encode(names)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def release_files(metadata, endpoint):
    files = []
    for _ in range(1000):
        headers = {}
        files.extend(api(metadata, endpoint, headers=headers))
        next_page = re.search(r'<([^>]+)>; rel="next"; results="true"', headers.get('link', ''))
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
    size = min(settings['chunkSize'], UPLOAD_CHUNK_BYTES)
    if size <= 0:
        raise ValueError('Invalid upload chunk size')
    concurrency = min(max(int(settings.get('concurrency', 1)), 1), 4)

    def upload_chunk(chunk):
        checksum = hashlib.sha1(chunk).hexdigest()
        boundary = uuid.uuid4().hex
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; '
                   f'name="file_gzip"; filename="{checksum}"\r\n'
                   'Content-Type: application/gzip\r\n\r\n').encode()
        payload += gzip.compress(chunk, mtime=0) + f'\r\n--{boundary}--\r\n'.encode()
        api(metadata, prefix + 'chunk-upload/', payload, 'multipart/form-data; boundary=' + boundary)
        return checksum

    total_chunks = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for part, _ in split_artifact_bundles(bundle, manifest):
            parts = (part[offset:offset + size] for offset in range(0, len(part), size))
            chunks = list(executor.map(upload_chunk, parts))
            assembly = {'checksum': hashlib.sha1(part).hexdigest(), 'chunks': chunks,
                        'projects': [metadata['project']], 'version': release}
            if len(json.dumps(assembly).encode()) > 12 * 1024:
                raise ValueError('Assemble request exceeds the direct HTTPS limit')
            result = api(metadata, prefix + 'artifactbundle/assemble/', assembly)
            if result['missingChunks'] or result['state'] not in ('created', 'ok'):
                raise ValueError('Artifact assembly rejected')
            total_chunks += len(chunks)
            print(json.dumps({'phase': 'private-artifact-upload',
                              'chunks': total_chunks}), flush=True)
    # GlitchTip 6.2 acknowledges queueing, not assembly. Verify stored artifacts.
    expected = Counter(Path(name).name for name in manifest['files'])
    for _ in range(60):
        stored = release_files(metadata, prefix + 'releases/' + release +
                               f'/files/?limit={RELEASE_FILES_PAGE_SIZE}')
        if not (expected - Counter(item['name'] for item in stored)):
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
